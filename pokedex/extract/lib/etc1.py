"""Parse ETC1, a terrible micro block-based image compression format.

Please enjoy the docs.
https://www.khronos.org/registry/gles/extensions/OES/OES_compressed_ETC1_RGB8_texture.txt
"""
import io
import itertools


three_bit_twos_complement = [0, 1, 2, 3, -4, -3, -2, -1]

etc1_modifier_tables = [
    ( 2,   8,  -2,   -8),
    ( 5,  17,  -5,  -17),
    ( 9,  29,  -9,  -29),
    (13,  42, -13,  -42),
    (18,  60, -18,  -60),
    (24,  80, -24,  -80),
    (33, 106, -33, -106),
    (47, 183, -47, -183),
]

def decode_etc1(data):
    # TODO sizes are hardcoded here
    f = io.BytesIO(data)
    f.read(0x80)
    outpixels = [[None] * 128 for _ in range(128)]
    for blocky in range(0, 128, 8):
        for blockx in range(0, 128, 8):
            for z in range(4):
                row = f.read(16)
                if not row:
                    raise RuntimeError

                alpha = row[:8]
                etc1 = int.from_bytes(row[8:], 'big')
                diffbit = row[12] & 2
                flipbit = row[12] & 1
                lopixelbits = int.from_bytes(row[8:10], 'little')
                hipixelbits = int.from_bytes(row[10:12], 'little')

                if diffbit:
                    red1 = row[15] >> 3
                    red2 = max(0, red1 + three_bit_twos_complement[row[15] & 0x7])
                    green1 = row[14] >> 3
                    green2 = max(0, green1 + three_bit_twos_complement[row[14] & 0x7])
                    blue1 = row[13] >> 3
                    blue2 = max(0, blue1 + three_bit_twos_complement[row[13] & 0x7])

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

                codeword1 = row[12] >> 5
                codeword2 = (row[12] >> 2) & 0x7
                table1 = etc1_modifier_tables[codeword1]
                table2 = etc1_modifier_tables[codeword2]

                def nybbles(b):
                    for byte in b:
                        yield (byte & 0xf) << 4
                        yield byte >> 4 << 4
                it = nybbles(alpha)

                for c in range(4):
                    for r in range(4):
                        x = blockx + c
                        y = blocky + r
                        if z in (1, 3):
                            x += 4
                        if z in (2, 3):
                            y += 4

                        if flipbit:
                            # Horizontal
                            whichblock = 1 if r < 2 else 2
                        else:
                            whichblock = 1 if c < 2 else 2
                        if whichblock == 1:
                            table = table1
                            base = base1
                        else:
                            table = table2
                            base = base2

                        pixelbit = c * 4 + r
                        idx = 2 * ((hipixelbits >> pixelbit) & 1) + ((lopixelbits >> pixelbit) & 1)
                        mod = table[idx]
                        color = tuple(min(255, max(0, b + mod)) for b in base) + (next(it),)
                        outpixels[y][x] = color

    return 128, 128, 4, None, outpixels
