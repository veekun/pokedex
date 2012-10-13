# encoding: utf8
u"""
Handles reading and encryption/decryption of Pokémon save file data.

See: http://projectpokemon.org/wiki/Pokemon_NDS_Structure

Kudos to LordLandon for his pkmlib.py, from which this module was originally
derived.
"""

import struct
import base64
import datetime
import contextlib
from operator import attrgetter

import sqlalchemy.orm.exc

from pokedex.db import tables, util
from pokedex.formulae import calculated_hp, calculated_stat
from pokedex.compatibility import namedtuple, permutations
from pokedex.struct._pokemon_struct import (make_pokemon_struct, pokemon_forms,
    StringWithOriginal)

def pokemon_prng(seed):
    u"""Creates a generator that simulates the main Pokémon PRNG."""
    while True:
        seed = 0x41C64E6D * seed + 0x6073
        seed &= 0xFFFFFFFF
        yield seed >> 16


def struct_proxy(name, dependent=[]):
    def getter(self):
        return getattr(self.structure, name)

    def setter(self, value):
        setattr(self.structure, name, value)
        for dep in dependent:
            delattr(self, dep)
        del self.blob

    return property(getter, setter)


def struct_frozenset_proxy(name):
    def getter(self):
        bitstruct = getattr(self.structure, name)
        return frozenset(k for k, v in bitstruct.items() if v)

    def setter(self, new_set):
        new_set = set(new_set)
        struct = getattr(self.structure, name)
        for key in struct:
            setattr(struct, key, key in new_set)
            new_set.discard(key)
        if new_set:
            raise ValueError('Unknown values: {0}'.format(', '.join(ribbons)))
        del self.blob

    return property(getter, setter)


class cached_property(object):
    def __init__(self, getter, setter=None):
        self._getter = getter
        self._setter = setter
        self.cache_setter_value = True

    def setter(self, func):
        """With this setter, the value being set is automatically cached
        """
        self._setter = func
        self.cache_setter_value = True
        return self

    def complete_setter(self, func):
        """Setter without automatic caching of the set value
        """
        self._setter = func
        self.cache_setter_value = False
        return self

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            try:
                return instance._cached_properties[self]
            except AttributeError:
                instance._cached_properties = {}
            except KeyError:
                pass
            result = self._getter(instance)
            instance._cached_properties[self] = result
            return result

    def __set__(self, instance, value):
        if self._setter is None:
            raise AttributeError('Cannot set attribute')
        else:
            self._setter(instance, value)
            if self.cache_setter_value:
                try:
                    instance._cached_properties[self] = value
                except AttributeError:
                    instance._cached_properties = {self: value}
            del instance.blob

    def __delete__(self, instance):
        try:
            del instance._cached_properties[self]
        except (AttributeError, KeyError):
            pass


class InstrumentedList(object):
    def __init__(self, callback, initial=()):
        self.list = list(initial)
        self.callback = callback

    def __getitem__(self, index):
        return self.list[index]

    def __setitem__(self, index, value):
        self.list[index] = value
        self.callback()

    def __delitem__(self, index, value):
        self.list[index] = value
        self.callback()

    def append(self, item):
        self.list.append(item)
        self.callback()

    def extend(self, extralist):
        self.list.extend(extralist)
        self.callback()

    def __iter__(self):
        return iter(self.list)


