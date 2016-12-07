"""Support for reading the GARC generic container format used in the 3DS
filesystem.

Based on code by Zhorken: https://github.com/Zhorken/pokemon-x-y-icons
and Kaphotics: https://github.com/kwsch/GARCTool
"""
from collections import Counter
from io import BytesIO
from pathlib import Path
import struct
import sys

import construct as c

from . import lzss3
from .base import _ContainerFile, Substream
from .pc import PokemonContainerFile


def count_bits(n):
    c = 0
    while n:
        c += n & 1
        n >>= 1
    return c


garc_header_struct = c.Struct(
    'garc_header',
    c.Magic(b'CRAG'),
    c.ULInt32('header_size'),  # 28 in XY, 36 in SUMO
    c.Const(c.ULInt16('byte_order'), 0xfeff),
    c.ULInt16('mystery1'),  # 0x0400 in XY, 0x0600 in SUMO
    #c.Const(c.ULInt32('chunks_ct'), 4),
    c.ULInt32('chunks_ct'),
    c.ULInt32('data_offset'),
    c.ULInt32('garc_length'),
    c.ULInt32('last_length'),
    c.Field('unknown_sumo_stuff', lambda ctx: ctx.header_size - 28),
)
fato_header_struct = c.Struct(
    'fato_header',
    c.Magic(b'OTAF'),
    c.ULInt32('header_size'),
    c.ULInt16('count'),
    c.Const(c.ULInt16('padding'), 0xffff),
    c.Array(
        lambda ctx: ctx.count,
        c.ULInt32('fatb_offsets'),
    ),
)
fatb_header_struct = c.Struct(
    'fatb_header',
    c.Magic(b'BTAF'),
    c.ULInt32('fatb_length'),
    c.ULInt32('count'),
)


class GARCFile(_ContainerFile):
    def __init__(self, stream):
        self.stream = stream = Substream(stream)

        garc_header = garc_header_struct.parse_stream(self.stream)
        # FATO (file allocation table...  offsets?)
        fato_header = fato_header_struct.parse_stream(self.stream)
        # FATB (file allocation table)
        fatb_header = fatb_header_struct.parse_stream(self.stream)

        fatb_start = garc_header.header_size + fato_header.header_size
        assert stream.tell() == fatb_start + 12

        self.slices = []
        for i, offset in enumerate(fato_header.fatb_offsets):
            stream.seek(fatb_start + offset + 12)

            slices = []
            bits, = struct.unpack('<L', stream.read(4))
            while bits:
                if bits & 1:
                    start, end, length = struct.unpack('<3L', stream.read(12))
                    slices.append((garc_header.data_offset + start, end - start))
                bits >>= 1

            self.slices.append(GARCEntry(stream, slices))

        # FIMB
        stream.seek(fatb_start + fatb_header.fatb_length)
        magic, fimb_header_length, fimb_length = struct.unpack(
            '<4s2L', stream.read(12))
        assert magic == b'BMIF'
        assert fimb_header_length == 0xC


class GARCEntry(object):
    def __init__(self, stream, slices):
        self.stream = stream
        self.slices = slices

    def __getitem__(self, i):
        start, length = self.slices[i]
        ss = self.stream.slice(start, length)
        if ss.peek(1) in [b'\x10', b'\x11']:
            # XXX this sucks but there's no real way to know for sure whether
            # data is compressed or not.  maybe just bake this into the caller
            # and let them deal with it, same way we do with text decoding?
            # TODO it would be nice if this could be done lazily for 'inspect'
            # purposes, since the first four bytes are enough to tell you the
            # size
            try:
                data = lzss3.decompress_bytes(ss.read())
            except Exception:
                ss.seek(0)
            else:
                return Substream(BytesIO(data))
        return ss

    def __len__(self):
        return len(self.slices)


XY_CHAR_MAP = {
    0x307f: 0x202f,  # nbsp
    0xe08d: 0x2026,  # ellipsis
    0xe08e: 0x2642,  # female sign
    0xe08f: 0x2640,  # male sign
}

