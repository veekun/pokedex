"""Parse ETC1, a terrible 4x4 block-based image compression format.

Please enjoy the docs.
https://www.khronos.org/registry/gles/extensions/OES/OES_compressed_ETC1_RGB8_texture.txt

The format supported here isn't actually ETC1, but a Nintendo-flavored variant
that decodes four 4x4 blocks one 8x8 block at a time, because of course it is.
(I believe the 3DS operates with 8x8 tiles, so this does make some sense.)
"""
import io

# Easier than doing math
THREE_BIT_TWOS_COMPLEMENT = [0, 1, 2, 3, -4, -3, -2, -1]

# Table of magic numbers.  Note that the columns aren't in the same order as
# they appear in the docs, because the order of columns in the docs doesn't
# match how the format actually picks them!
ETC1_MODIFIER_TABLES = [
    (2,  8,   -2,  -8),
    (5,  17,  -5,  -17),
    (9,  29,  -9,  -29),
    (13, 42,  -13, -42),
    (18, 60,  -18, -60),
    (24, 80,  -24, -80),
    (33, 106, -33, -106),
    (47, 183, -47, -183),
]


def iter_alpha_nybbles(b):
    """Iterates nybbles from a string of bytes, in little-endian order."""
    for byte in b:
        nybble = byte & 0x0f
        yield (nybble << 4) | nybble
        nybble = byte >> 4
        yield (nybble << 4) | nybble


def clamp_to_byte(n):
    return max(0, min(255, n))


def decode_etc1(data):
    # TODO sizes are hardcoded here
    width = 128
    height = 128

    # TODO this seems a little redundant; could just ask for a stream
    f = io.BytesIO(data)
    # Skip header
    f.read(0x80)

    outpixels = [[None] * width for _ in range(height)]
    # ETC1 encodes as 4x4 blocks.  Normal ETC1 arranges them in English reading
    # order, right and down.  This Nintendo variant groups them as 8x8
    # superblocks, where the four blocks in each superblock are themselves
    # arranged right and down.  So we read block offsets 8 at a time, and 'z'
    # is our current position within a superblock.
    # TODO this may do the wrong thing if width/height is not divisible by 8
    for blocky in range(0, height, 8):
        for blockx in range(0, width, 8):
            for z in range(4):
                row = f.read(16)
                if not row:
                    raise EOFError

                # Each block is encoded as 16 bytes.  The first 8 are a 4-bit
                # alpha channel; the latter 8 are color data and flags.
                alpha = row[:8]
                # A block is encoded in two halves.  This bit determines
                # whether the split is vertical (0) or horizontal (1).
                flipbit = row[12] & 1
                # Each half-block has a base color, and its palette is computed
                # relative to that color.  If this bit is 0, the halves use
                # "individual" mode, where each gets its own 4-bit base color;
                # if 1, use "differential" mode, where the first half has a
                # 5-bit base color and the other is given by a 3-bit offset.
                diffbit = row[12] & 2
                # Each half-block also uses one of the predefined tables of
                # four modifiers listed above.  There are eight such tables,
                # thus three bits to pick one.
                codeword1 = row[12] >> 5
                codeword2 = (row[12] >> 2) & 0x7
                table1 = ETC1_MODIFIER_TABLES[codeword1]
                table2 = ETC1_MODIFIER_TABLES[codeword2]
                # Finally, each pixel uses one each of these bits to get an
                # index into the modifier table, then adds that modifier to the
                # base color.  (Note that no pixel can be the base color.)
                lopixelbits = int.from_bytes(row[8:10], 'little')
                hipixelbits = int.from_bytes(row[10:12], 'little')

                # Read the base color for each half-block, depending on mode
                if diffbit:
                    # Differential mode: first half uses 5-bit color, second
                    # half is relative to it
                    red1 = row[15] >> 3
                    green1 = row[14] >> 3
                    blue1 = row[13] >> 3
                    red2 = clamp_to_byte(
                        red1 + THREE_BIT_TWOS_COMPLEMENT[row[15] & 0x7])
                    green2 = clamp_to_byte(
                        green1 + THREE_BIT_TWOS_COMPLEMENT[row[14] & 0x7])
                    blue2 = clamp_to_byte(
                        blue1 + THREE_BIT_TWOS_COMPLEMENT[row[13] & 0x7])

                    red1 = (red1 << 3) | (red1 >> 2)
                    green1 = (green1 << 3) | (green1 >> 2)
                    blue1 = (blue1 << 3) | (blue1 >> 2)
                    red2 = (red2 << 3) | (red2 >> 2)
                    green2 = (green2 << 3) | (green2 >> 2)
                    blue2 = (blue2 << 3) | (blue2 >> 2)
                else:
                    red1 = row[15] >> 4
                    red2 = row[15] & 0xf
                    green1 = row[14] >> 4
                    green2 = row[14] & 0xf
                    blue1 = row[13] >> 4
                    blue2 = row[13] & 0xf

                    red1 = (red1 << 4) | red1
                    green1 = (green1 << 4) | green1
                    blue1 = (blue1 << 4) | blue1
                    red2 = (red2 << 4) | red2
                    green2 = (green2 << 4) | green2
                    blue2 = (blue2 << 4) | blue2
                base1 = red1, green1, blue1
                base2 = red2, green2, blue2

                # Now deal with individual pixels
                it = iter_alpha_nybbles(alpha)
                for c in range(4):
                    for r in range(4):
                        x = blockx + c
                        y = blocky + r
                        if z in (1, 3):
                            x += 4
                        if z in (2, 3):
                            y += 4

                        if (flipbit and r < 2) or (not flipbit and c < 2):
                            table = table1
                            base = base1
                        else:
                            table = table2
                            base = base2

                        pixelbit = c * 4 + r
                        hibit = (hipixelbits >> pixelbit) & 0x1
                        lobit = (lopixelbits >> pixelbit) & 0x1
                        mod = table[hibit * 2 + lobit]
                        color = tuple(clamp_to_byte(b + mod) for b in base)
                        color += (next(it),)
                        outpixels[y][x] = color

    # 4 is the bit depth; None is the palette
    return width, height, 4, None, outpixels
