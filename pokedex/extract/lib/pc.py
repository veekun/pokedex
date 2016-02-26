"""Allegedly stands for 'Pokémon Container'.  Completely generic, dead-simple
container format.
"""
from .base import _ContainerFile, Substream


class PokemonContainerFile(_ContainerFile):
    magic = b'PC'

    def __init__(self, stream):
        self.stream = stream = Substream(stream)

        magic, entry_ct = stream.unpack('<2sH')
        assert magic == b'PC'

        self.slices = []
        for _ in range(entry_ct):
            start, end = stream.unpack('<LL')
            self.slices.append(self.stream.slice(start, end - start))