XY_VAR_NAMES = {
    0xff00: "COLOR",
    0x0100: "TRNAME",
    0x0101: "PKNAME",
    0x0102: "PKNICK",
    0x0103: "TYPE",
    0x0105: "LOCATION",
    0x0106: "ABILITY",
    0x0107: "MOVE",
    0x0108: "ITEM1",
    0x0109: "ITEM2",
    0x010a: "sTRBAG",
    0x010b: "BOX",
    0x010d: "EVSTAT",
    0x0110: "OPOWER",
    0x0127: "RIBBON",
    0x0134: "MIINAME",
    0x013e: "WEATHER",
    0x0189: "TRNICK",
    0x018a: "1stchrTR",
    0x018b: "SHOUTOUT",
    0x018e: "BERRY",
    0x018f: "REMFEEL",
    0x0190: "REMQUAL",
    0x0191: "WEBSITE",
    0x019c: "CHOICECOS",
    0x01a1: "GSYNCID",
    0x0192: "PRVIDSAY",
    0x0193: "BTLTEST",
    0x0195: "GENLOC",
    0x0199: "CHOICEFOOD",
    0x019a: "HOTELITEM",
    0x019b: "TAXISTOP",
    0x019f: "MAISTITLE",
    0x1000: "ITEMPLUR0",
    0x1001: "ITEMPLUR1",
    0x1100: "GENDBR",
    0x1101: "NUMBRNCH",
    0x1302: "iCOLOR2",
    0x1303: "iCOLOR3",
    0x0200: "NUM1",
    0x0201: "NUM2",
    0x0202: "NUM3",
    0x0203: "NUM4",
    0x0204: "NUM5",
    0x0205: "NUM6",
    0x0206: "NUM7",
    0x0207: "NUM8",
    0x0208: "NUM9",
}


def _xy_inner_keygen(key):
    while True:
        yield key
        key = ((key << 3) | (key >> 13)) & 0xffff


def _xy_outer_keygen():
    key = 0x7c89
    while True:
        yield _xy_inner_keygen(key)
        key = (key + 0x2983) & 0xffff


def decrypt_xy_text(data):
    text_sections, lines, length, initial_key, section_data = struct.unpack_from(
        '<HHLLl', data)

    outer_keygen = _xy_outer_keygen()
    ret = []

    for i in range(lines):
        keygen = next(outer_keygen)
        s = []
        offset, length = struct.unpack_from('<lh', data, i * 8 + section_data + 4)
        offset += section_data
        start = offset
        characters = []
        for ech in struct.unpack_from("<{}H".format(length), data, offset):
            characters.append(ech ^ next(keygen))

        chiter = iter(characters)
        for c in chiter:
            if c == 0:
                break
            elif c == 0x10:
                # Goofy variable thing
                length = next(chiter)
                typ = next(chiter)
                if typ == 0xbe00:
                    # Pause, then scroll
                    s.append('\r')
                elif typ == 0xbe01:
                    # Pause, then clear screen
                    s.append('\f')
                elif typ == 0xbe02:
                    # Pause for some amount of time?
                    s.append("{{pause:{}}}".format(next(chiter)))
                elif typ == 0xbdff:
                    # Empty text line?  Includes line number, maybe for finding unused lines?
                    s.append("{{blank:{}}}".format(next(chiter)))
                else:
                    s.append("{{{}:{}}}".format(
                        XY_VAR_NAMES.get(typ, "{:04x}".format(typ)),
                        ','.join(str(next(chiter)) for _ in range(length - 1)),
                    ))
            else:
                s.append(chr(XY_CHAR_MAP.get(c, c)))

        ret.append(''.join(s))

    return ret


def main(args):
    parser = make_arg_parser()
    args = parser.parse_args(args)
    args.cb(args)


def detect_subfile_type(subfile):
    header = subfile.peek(16)
    magic = header[0:4]

    # CLIM
    if magic.isalnum():
        return magic.decode('ascii')

    # PC
    if magic[:2].isalnum():
        return magic[:2].decode('ascii')

    # Encrypted X/Y text?
    if len(header) >= 16:
        text_length = int.from_bytes(header[4:8], 'little')
        header_length = int.from_bytes(header[12:16], 'little')
        if len(subfile) == text_length + header_length:
            return 'gen 6 text'

    return None


