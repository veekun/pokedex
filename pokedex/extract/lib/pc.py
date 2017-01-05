"""Allegedly stands for 'Pokémon Container'.  Completely generic, dead-simple
container format.
"""
from .base import _ContainerFile, Substream


class PokemonContainerFile(_ContainerFile):
    magic = b'PC'

    def __init__(self, stream):
        self.stream = stream = Substream(stream)

        magic, entry_ct = stream.unpack('<2sH')
        assert magic in (b'PC', b'PS', b'BL')

        # Offsets are "A B C ...", where entry 0 ranges from A to B, entry 1
        # from B to C, etc.
        offsets = stream.unpack('<{}L'.format(entry_ct + 1))
        self.slices = []
        for i in range(entry_ct):
            start, end = offsets[i:i + 2]
            self.slices.append(self.stream.slice(start, end - start))