class SaveFilePokemon(object):
    u"""Base class for an individual Pokémon, from the game's point of view.

    Handles translating between the on-disk encrypted form, the in-RAM blob
    (also used by pokesav), and something vaguely intelligible.
    """
    Stat = namedtuple('Stat', ['stat', 'base', 'gene', 'exp', 'calc'])

    def __init__(self, blob=None, dict_=None, encrypted=False, session=None):
        u"""Wraps a Pokémon save struct in a friendly object.

        If `encrypted` is True, the blob will be decrypted as though it were an
        on-disk save.  Otherwise, the blob is taken to be already decrypted and
        is left alone.

        `session` is an optional database session. Either give it or fill it
            later with `use_database_session`
        """

        try:
            self.generation_id
        except AttributeError:
            raise NotImplementedError(
                "Use generation-specific subclass of SaveFilePokemon")

        if blob:
            if encrypted:
                # Decrypt it.
                # Interpret as one word (pid), followed by a bunch of shorts
                struct_def = "I" + "H" * ((len(blob) - 4) / 2)
                shuffled = list( struct.unpack(struct_def, blob) )

                # Apply standard Pokémon decryption, undo the block shuffling, and
                # done
                self.reciprocal_crypt(shuffled)
                words = self.shuffle_chunks(shuffled, reverse=True)
                self.blob = struct.pack(struct_def, *words)

            else:
                # Already decrypted
                self.blob = blob

        else:
            self.blob = '\0' * (32 * 4 + 8)

        if session:
            self.session = session
        else:
            self.session = None

        if dict_:
            self.update(dict_)

    @property
    def as_struct(self):
        u"""Returns a decrypted struct, aka .pkm file."""
        return self.blob

    @property
    def as_encrypted(self):
        u"""Returns an encrypted struct the game expects in a save file."""

        # Interpret as one word (pid), followed by a bunch of shorts
        struct_def = "I" + "H" * ((len(self.blob) - 4) / 2)
        words = list( struct.unpack(struct_def, self.blob) )

        # Apply the block shuffle and standard Pokémon encryption
        shuffled = self.shuffle_chunks(words)
        self.reciprocal_crypt(shuffled)

        # Stuff back into a string, and done
        return struct.pack(struct_def, *shuffled)

    def export_dict(self):
        """Exports the pokemon as a YAML/JSON-compatible dict
        """
        st = self.structure

        NO_VALUE = object()
        def save(target_dict, key, value=NO_VALUE, transform=None,
                condition=lambda x: x):
            """Set a dict key to a value, if a condition is true

            If value is not given, it is looked up on self.
            The value can be transformed by a function before setting.
            """
            if value is NO_VALUE:
                attrname = key.replace(' ', '_')
                value = getattr(self, attrname)
            if condition(value):
                if transform:
                    value = transform(value)
                target_dict[key] = value

        def save_string(target_dict, string_key, trash_key, string):
            """Save a string, including trash bytes"""
            target_dict[string_key] = unicode(string)
            trash = getattr(string, 'original', None)
            if trash:
                expected = (string + u'\uffff').encode('utf-16LE')
                if trash.rstrip('\0') != expected:
                    target_dict[trash_key] = base64.b64encode(trash)

        def save_object(target_dict, key, value=NO_VALUE, **extra):
            """Objects are represented as dicts with "name" and a bunch of IDs

            The name is for humans. The ID is the number from the struct.
            """
            save(target_dict, key, value=value, transform=lambda value:
                dict(name=value.name, **extra))

        result = dict(
            species=dict(id=self.species.id, name=self.species.name),
        )
        if self.form != self.species.default_form:
            result['form'] = dict(id=st.form_id, name=self.form.form_name)

        save_object(result, 'ability', id=st.ability_id)
        save_object(result, 'held item', id=st.held_item_id)
        save_object(result, 'pokeball', id=st.dppt_pokeball or st.hgss_pokeball)

        trainer = dict(
                id=self.original_trainer_id,
                secret=self.original_trainer_secret_id,
                name=unicode(self.original_trainer_name),
                gender=self.original_trainer_gender
            )
        save_string(trainer, 'name', 'name trash', self.original_trainer_name)
        if (trainer['id'] or trainer['secret'] or
                trainer['name'].strip('\0') or trainer['gender'] != 'male'):
            result['oiginal trainer'] = trainer

        save(result, 'exp')
        save(result, 'happiness')
        save(result, 'markings', transform=sorted)
        save(result, 'original country')
        save(result, 'original version')
        save(result, 'encounter type', condition=lambda et:
                (et and et != 'special'))
        save_string(result, 'nickname', 'nickname trash', self.nickname)
        save(result, 'egg received', self.date_egg_received,
            transform=lambda x: x.isoformat())
        save(result, 'date met',
            transform=lambda x: x.isoformat())
        save(result, 'pokerus data', self.pokerus)
        save(result, 'met at level')
        save(result, 'nicknamed', self.is_nicknamed)
        save(result, 'is egg')
        save(result, 'fateful encounter')
        save(result, 'personality')
        save(result, 'gender', condition=lambda g: g != 'genderless')
        save(result, 'has hidden ability', self.hidden_ability)
        save(result, 'ribbons',
            sorted(r.replace('_', ' ') for r in self.ribbons))

        for loc_type in 'egg', 'met':
            loc_dict = dict()
            save(loc_dict, 'id_pt', st['pt_{0}_location_id'.format(loc_type)])
            save(loc_dict, 'id_dp', st['dp_{0}_location_id'.format(loc_type)])
            save(loc_dict, 'name',
                getattr(self, '{0}_location'.format(loc_type)),
                transform=attrgetter('name'))
            save(result, '{0} location'.format(loc_type), loc_dict)

        moves = result['moves'] = []
        for i, move_object in enumerate(self.moves, 1):
            move = {}
            save(move, 'id', move_object, transform=attrgetter('id'))
            save(move, 'name', move_object, transform=attrgetter('name'))
            save(move, 'pp ups', st['move%s_pp_ups' % i])
            pp = st['move%s_pp' % i]
            if move or pp:
                move['pp'] = pp
                moves.append(move)

        effort = {}
        genes = {}
        contest_stats = {}
        for pokemon_stat in self.pokemon.stats:
            stat_identifier = pokemon_stat.stat.identifier
            st_stat_identifier = stat_identifier.replace('-', '_')
            dct_stat_identifier = stat_identifier.replace('-', ' ')
            genes[dct_stat_identifier] = st['iv_' + st_stat_identifier]
            effort[dct_stat_identifier] = st['effort_' + st_stat_identifier]
        for contest_stat in 'cool', 'beauty', 'cute', 'smart', 'tough', 'sheen':
            contest_stats[contest_stat] = st['contest_' + contest_stat]
        save(result, 'effort', effort, condition=any)
        save(result, 'genes', genes, condition=any)
        save(result, 'contest stats', contest_stats, condition=any)

        return result

    def update(self, dct, **kwargs):
        """Updates the pokemon from a YAML/JSON-compatible dict

        Dicts that don't specify all the data are allowed. They update the
        structure with the information they contain.

        Keyword arguments with single keys are allowed. The semantics are
        similar to dict.update.

        Unlike setting properties directly, the this method tries more to keep
        the result sensible, e.g. when species is updated, it can switch
        to/from genderless.
        """
        st = self.structure
        session = self.session
        dct.update(kwargs)
        if 'ability' in dct:
            st.ability_id = dct['ability']['id']
            del self.ability
        reset_form = False
        if 'form' in dct:
            st.alternate_form = dct['form']
            reset_form = True
        if 'species' in dct:
            st.national_id = dct['species']['id']
            if 'form' not in dct:
                st.alternate_form = 0
            reset_form = True
        if reset_form:
            del self.form
            if not self.is_nicknamed:
                self.nickname = self.species.name
                self.is_nicknamed = False
            if self.species.gender_rate == -1:
                self.gender = 'genderless'
            elif self.gender == 'genderless':
                # make id=0 the default, sorry if it looks sexist
                self.gender = 'male'
        if 'held item' in dct:
            st.held_item_id = dct['held item']['id']
            del self.held_item
        if 'pokeball' in dct:
            self.pokeball = self._get_pokeball(dct['pokeball']['id'])
            del self.pokeball
        def _load_values(source, **values):
            for attrname, key in values.iteritems():
                try:
                    value = source[key]
                except KeyError:
                    pass
                else:
                    setattr(self, attrname, value)
        def load_name(attr_name, dct, string_key, trash_key):
            if string_key in dct:
                if trash_key in dct:
                    name = StringWithOriginal(unicode(dct[string_key]))
                    name.original = base64.b64decode(dct[trash_key])
                    setattr(self, attr_name, name)
                else:
                    setattr(self, attr_name, unicode(dct[string_key]))
        if 'oiginal trainer' in dct:
            trainer = dct['oiginal trainer']
            _load_values(trainer,
                    original_trainer_id='id',
                    original_trainer_secret_id='secret',
                    original_trainer_gender='gender',
                )
            load_name('original_trainer_name', trainer, 'name', 'name trash')
        was_nicknamed = self.is_nicknamed
        _load_values(dct,
                exp='exp',
                happiness='happiness',
                markings='markings',
                original_country='original country',
                original_version='original version',
                encounter_type='encounter type',
                pokerus='pokerus data',
                met_at_level='met at level',
                is_egg='is egg',
                fateful_encounter='fateful encounter',
                gender='gender',
                personality='personality',
                hidden_ability='has hidden ability',
            )
        load_name('nickname', dct, 'nickname', 'nickname trash')
        self.is_nicknamed = was_nicknamed
        _load_values(dct,
                is_nicknamed='nicknamed',
            )
        for loc_type in 'egg', 'met':
            loc_dict = dct.get('{0} location'.format(loc_type))
            if loc_dict:
                dp_attr = 'dp_{0}_location_id'.format(loc_type)
                pt_attr = 'pt_{0}_location_id'.format(loc_type)
                if 'id_dp' in loc_dict:
                    st[dp_attr] = loc_dict['id_dp']
                if 'id_pt' in loc_dict:
                    st[pt_attr] = loc_dict['id_pt']
                delattr(self, '{0}_location'.format(loc_type))
        if 'date met' in dct:
            self.date_met = datetime.datetime.strptime(
                dct['date met'], '%Y-%m-%d').date()
        if 'egg received' in dct:
            self.date_egg_received = datetime.datetime.strptime(
                dct['egg received'], '%Y-%m-%d').date()
        if 'ribbons' in dct:
            self.ribbons = (r.replace(' ', '_') for r in dct['ribbons'])
        if 'moves' in dct:
            pp_reset_indices = []
            for i, movedict in enumerate(dct['moves']):
                st['move{0}_id'.format(i + 1)] = movedict['id']
                if 'pp' in movedict:
                    st['move{0}_pp'.format(i + 1)] = movedict['pp']
                else:
                    pp_reset_indices.append(i)
                if 'pp ups' in movedict:
                    st['move{0}_pp_ups'.format(i + 1)] = movedict['pp ups']
            for i in range(i + 1, 4):
                # Reset the rest of the moves
                st['move{0}_id'.format(i + 1)] = 0
                st['move{0}_pp'.format(i + 1)] = 0
                st['move{0}_pp_up'.format(i + 1)] = 0
            del self.moves
            del self.move_pp
            for i in pp_reset_indices:
                # Set default PP here, when the moves dict is regenerated
                st['move{0}_pp'.format(i + 1)] = self.moves[i].pp
        for key, prefix in (('genes', 'iv'), ('effort', 'effort'),
                ('contest stats', 'contest')):
            for name, value in dct.get(key, {}).items():
                st['{}_{}'.format(prefix, name.replace(' ', '_'))] = value
        return self

    ### Delicious data
    @property
    def is_shiny(self):
        u"""Returns true iff this Pokémon is shiny."""
        # See http://bulbapedia.bulbagarden.net/wiki/Personality#Shininess
        # But don't see it too much, because the above is super over
        # complicated.  Do this instead!
        personality_msdw = self.structure.personality >> 16
        personality_lsdw = self.structure.personality & 0xffff
        return (
            self.structure.original_trainer_id
            ^ self.structure.original_trainer_secret_id
            ^ personality_msdw
            ^ personality_lsdw
        ) < 8

    def use_database_session(self, session):
        """Remembers the given database session, and prefetches a bunch of
        database stuff.  Gotta call this (or give session to `__init__`) before
        you use the database properties like `species`, etc.
        """
        if self.session and self.session is not session:
            raise ValueError('Re-setting a session is not supported')
        self.session = session

    @cached_property
    def stats(self):
        stats = []
        for pokemon_stat in self.pokemon.stats:
            stat_identifier = pokemon_stat.stat.identifier.replace('-', '_')
            gene = st['iv_' + stat_identifier]
            exp  = st['effort_' + stat_identifier]

            if pokemon_stat.stat.identifier == u'hp':
                calc = calculated_hp
            else:
                calc = calculated_stat

            stat_tup = self.Stat(
                stat = pokemon_stat.stat,
                base = pokemon_stat.base_stat,
                gene = gene,
                exp  = exp,
                calc = calc(
                    pokemon_stat.base_stat,
                    level = level,
                    iv = gene,
                    effort = exp,
                ),
            )

            stats.append(stat_tup)
        return tuple(stats)

    @property
    def alternate_form(self):
        st = self.structure
        forms = pokemon_forms.get(st.national_id)
        if forms:
            return forms[st.alternate_form_id]
        else:
            return None

    @alternate_form.setter
    def alternate_form(self, alternate_form):
        st = self.structure
        forms = pokemon_forms.get(st.national_id)
        if forms:
            st.alternate_form_id = forms.index(alternate_form)
        else:
            st.alternate_form_id = 0
        del self.form

    @property
    def species(self):
        if self.form:
            return self.form.species
        else:
            return None

    @species.setter
    def species(self, species):
        self.form = species.default_form

    @property
    def pokemon(self):
        if self.form:
            return self.form.pokemon
        else:
            return None

    @pokemon.setter
    def pokemon(self, pokemon):
        self.form = pokemon.default_form

    @cached_property
    def form(self):
        st = self.structure
        session = self.session
        if st.national_id:
            pokemon = session.query(tables.Pokemon).get(st.national_id)
            if self.alternate_form:
                return session.query(tables.PokemonForm) \
                    .with_parent(pokemon) \
                    .filter_by(form_identifier=self.alternate_form) \
                    .one()
            else:
                return pokemon.default_form
        else:
            return None

    @form.setter
    def form(self, form):
        self.structure.national_id = form.species.id
        self.structure.alternate_form = form.form_identifier
        del self.species
        del self.pokemon
        self._reset()

    @cached_property
    def pokeball(self):
        st = self.structure
        if st.hgss_pokeball >= 17:
            pokeball_id = st.hgss_pokeball - 17 + 492
        elif st.dppt_pokeball:
            pokeball_id = st.dppt_pokeball
        else:
            return None
        return self._get_pokeball(pokeball_id)

    def _get_pokeball(self, pokeball_id):
        return (self.session.query(tables.ItemGameIndex)
            .filter_by(generation_id=4, game_index = pokeball_id).one().item)

    @pokeball.setter
    def pokeball(self, pokeball):
        st = self.structure
        st.hgss_pokeball = st.dppt_pokeball = 0
        if pokeball:
            pokeball_id = pokeball.id
            boundary = 492 - 17
            if pokeball_id >= boundary:
                st.hgss_pokeball = pokeball_id - boundary
            else:
                st.dppt_pokeball = pokeball_id

    @cached_property
    def egg_location(self):
        st = self.structure
        egg_loc_id = st.pt_egg_location_id or st.dp_egg_location_id
        if egg_loc_id:
            try:
                return self.session.query(tables.LocationGameIndex) \
                    .filter_by(generation_id=4,
                        game_index = egg_loc_id).one().location
            except sqlalchemy.orm.exc.NoResultFound:
                return None
        else:
            return None

    @cached_property
    def met_location(self):
        st = self.structure
        met_loc_id = st.pt_met_location_id or st.dp_met_location_id
        if met_loc_id:
            try:
                return self.session.query(tables.LocationGameIndex) \
                    .filter_by(generation_id=4,
                        game_index=met_loc_id).one().location
            except sqlalchemy.orm.exc.NoResultFound:
                return None
        else:
            return None

    @property
    def level(self):
        return self.experience_rung.level

    @cached_property
    def experience_rung(self):
        growth_rate = self.species.growth_rate
        return (session.query(tables.Experience)
            .filter(tables.Experience.growth_rate == growth_rate)
            .filter(tables.Experience.experience <= self.exp)
            .order_by(tables.Experience.level.desc())
            [0])

    @cached_property
    def next_experience_rung(self):
        level = self.level
        if level < 100:
            return (session.query(tables.Experience)
                .filter(tables.Experience.growth_rate == growth_rate)
                .filter(tables.Experience.level == level + 1)
                .one())
        else:
            return None

    @property
    def exp_to_next(self):
        if self.next_experience_rung:
            return self.next_experience_rung.experience - self.exp
        else:
            return 0

    @property
    def progress_to_next(self):
        if self.next_experience_rung:
            rung = self.experience_rung
            return (1.0 *
                (self.exp - rung.experience) /
                (self.next_experience_rung.experience - rung.experience))
        else:
            return 0.0

    @cached_property
    def ability(self):
        return self.session.query(tables.Ability).get(self.structure.ability_id)

    @ability.setter
    def ability(self, ability):
        self.structure.ability_id = ability.id

    @cached_property
    def held_item(self):
        held_item_id = self.structure.held_item_id
        if held_item_id:
            return self.session.query(tables.ItemGameIndex) \
                .filter_by(generation_id=self.generation_id,
                    game_index=held_item_id) \
                .one().item

    @cached_property
    def moves(self):
        move_ids = (
            self.structure.move1_id,
            self.structure.move2_id,
            self.structure.move3_id,
            self.structure.move4_id,
        )
        move_rows = (self.session.query(tables.Move)
            .filter(tables.Move.id.in_(move_ids)))
        moves_dict = dict((move.id, move) for move in move_rows)

        def callback():
            def get(index):
                try:
                    return result[x].id
                except AttributeError:
                    return 0
            self.structure.move1_id = get(0)
            self.structure.move2_id = get(1)
            self.structure.move3_id = get(2)
            self.structure.move4_id = get(3)
            self._reset()

        result = InstrumentedList(
            callback,
            [moves_dict.get(move_id, None) for move_id in move_ids])

        return result

    @moves.complete_setter
    def moves(self, new_moves):
        self.moves[:] = new_moves

    @cached_property
    def move_pp(self):
        return (
            self.structure.move1_pp,
            self.structure.move2_pp,
            self.structure.move3_pp,
            self.structure.move4_pp,
        )

    @move_pp.complete_setter
    def move_pp(self, new_pps):
        self.move_pp[:] = new_pps

    original_trainer_id = struct_proxy('original_trainer_id')
    original_trainer_secret_id = struct_proxy('original_trainer_secret_id')
    original_trainer_name = struct_proxy('original_trainer_name')
    exp = struct_proxy('exp',
        dependent=['experience_rung', 'next_experience_rung'])
    happiness = struct_proxy('happiness')
    original_country = struct_proxy('original_country')
    is_nicknamed = struct_proxy('is_nicknamed')
    is_egg = struct_proxy('is_egg')
    fateful_encounter = struct_proxy('fateful_encounter')
    gender = struct_proxy('gender')
    original_version = struct_proxy('original_version')
    date_egg_received = struct_proxy('date_egg_received')
    date_met = struct_proxy('date_met')
    pokerus = struct_proxy('pokerus')
    met_at_level = struct_proxy('met_at_level')
    original_trainer_gender = struct_proxy('original_trainer_gender')
    encounter_type = struct_proxy('encounter_type')
    personality = struct_proxy('personality')

    markings = struct_frozenset_proxy('markings')
    sinnoh_ribbons = struct_frozenset_proxy('sinnoh_ribbons')
    hoenn_ribbons = struct_frozenset_proxy('hoenn_ribbons')
    sinnoh_contest_ribbons = struct_frozenset_proxy('sinnoh_contest_ribbons')

    @property
    def ribbons(self):
        return frozenset(
            self.sinnoh_ribbons |
            self.hoenn_ribbons |
            self.sinnoh_contest_ribbons)

    @ribbons.setter
    def ribbons(self, ribbons):
        ribbons = set(ribbons)
        for ribbonset_name in (
                'sinnoh_ribbons', 'hoenn_ribbons', 'sinnoh_contest_ribbons'):
            ribbonset = self.structure[ribbonset_name]
            for ribbon_name in ribbonset:
                ribbonset[ribbon_name] = (ribbon_name in ribbons)
                ribbons.discard(ribbon_name)
        if ribbons:
            raise ValueError('Unknown ribbons: {0}'.format(', '.join(ribbons)))

    @property
    def nickname(self):
        return self.structure.nickname

    @nickname.setter
    def nickname(self, value):
        self.structure.nickname = value
        self.is_nicknamed = True
        del self.blob

    @nickname.deleter
    def nickname(self, value):
        self.structure.nickname = ''
        self.is_nicknamed = False
        del self.blob

    ### Utility methods

    shuffle_orders = list( permutations(range(4)) )

    @classmethod
    def shuffle_chunks(cls, words, reverse=False):
        """The main 128 encrypted bytes (or 64 words) in a save block are split
        into four chunks and shuffled around in some order, based on
        personality.  The actual order of shuffling is a permutation of four
        items in order, indexed by the shuffle index.  That is, 0 yields 0123,
        1 yields 0132, 2 yields 0213, etc.

        Given a list of words (the first of which should be the pid), this
        function returns the words in shuffled order.  Pass reverse=True to
        unshuffle instead.
        """

        pid = words[0]
        shuffle_index = (pid >> 0xD & 0x1F) % 24

        shuffle_order = cls.shuffle_orders[shuffle_index]
        if reverse:
            # Decoding requires going the other way; invert the order
            shuffle_order = [shuffle_order.index(i) for i in range(4)]

        shuffled = words[:3]  # skip the unencrypted stuff
        for chunk in shuffle_order:
            shuffled += words[ chunk * 16 + 3 : chunk * 16 + 19 ]
        shuffled += words[67:]  # extra bytes are also left alone

        return shuffled

    @classmethod
    def reciprocal_crypt(cls, words):
        u"""Applies the reciprocal Pokémon save file cipher to the provided
        list of words.

        Returns nothing; the list is changed in-place.
        """
        # Apply regular Pokémon "encryption": xor everything with the output of
        # the PRNG.  First three items are pid/unused/checksum and are not
        # encrypted.

        # Main data is encrypted using the checksum as a seed
        prng = pokemon_prng(words[2])
        for i in range(3, 67):
            words[i] ^= next(prng)

        if len(words) > 67:
            # Extra bytes are encrypted using the pid as a seed
            prng = pokemon_prng(words[0])
            for i in range(67, len(words)):
                words[i] ^= next(prng)

        return

    @cached_property
    def blob(self):
        blob = self.pokemon_struct.build(self.structure)
        self.structure = self.pokemon_struct.parse(blob)
        checksum = sum(struct.unpack('H' * 0x40, blob[8:0x88])) & 0xffff
        self.structure.checksum = checksum
        blob = blob[:6] + struct.pack('H', checksum) + blob[8:]
        return blob

    @blob.setter
    def blob(self, blob):
        self.structure = self.pokemon_struct.parse(blob)


