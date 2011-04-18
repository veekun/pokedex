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
from pokedex.struct._pokemon_struct import pokemon_struct

def pokemon_prng(seed):
    u"""Creates a generator that simulates the main Pokémon PRNG."""
    while True:
        seed = 0x41C64E6D * seed + 0x6073
        seed &= 0xFFFFFFFF
        yield seed >> 16


class SaveFilePokemon(object):
    u"""Represents an individual Pokémon, from the game's point of view.

    Handles translating between the on-disk encrypted form, the in-RAM blob
    (also used by pokesav), and something vaguely intelligible.
    """

    Stat = namedtuple('Stat', ['stat', 'base', 'gene', 'exp', 'calc'])

    def __init__(self, blob, encrypted=False):
        u"""Wraps a Pokémon save struct in a friendly object.

        If `encrypted` is True, the blob will be decrypted as though it were an
        on-disk save.  Otherwise, the blob is taken to be already decrypted and
        is left alone.

        `session` is an optional database session.
        """

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

        self.structure = pokemon_struct.parse(self.blob)

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
        database stuff.  Gotta call this before you use the database properties
        like `species`, etc.
        """
        self._session = session

        st = self.structure
        self._pokemon = session.query(tables.Pokemon).get(st.national_id)
        self._pokemon_form = session.query(tables.PokemonForm) \
            .with_parent(self._pokemon) \
            .filter_by(name=st.alternate_form) \
            .one()
        self._ability = self._session.query(tables.Ability).get(st.ability_id)

        growth_rate = self._pokemon.evolution_chain.growth_rate
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

        self._stats = []
        for pokemon_stat in self._pokemon.stats:
            structure_name = pokemon_stat.stat.name.lower().replace(' ', '_')
            gene = st.ivs['iv_' + structure_name]
            exp  = st['effort_' + structure_name]

            if pokemon_stat.stat.name == u'HP':
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
        else:
            pokeball_id = st.dppt_pokeball
        self._pokeball = session.query(tables.ItemGameIndex) \
            .filter_by(generation_id = 4, game_index = pokeball_id).one().item

        egg_loc_id = st.pt_egg_location_id or st.dp_egg_location_id
        met_loc_id = st.pt_met_location_id or st.dp_met_location_id

        self._egg_location = None
        if egg_loc_id:
            self._egg_location = session.query(tables.LocationGameIndex) \
                .filter_by(generation_id = 4, game_index = egg_loc_id).one().location

        self._met_location = session.query(tables.LocationGameIndex) \
            .filter_by(generation_id = 4, game_index = met_loc_id).one().location

    @property
    def species(self):
        # XXX forme!
        return self._pokemon

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
    def shiny_leaves(self):
        return (
            self.structure.shining_leaves.leaf1,
            self.structure.shining_leaves.leaf2,
            self.structure.shining_leaves.leaf3,
            self.structure.shining_leaves.leaf4,
            self.structure.shining_leaves.leaf5,
        )

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