def do_inspect(args):
    root = Path(args.path)
    if root.is_dir():
        for path in sorted(root.glob('**/*')):
            if path.is_dir():
                continue

            shortname = str(path.relative_to(root))
            if len(shortname) > 12:
                shortname = '...' + shortname[-9:]
            stat = path.stat()
            print("{:>12s}  {:>10d}  ".format(shortname, stat.st_size), end='')
            if stat.st_size == 0:
                print("empty file")
                continue

            with path.open('rb') as f:
                try:
                    garc = GARCFile(f)
                except Exception as exc:
                    print("{}: {}".format(type(exc).__name__, exc))
                    continue

                total_subfiles = 0
                magic_ctr = Counter()
                size_ctr = Counter()
                for i, topfile in enumerate(garc):
                    for j, subfile in enumerate(topfile):
                        total_subfiles += 1
                        size_ctr[len(subfile)] += 1
                        magic_ctr[detect_subfile_type(subfile)] += 1

                print("{} subfiles".format(total_subfiles), end='')
                if total_subfiles > len(garc):
                    print("  (some nested)")
                else:
                    print()

                cutoff = max(total_subfiles // 10, 2)
                for magic, ct in magic_ctr.most_common():
                    if ct < cutoff:
                        break
                    print(" " * 24, "{:4d} x {:>9s}".format(ct, magic or 'unknown'))
                for size, ct in size_ctr.most_common():
                    if ct < cutoff:
                        break
                    print(" " * 24, "{:4d} x {:9d}".format(ct, size))


        return

    with open(args.path, 'rb') as f:
        garc = GARCFile(f)
        for i, topfile in enumerate(garc):
            for j, subfile in enumerate(topfile):
                print("{:4d}/{:<4d}  {:7d}B".format(i, j, len(subfile)), end='')
                magic = detect_subfile_type(subfile)
                if magic == 'PC':
                    print(" -- appears to be a PC file (generic container)")
                    pcfile = PokemonContainerFile(subfile)
                    for k, entry in enumerate(pcfile):
                        print('       ', repr(entry.read(50)))
                elif magic == 'gen 6 text':
                    # TODO turn this into a generator so it doesn't have to
                    # parse the whole thing?  need length though
                    texts = decrypt_xy_text(subfile.read())
                    print(" -- X/Y text, {} entries: {!r}".format(len(texts), texts[:5]), texts[-5:])
                else:
                    print('', repr(subfile.read(50)))


def do_extract(args):
    with open(args.path, 'rb') as f:
        garc = GARCFile(f)
        # TODO shouldn't path really be a directory, so you can mass-extract everything?  do i want to do that ever?
        # TODO actually respect mode, fileno, entryno
        for i, topfile in enumerate(garc):
            # TODO i guess this should be a list, or??
            if args.fileno is not all and args.fileno != i:
                continue
            for j, subfile in enumerate(topfile):
                # TODO auto-detect extension, maybe?  depending on mode?
                outfile = Path("{}-{}-{}".format(args.out, i, j))
                with outfile.open('wb') as g:
                    # TODO should use copyfileobj
                    g.write(subfile.read())
                print("wrote", outfile)


def make_arg_parser():
    from argparse import ArgumentParser
    p = ArgumentParser()
    sp = p.add_subparsers(metavar='command')

    inspect_p = sp.add_parser('inspect', help='examine a particular file')
    inspect_p.set_defaults(cb=do_inspect)
    inspect_p.add_argument('path', help='relative path to a game file')
    inspect_p.add_argument('mode', nargs='?', default='shorthex')
    inspect_p.add_argument('fileno', nargs='?', default=all)
    inspect_p.add_argument('entryno', nargs='?', default=all)

    extract_p = sp.add_parser('extract', help='extract contents of a file')
    extract_p.set_defaults(cb=do_extract)
    extract_p.add_argument('path', help='relative path to a game file')
    extract_p.add_argument('out', help='filename to use for extraction')
    extract_p.add_argument('mode', nargs='?', default='raw')
    extract_p.add_argument('fileno', nargs='?', default=all)
    extract_p.add_argument('entryno', nargs='?', default=all)

    return p


if __name__ == '__main__':
    main(sys.argv[1:])
