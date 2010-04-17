# encoding: utf8
u"""
Handles reading and encryption/decryption of Pokémon save file data.

See: http://projectpokemon.org/wiki/Pokemon_NDS_Structure

Kudos to LordLandon for his pkmlib.py, from which this module was originally
derived.
"""

import itertools, struct

def pokemon_prng(seed):
    u"""Creates a generator that simulates the main Pokémon PRNG."""
    while True:
        seed = 0x41C64E6D * seed + 0x6073
        seed &= 0xFFFFFFFF
        yield seed >> 16


class PokemonSave(object):
    u"""Represents an individual Pokémon, from the game's point of view.

    Handles translating between the on-disk encrypted form, the in-RAM blob
    (also used by pokesav), and something vaguely intelligible.

    XXX: Okay, well, right now it's just encryption and decryption.  But, you
    know.
    """

    def __init__(self, blob, encrypted=False):
        u"""Wraps a Pokémon save struct in a friendly object.

        If `encrypted` is True, the blob will be decrypted as though it were an
        on-disk save.  Otherwise, the blob is taken to be already decrypted and
        is left alone.
        """

        # XXX Sometime this should have an abstract internal representation.
        # For now, just store the decrypted version

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


    ### Utility methods

    shuffle_orders = list( itertools.permutations(range(4)) )

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