class SaveFilePokemonGen4(SaveFilePokemon):
    generation_id = 4
    pokemon_struct = make_pokemon_struct(generation=generation_id)

    def export_dict(self):
        result = super(SaveFilePokemonGen5, self).export_dict()
        if any(self.shiny_leaves):
            result['shiny leaves'] = self.shiny_leaves
        return result

    def update(self, dct, **kwargs):
        dct.update(kwargs)
        if 'shiny leaves' in dct:
            self.shiny_leaves = dct['shiny leaves']
        super(SaveFilePokemonGen4, self).update(dct)

    @property
    def shiny_leaves(self):
        return (
            self.structure.shining_leaves.leaf1,
            self.structure.shining_leaves.leaf2,
            self.structure.shining_leaves.leaf3,
            self.structure.shining_leaves.leaf4,
            self.structure.shining_leaves.leaf5,
            self.structure.shining_leaves.crown,
        )

    @shiny_leaves.setter
    def shiny_leaves(self, new_values):
        (
            self.structure.shining_leaves.leaf1,
            self.structure.shining_leaves.leaf2,
            self.structure.shining_leaves.leaf3,
            self.structure.shining_leaves.leaf4,
            self.structure.shining_leaves.leaf5,
            self.structure.shining_leaves.crown,
        ) = new_values
        del self.blob


class SaveFilePokemonGen5(SaveFilePokemon):
    generation_id = 5
    pokemon_struct = make_pokemon_struct(generation=generation_id)

    def export_dict(self):
        result = super(SaveFilePokemonGen5, self).export_dict()
        if self.nature:
            result['nature'] = dict(
                id=self.structure.nature_id, name=self.nature.name)
        return result

    def update(self, dct, **kwargs):
        dct.update(kwargs)
        super(SaveFilePokemonGen5, self).update(dct)
        if 'nature' in dct:
            self.structure.nature_id = dct['nature']['id']
        if 'has hidden ability' not in dct:
            self.hidden_ability = (self.ability == self.pokemon.dream_ability
                and self.ability not in self.pokemon.abilities)

    @cached_property
    def nature(self):
        st = self.structure
        if st.nature_id:
            return (self.session.query(tables.Nature)
                .filter_by(game_index = st.nature_id).one())
        else:
            return None

    @nature.setter
    def nature(self, new_nature):
        self.structure.nature_id = int(new_nature.game_index)

    hidden_ability = struct_proxy('hidden_ability')


save_file_pokemon_classes = {
    4: SaveFilePokemonGen4,
    5: SaveFilePokemonGen5,
}
