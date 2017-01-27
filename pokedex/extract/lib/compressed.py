"""Substreams that can handle compressed data."""
import struct

from .base import Substream


class DecompressionError(ValueError):
    pass


class CompressedStream:
    def __init__(self, stream):
        self.stream = stream
        self.data = bytearray()
        self.pos = 0
        self._read_header()

    def __len__(self):
        return self.length

    def read(self, n=-1):
        maxread = self.length - self.pos
        if n < 0 or 0 <= maxread < n:
            n = maxread
        self._ensure_bytes(self.pos + n)
        data = self.data[self.pos:self.pos + n]
        self.pos += n
        return data

    def seek(self, offset, whence=0):
        if whence == 1:
            offset += self.pos
        elif whence == 2:
            offset += self.length
        offset = max(offset, 0)
        if self.length >= 0:
            offset = min(offset, self.length)
        self.pos = offset

    def tell(self):
        return self.pos

    def peek(self, n):
        pos = self.tell()
        maxread = self.length - self.pos
        data = self.read(min(maxread, n))
        self.seek(pos)
        return data

    def unpack(self, fmt):
        """Unpacks a struct format from the current position in the stream."""
        data = self.read(struct.calcsize(fmt))
        return struct.unpack(fmt, data)

    def slice(self, offset, length=-1):
        # TODO limit or warn if length is too long for this slice?
        raise RuntimeError
        return Substream(self, offset, length)


def _bits(byte):
    return ((byte >> 7) & 1,
            (byte >> 6) & 1,
            (byte >> 5) & 1,
            (byte >> 4) & 1,
            (byte >> 3) & 1,
            (byte >> 2) & 1,
            (byte >> 1) & 1,
            (byte) & 1)


class LZSS11CompressedStream(CompressedStream):
    def _read_header(self):
        header = self.stream.read(4)
        self.compressed_pos = self.stream.tell()
        assert header[0] == 0x11
        self.length, = struct.unpack('<L', header[1:] + b'\x00')

    def _ensure_bytes(self, needed):
        self.stream.seek(self.compressed_pos)

        def writebyte(b):
            self.data.append(b)

        def readbyte():
            return self.stream.read(1)[0]

        def copybyte():
            writebyte(readbyte())

        while len(self.data) < needed:
            byte = self.stream.read(1)
            if not byte:
                break
            b, = byte
            flags = _bits(b)
            for flag in flags:
                if flag == 0:
                    copybyte()
                elif flag == 1:
                    b = readbyte()
                    indicator = b >> 4

                    if indicator == 0:
                        # 8 bit count, 12 bit disp
                        # indicator is 0, don't need to mask b
                        count = (b << 4)
                        b = readbyte()
                        count += b >> 4
                        count += 0x11
                    elif indicator == 1:
                        # 16 bit count, 12 bit disp
                        count = ((b & 0xf) << 12) + (readbyte() << 4)
                        b = readbyte()
                        count += b >> 4
                        count += 0x111
                    else:
                        # indicator is count (4 bits), 12 bit disp
                        count = indicator
                        count += 1

                    disp = ((b & 0xf) << 8) + readbyte()
                    disp += 1

                    try:
                        for _ in range(count):
                            writebyte(self.data[-disp])
                    except IndexError:
                        # FIXME `it` no longer exists, need len of substream
                        raise DecompressionError(count, disp, len(self.data), len(self.stream), self.compressed_pos, self.stream.tell())
                else:
                    raise DecompressionError(flag)

                if needed <= len(self.data):
                    break

        self.compressed_pos = self.stream.tell()

        # FIXME check this once we hit eof
        #if len(self.data) != decompressed_size:
        #    raise DecompressionError(
        #        "decompressed size does not match the expected size")
