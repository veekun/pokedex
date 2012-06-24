# encoding: utf8
u"""
Handles reading and encryption/decryption of Pokémon save file data.

See: http://projectpokemon.org/wiki/Pokemon_NDS_Structure

Kudos to LordLandon for his pkmlib.py, from which this module was originally
derived.
"""

import struct

from pokedex.db import tables
from pokedex.formulae import calculated_hp, calculated_stat
from pokedex.compatibility import namedtuple, permutations
from pokedex.struct._pokemon_struct import make_pokemon_struct

def pokemon_prng(seed):
    u"""Creates a generator that simulates the main Pokémon PRNG."""
    while True:
        seed = 0x41C64E6D * seed + 0x6073
        seed &= 0xFFFFFFFF
        yield seed >> 16


def _struct_proxy(name):
    def getter(self):
        return getattr(self.structure, name)

    def setter(self, value):
        setattr(self.structure, name, value)

    return property(getter, setter)

def _struct_frozenset_proxy(name):
    def getter(self):
        bitstruct = getattr(self.structure, name)
        return frozenset(k for k, v in bitstruct.items() if v)

    def setter(self, value):
        bitstruct = dict((k, True) for k in value)
        setattr(self.structure, name, bitstruct)

    return property(getter, setter)


class SaveFilePokemon(object):
    u"""Base class for an individual Pokémon, from the game's point of view.

    Handles translating between the on-disk encrypted form, the in-RAM blob
    (also used by pokesav), and something vaguely intelligible.
    """
    Stat = namedtuple('Stat', ['stat', 'base', 'gene', 'exp', 'calc'])

    def __init__(self, blob=None, encrypted=False, session=None):
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

            self.structure = self.pokemon_struct.parse(self.blob)
        else:
            self.structure = self.pokemon_struct.parse('\0' * (32 * 4 + 8))

        if session:
            self.use_database_session(session)
        else:
            self._session = None

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

    def export(self):
        """Exports the pokemon as a YAML/JSON-compatible dict
        """
        st = self.structure

        result = dict(
            species=dict(id=self.species.id, name=self.species.name),
            ability=dict(id=self.ability.id, name=self.ability.name),
        )

        result['original trainer'] = dict(
                id=self.original_trainer_id,
                secret=self.original_trainer_secret_id,
                name=unicode(self.original_trainer_name),
                gender=self.original_trainer_gender
            )

        if self.form != self.species.default_form:
            result['form'] = dict(id=self.form.id, name=self.form.form_name)
        if self.held_item:
            result['item'] = dict(id=self.item.id, name=self.item.name)
        if self.exp:
            result['exp'] = self.exp
        if self.happiness:
            result['happiness'] = self.happiness
        if self.markings:
            result['markings'] = sorted(self.markings)
        if self.original_country and self.original_country != '_unset':
            result['original country'] = self.original_country
        if self.original_version and self.original_version != '_unset':
            result['original version'] = self.original_version
        if self.encounter_type and self.encounter_type != '_unset':
            result['encounter type'] = self.encounter_type
        if self.nickname:
            result['nickname'] = unicode(self.nickname)
        if self.egg_location:
            result['egg location'] = dict(id=self.egg_location.id,
                name=self.egg_location.name)
        if self.met_location:
            result['met location'] = dict(id=self.egg_location.id,
                name=self.met_location.name)
        if self.date_egg_received:
            result['egg received'] = self.date_egg_received.isoformat()
        if self.date_met:
            result['date met'] = self.date_met.isoformat()
        if self.pokerus:
            result['pokerus data'] = self.pokerus
        if self.pokeball:
            result['pokeball'] = dict(id=self.pokeball.id,
                name=self.pokeball.name)
        if self.met_at_level:
            result['met at level'] = self.met_at_level

        if not self.is_nicknamed:
            result['not nicknamed'] = True
        if self.is_egg:
            result['is egg'] = True
        if self.fateful_encounter:
            result['fateful encounter'] = True
        if self.gender != 'genderless':
            result['gender'] = self.gender

        moves = result['moves'] = []
        for i, move_object in enumerate(self.moves, 1):
            move = {}
            if move_object:
                move['id'] = move_object.id
                move['name'] = move_object.name
            pp = st['move%s_pp' % i]
            if pp:
                move['pp'] = pp
            pp_up = st['move%s_pp_ups' % i]
            if pp_up:
                move['pp_up'] = pp_up
            if move:
                moves.append(move)

        effort = {}
        genes = {}
        contest_stats = {}
        for pokemon_stat in self._pokemon.stats:
            stat_identifier = pokemon_stat.stat.identifier.replace('-', '_')
            if st['iv_' + stat_identifier]:
                genes[stat_identifier] = st['iv_' + stat_identifier]
            if st['effort_' + stat_identifier]:
                effort[stat_identifier] = st['effort_' + stat_identifier]
        for contest_stat in 'cool', 'beauty', 'cute', 'smart', 'tough', 'sheen':
            if st['contest_' + contest_stat]:
                contest_stats[contest_stat] = st['contest_' + contest_stat]
        if effort:
            result['effort'] = effort
        if genes:
            result['genes'] = genes
        if contest_stats:
            result['contest_stats'] = contest_stats

        ribbons = list(self.ribbons)
        if ribbons:
            result['ribbons'] = ribbons
        return result

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
        self._session = session

        st = self.structure

        if st.national_id:
            self._pokemon = session.query(tables.Pokemon).get(st.national_id)
            self._pokemon_form = session.query(tables.PokemonForm) \
                .with_parent(self._pokemon) \
                .filter_by(form_identifier=st.alternate_form) \
                .one()
        else:
            self._pokemon = self._pokemon_form = None
        self._ability = self._session.query(tables.Ability).get(st.ability_id)

        if self._pokemon:
            growth_rate = self._pokemon.species.growth_rate
            self._experience_rung = session.query(tables.Experience) \
                .filter(tables.Experience.growth_rate == growth_rate) \
                .filter(tables.Experience.experience <= st.exp) \
                .order_by(tables.Experience.level.desc()) \
                [0]
            level = self._experience_rung.level

            self._next_experience_rung = None
            if level < 100:
                self._next_experience_rung = session.query(tables.Experience) \
                    .filter(tables.Experience.growth_rate == growth_rate) \
                    .filter(tables.Experience.level == level + 1) \
                    .one()

        self._held_item = None
        if st.held_item_id:
            self._held_item = session.query(tables.ItemGameIndex) \
                .filter_by(generation_id = 4, game_index = st.held_item_id).one().item

        if self._pokemon:
            self._stats = []
            for pokemon_stat in self._pokemon.stats:
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

                self._stats.append(stat_tup)
        else:
            self._stats = [0] * 6


        move_ids = (
            self.structure.move1_id,
            self.structure.move2_id,
            self.structure.move3_id,
            self.structure.move4_id,
        )
        move_rows = self._session.query(tables.Move).filter(tables.Move.id.in_(move_ids))
        moves_dict = dict((move.id, move) for move in move_rows)

        self._moves = [moves_dict.get(move_id, None) for move_id in move_ids]

        if st.hgss_pokeball >= 17:
            pokeball_id = st.hgss_pokeball - 17 + 492
        elif st.dppt_pokeball:
            pokeball_id = st.dppt_pokeball
        else:
            pokeball_id = None
        if pokeball_id:
            self._pokeball = session.query(tables.ItemGameIndex) \
                .filter_by(generation_id = 4, game_index = pokeball_id).one().item

        egg_loc_id = st.pt_egg_location_id or st.dp_egg_location_id
        met_loc_id = st.pt_met_location_id or st.dp_met_location_id

        self._egg_location = None
        if egg_loc_id:
            self._egg_location = session.query(tables.LocationGameIndex) \
                .filter_by(generation_id = self.generation_id, game_index = egg_loc_id).one().location

        if met_loc_id:
            self._met_location = session.query(tables.LocationGameIndex) \
                .filter_by(generation_id = self.generation_id, game_index = met_loc_id).one().location
        else:
            self._met_location = None

    @property
    def species(self):
        return self._pokemon_form.species

    @property
    def pokemon(self):
        return self._pokemon_form.pokemon

    @property
    def form(self):
        return self._pokemon_form

    @property
    def species_form(self):
        return self._pokemon_form

    @property
    def pokeball(self):
        return self._pokeball

    @property
    def egg_location(self):
        return self._egg_location

    @property
    def met_location(self):
        return self._met_location

    @property
    def level(self):
        return self._experience_rung.level

    @property
    def exp_to_next(self):
        if self._next_experience_rung:
            return self._next_experience_rung.experience - self.structure.exp
        else:
            return 0

    @property
    def progress_to_next(self):
        if self._next_experience_rung:
            return 1.0 \
                * (self.structure.exp - self._experience_rung.experience) \
                / (self._next_experience_rung.experience - self._experience_rung.experience)
        else:
            return 0.0

    @property
    def ability(self):
        return self._ability

    @property
    def held_item(self):
        return self._held_item

    @property
    def stats(self):
        return self._stats

    @property
    def moves(self):
        return self._moves

    @property
    def move_pp(self):
        return (
            self.structure.move1_pp,
            self.structure.move2_pp,
            self.structure.move3_pp,
            self.structure.move4_pp,
        )

    @property
    def markings(self):
        return frozenset(k for k, v in self.structure.markings.items() if v)

    @markings.setter
    def markings(self, value):
        self.structure.markings = dict((k, True) for k in value)

    original_trainer_id = _struct_proxy('original_trainer_id')
    original_trainer_secret_id = _struct_proxy('original_trainer_secret_id')
    original_trainer_name = _struct_proxy('original_trainer_name')
    exp = _struct_proxy('exp')
    happiness = _struct_proxy('happiness')
    original_country = _struct_proxy('original_country')
    is_nicknamed = _struct_proxy('is_nicknamed')
    is_egg = _struct_proxy('is_egg')
    fateful_encounter = _struct_proxy('fateful_encounter')
    gender = _struct_proxy('gender')
    original_version = _struct_proxy('original_version')
    date_egg_received = _struct_proxy('date_egg_received')
    date_met = _struct_proxy('date_met')
    pokerus = _struct_proxy('pokerus')
    met_at_level = _struct_proxy('met_at_level')
    original_trainer_gender = _struct_proxy('original_trainer_gender')
    encounter_type = _struct_proxy('encounter_type')

    markings = _struct_frozenset_proxy('markings')
    sinnoh_ribbons = _struct_frozenset_proxy('sinnoh_ribbons')
    hoenn_ribbons = _struct_frozenset_proxy('hoenn_ribbons')
    sinnoh_contest_ribbons = _struct_frozenset_proxy('sinnoh_contest_ribbons')

    @property
    def ribbons(self):
        return frozenset(
            self.sinnoh_ribbons |
            self.hoenn_ribbons |
            self.sinnoh_contest_ribbons)
    # XXX: ribbons setter

    @property
    def nickname(self):
        return self.structure.nickname

    @nickname.setter
    def nickname(self, value):
        self.structure.nickname = value
        self.structure.is_nicknamed = True

    @nickname.deleter
    def nickname(self, value):
        self.structure.nickname = ''
        self.structure.is_nicknamed = False

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

    def _reset(self):
        """Update self with modified pokemon_struct

        Rebuilds the blob; recalculates checksum; if a session was set,
        re-fetches the DB objects.
        """
        self.blob = self.pokemon_struct.build(self.structure)
        self.structure = self.pokemon_struct.parse(self.blob)
        checksum = sum(struct.unpack('H' * 0x40, self.blob[8:0x88])) & 0xffff
        self.structure.checksum = checksum
        self.blob = self.blob[:6] + struct.pack('H', checksum) + self.blob[8:]
        if self._session:
            self.use_database_session(self._session)


class SaveFilePokemonGen4(SaveFilePokemon):
    generation_id = 4
    pokemon_struct = make_pokemon_struct(generation=generation_id)

    def export(self):
        result = super(SaveFilePokemonGen5, self).export()
        if any(self.shiny_leaves):
            result['shiny leaves'] = self.shiny_leaves
        return result

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
        self._reset()


class SaveFilePokemonGen5(SaveFilePokemon):
    generation_id = 5
    pokemon_struct = make_pokemon_struct(generation=generation_id)

    def use_database_session(self, session):
        super(SaveFilePokemonGen5, self).use_database_session(session)

        st = self.structure

        if st.nature_id:
            self._nature = session.query(tables.Nature) \
                .filter_by(game_index = st.nature_id).one()

    def export(self):
        result = super(SaveFilePokemonGen5, self).export()
        result['nature'] = dict(id=self.nature.id, name=self.nature.name)
        return result

    # XXX: Ability setter must set hidden ability flag

    @property
    def nature(self):
        return self._nature

    @nature.setter
    def nature(self, new_nature):
        self.structure.nature_id = int(new_nature.game_index)
        self._reset()


save_file_pokemon_classes = {
    4: SaveFilePokemonGen4,
    5: SaveFilePokemonGen5,
}
