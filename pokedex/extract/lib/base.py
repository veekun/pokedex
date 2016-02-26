"""Base or helper classes used a lot for dealing with file formats.
"""
import io
import struct


class Substream:
    """Wraps a stream and pretends it starts at an offset other than 0.

    Partly implements the file interface.

    This type always seeks before reading, but doesn't do so afterwards, so
    interleaving reads with the underlying stream may not do what you want.
    """
    def __init__(self, stream, offset=0, length=-1):
        if isinstance(stream, Substream):
            self.stream = stream.stream
            self.offset = offset + stream.offset
        else:
            self.stream = stream
            self.offset = offset

        self.length = length
        self.pos = 0

    def __repr__(self):
        return "<{} of {} at {}>".format(
            type(self).__name__, self.stream, self.offset)

    def read(self, n=-1):
        self.stream.seek(self.offset + self.pos)
        if n < 0:
            n = self.length
        elif self.length >= 0 and n > self.length:
            n = self.length
        data = self.stream.read(n)
        self.pos += len(data)
        return data

    def seek(self, offset):
        offset = max(offset, 0)
        if self.length >= 0:
            offset = min(offset, self.length)
        self.stream.seek(self.offset + offset)
        self.pos = self.tell()

    def tell(self):
        return self.stream.tell() - self.offset

    def __len__(self):
        if self.length < 0:
            pos = self.stream.tell()
            self.stream.seek(0, io.SEEK_END)
            parent_length = self.stream.tell()
            self.stream.seek(pos)
            return parent_length - self.offset
        else:
            return self.length

    def peek(self, n):
        pos = self.stream.tell()
        self.stream.seek(self.offset + self.pos)
        data = self.stream.read(n)
        self.stream.seek(pos)
        return data

    def unpack(self, fmt):
        """Unpacks a struct format from the current position in the stream."""
        data = self.read(struct.calcsize(fmt))
        return struct.unpack(fmt, data)

    def slice(self, offset, length=-1):
        # TODO limit or warn if length is too long for this slice?
        return Substream(self, self.offset + offset, length)


class _ContainerFile:
    slices = ()

    def __len__(self):
        return len(self.slices)

    def __iter__(self):
        return iter(self.slices)

    def __getitem__(self, key):
        return self.slices[key]
