import io
import itertools
import math
import struct

import attr
import construct as c

clim_header_struct = c.Struct(
    c.Const(b'FLIM'),  # TODO 'FLIM' in SUMO
    'endianness' / c.Const(c.Int16ul, 0xfeff),
    'header_length' / c.Const(c.Int16ul, 0x14),
    'version' / c.Int32ul,
    'file_size' / c.Int32ul,
    'blocks_ct' / c.Int32ul,
)
imag_header_struct = c.Struct(
    c.Const(b'imag'),
    'section_length' / c.Const(c.Int32ul, 0x10),
    'width' / c.Int16ul,
    'height' / c.Int16ul,
    #'format' / c.Int32ul,
    # TODO this seems to have been expanded into several things in SUMO
    #c.Enum(
    #    c.ULInt32('format'),
    #    L8=0,
    #    A8=1,
    #    LA4=2,
    #    LA8=3,
    #    HILO8=4,
    #    RGB565=5,
    #    RGB8=6,
    #    RGBA5551=7,
    #    RGBA4=8,
    #    RGBA8=9,
    #    ETC1=10,
    #    ETC1A4=11,
    #    L4=12,
    #    A4=13,
    #    #ETC1=19,
    #)
    'unknown' / c.Int16ul,
    'format' / c.Enum(
        c.Int8ul,
        L8=0,
        A8=1,
        LA4=2,
        LA8=3,
        HILO8=4,
        RGB565=5,
        RGB8=6,
        RGBA5551=7,
        RGBA4=8,
        RGBA8=9,
        ETC1=10,
        ETC1A4=11,
        L4=12,
        A4=13,
        #ETC1=19,
    ),
    # RGB565=5,
    # ETC1A4=11,
    'unknown2' / c.Int8ul,
)


# TODO probably move these to their own module, since they aren't just for
# CLIM.  pixel deshuffler, too.  (which should probably spit out pypng's native
# format)
COLOR_FORMATS = {}


@attr.s
class ColorFormat:
    name = attr.ib('name')
    decoder = attr.ib('decoder')
    bits_per_pixel = attr.ib('bits_per_pixel')
    bit_depth = attr.ib('bit_depth')
    alpha = attr.ib('alpha')

    def __call__(self, data):
        return self.decoder(data)

    def __iter__(self):
        # TODO back compat until i fix the below code
        return iter((self, self.bits_per_pixel, self.bit_depth))


def _register_color_decoder(name, *, bpp, depth, alpha):
    def register(f):
        COLOR_FORMATS[name] = ColorFormat(name, f, bpp, depth, alpha)
        return f
    return register


@_register_color_decoder('A4', bpp=0.5, depth=4, alpha=True)
def decode_A4(data):
    for a in data:
        a0 = a & 0xf
        a0 = (a0 << 4) | (a0 << 0)
        a1 = a >> 4
        a1 = (a1 << 4) | (a1 << 0)
        yield 0, 0, 0, a0
        yield 0, 0, 0, a1


@_register_color_decoder('A8', bpp=1, depth=8, alpha=True)
def decode_a8(data):
    for a in data:
        yield 0, 0, 0, a


@_register_color_decoder('L4', bpp=0.5, depth=4, alpha=False)
def decode_l4(data):
    for l in data:
        l0 = l & 0xf
        l0 = (l0 << 4) | (l0 << 0)
        l1 = l >> 4
        l1 = (l1 << 4) | (l1 << 0)
        yield l0, l0, l0
        yield l1, l1, l1


@_register_color_decoder('L8', bpp=1, depth=8, alpha=False)
def decode_l8(data):
    for l in data:
        yield l, l, l


@_register_color_decoder('LA4', bpp=1, depth=4, alpha=True)
def decode_la4(data):
    for la in data:
        l = la >> 4
        l = (l << 4) | (l << 0)
        a = (la >> 0) & 0xf
        a = (a << 4) | (a << 4)
        yield l, l, l, a


@_register_color_decoder('LA8', bpp=2, depth=8, alpha=True)
def decode_la8(data):
    for i in range(0, len(data), 2):
        a = data[i]
        l = data[i + 1]
        yield l, l, l, a


@_register_color_decoder('RGBA4', bpp=2, depth=4, alpha=True)
def decode_rgba4(data):
    # The idea is that every uint16 is a packed rrrrggggbbbbaaaa, but when
    # written out little-endian this becomes bbbbaaaarrrrgggg and there's just
    # no pretty way to deal with this
    for i in range(0, len(data), 2):
        ba = data[i]
        rg = data[i + 1]
        r = (((rg & 0xf0) >> 4) * 255 + 7) // 15
        g = (((rg & 0x0f) >> 0) * 255 + 7) // 15
        b = (((ba & 0xf0) >> 4) * 255 + 7) // 15
        a = (((ba & 0x0f) >> 0) * 255 + 7) // 15
        yield r, g, b, a


@_register_color_decoder('RGB8', bpp=3, depth=8, alpha=False)
def decode_rgb8(data):
    for i in range(0, len(data), 3):
        yield data[i:i + 3][::-1]


@_register_color_decoder('RGBA8', bpp=4, depth=8, alpha=True)
def decode_rgba8(data):
    for i in range(0, len(data), 4):
        yield data[i:i + 4][::-1]


# FIXME turns out the above just are these, so, ditch these
@_register_color_decoder('BGR8', bpp=3, depth=8, alpha=False)
def decode_bgr8(data):
    for i in range(0, len(data), 3):
        yield data[i:i + 3][::-1]


@_register_color_decoder('ABGR8', bpp=4, depth=8, alpha=True)
def decode_abgr8(data):
    for i in range(0, len(data), 4):
        yield data[i:i + 4][::-1]


@_register_color_decoder('RGBA5551', bpp=2, depth=5, alpha=True)
def decode_rgba5551(data, *, start=0, count=None):
    # I am extremely irritated that construct cannot parse this mess for me
    # rrrrrgggggbbbbba
    if count is None:
        end = len(data)
    else:
        end = start + count * 2

    for i in range(start, end, 2):
        datum = data[i] + data[i + 1] * 256
        # FIXME repeat rather than doing division
        r = (((datum >> 11) & 0x1f) * 255 + 15) // 31
        g = (((datum >> 6) & 0x1f) * 255 + 15) // 31
        b = (((datum >> 1) & 0x1f) * 255 + 15) // 31
        a = (datum & 0x1) * 255
        yield r, g, b, a


@_register_color_decoder('RGB565', bpp=2, depth=5, alpha=False)
def decode_rgb565(data, *, start=0, count=None):
    # FIXME i bet construct totally /can/ parse this mess for me
    if count is None:
        end = len(data)
    else:
        end = start + count * 2

    for i in range(start, end, 2):
        datum = data[i] + data[i + 1] * 256
        # FIXME repeat rather than doing division
        r = (((datum >> 11) & 0x1f) * 255 + 15) // 31
        g = (((datum >> 5) & 0x3f) * 255 + 31) // 63
        b = (((datum >> 0) & 0x1f) * 255 + 15) // 31
        yield r, g, b


@_register_color_decoder('RGB332', bpp=1, depth=2, alpha=False)
def decode_rgb332(data, *, start=0, count=None):
    if count is None:
        end = len(data)
    else:
        end = start + count

    for i in range(start, end):
        datum = data[i]
        r = (datum >> 5) & 0x7
        r = (r << 5) | (r << 2) | (r >> 1)
        g = (datum >> 2) & 0x7
        g = (g << 5) | (g << 2) | (g >> 1)
        b = (datum >> 0) & 0x7
        b = (b << 5) | (b << 2) | (b >> 1)
        yield r, g, b


_register_color_decoder('ETC1', bpp=0.5, depth=4, alpha=False)(None)
_register_color_decoder('ETC1A4', bpp=1, depth=4, alpha=True)(None)


del _register_color_decoder


def uncuddle_paletted_pixels(palette, data):
    if len(palette) <= 16:
        # Short palettes allow cramming two pixels into each byte
        return (
            idx
            for byte in data
            for idx in (byte >> 4, byte & 0x0f)
        )
    else:
        return data


def untile_pixels(raw_pixels, width, height, *, is_flim):
    """Unscramble pixels into plain old rows.

    The pixels are arranged in 8×8 tiles, and each tile is a third-
    iteration Z-order curve.

    Taken from: https://github.com/Zhorken/pokemon-x-y-icons/
    """

    # FIXME this is a wild guess, because i've seen a 4x4 image that this just
    # doesn't handle correctly, but the image is all white so i have no idea
    # what the right fix is -- there's a 4 x 0x78 in 0/7/9 though...
    if width < 8 or height < 8:
        pixels = []
        it = iter(raw_pixels)
        for r in range(height):
            pixels.append([])
            for c in range(width):
                pixels[-1].append(next(it))
        return pixels

    # Images are stored padded to powers of two
    stored_width = 2 ** math.ceil(math.log(width) / math.log(2))
    stored_height = 2 ** math.ceil(math.log(height) / math.log(2))
    num_pixels = stored_width * stored_height
    tile_width = (stored_width + 7) // 8
    tile_height = (stored_height + 7) // 8

    pixels = [
        [None for x in range(width)]
        for y in range(height)
    ]

    for n, pixel in enumerate(raw_pixels):
        if n >= num_pixels:
            break

        # Find the coordinates of the top-left corner of the current tile.
        # n.b. The image is eight tiles wide, and each tile is 8×8 pixels.
        tile_num = n // 64
        # FIXME i found a 4x4 FLIM that this fails for???
        if is_flim:
            # The FLIM format seems to pseudo-rotate the entire image to the
            # right, so tiles start in the bottom left and go up
            tile_y = (tile_height - 1 - (tile_num % tile_height)) * 8
            tile_x = tile_num // tile_height * 8
        else:
            # CLIM has the more conventional right-then-down order
            tile_y = tile_num // tile_width * 8
            tile_x = tile_num % tile_width * 8

        # Determine the pixel's coordinates within the tile
        # http://en.wikipedia.org/wiki/Z-order_curve#Coordinate_values
        within_tile = n % 64

        sub_x = (
            (within_tile & 0b000001) |
            (within_tile & 0b000100) >> 1 |
            (within_tile & 0b010000) >> 2
        )
        sub_y = (
            (within_tile & 0b000010) >> 1 |
            (within_tile & 0b001000) >> 2 |
            (within_tile & 0b100000) >> 3
        )

        if is_flim:
            # Individual tiles are also rotated.  Unrotate them
            sub_x, sub_y = sub_y, 7 - sub_x

        # Add up the pixel's coordinates within the whole image
        x = tile_x + sub_x
        y = tile_y + sub_y

        if x < width and y < height:
            pixels[y][x] = pixel

    return pixels


def decode_clim(data):
    file_format = data[-40:-36]
    if file_format == b'CLIM':
        is_flim = False
    elif file_format == b'FLIM':
        is_flim = True
    else:
        raise ValueError("Unknown image format {}".format(file_format))

    imag_header = imag_header_struct.parse(data[-20:])
    #if is_flim:
    #    # TODO SUMO hack; not sure how to get format out of this header
    #    imag_header.format = 'RGBA5551'

    if imag_header.format not in COLOR_FORMATS:
        raise ValueError(
            "don't know how to decode {} pixels".format(imag_header.format))
    color_format = COLOR_FORMATS[imag_header.format]

    mode, = struct.unpack_from('<H', data, 0)
    if mode == 2:
        # Paletted
        palette_length, = struct.unpack_from('<H', data, 2)
        palette = list(color_format.decoder(data, start=4, count=palette_length))
        data_start = 4 + palette_length * color_format.bits_per_pixel
        scrambled_pixels = uncuddle_paletted_pixels(palette, data[data_start:])
    elif imag_header.format == 'ETC1':
        # FIXME merge this decoder in (problem is it needs to know width +
        # height -- maybe i can move the pixel unscrambling out of it somehow?)
        from .etc1 import decode_etc1
        pixels = decode_etc1(b'\x00' * 0x80 + data, imag_header.width, imag_header.height, use_alpha=False, is_flim=True)[4]
        return DecodedImageData(
            imag_header.width, imag_header.height, color_format, None, pixels)
    elif imag_header.format == 'ETC1A4':
        # FIXME same
        from .etc1 import decode_etc1
        pixels = decode_etc1(b'\x00' * 0x80 + data, imag_header.width, imag_header.height, is_flim=True)[4]
        return DecodedImageData(
            imag_header.width, imag_header.height, color_format, None, pixels)
    else:
        palette = None
        scrambled_pixels = color_format.decoder(data)

    pixels = untile_pixels(
        scrambled_pixels,
        imag_header.width,
        imag_header.height,
        is_flim=is_flim,
    )
    return DecodedImageData(
        imag_header.width, imag_header.height, color_format, palette, pixels)


class DecodedImageData:
    def __init__(self, width, height, color_format, palette, pixels):
        self.width = width
        self.height = height
        self.color_format = color_format
        self.palette = palette
        self.pixels = pixels

    def __iter__(self):
        return iter((self.width, self.height, self.color_format.bit_depth, self.palette, self.pixels))

    def mirror(self):
        for row in self.pixels:
            row.reverse()

    def write_to_png(self, f):
        """Write the results of ``decode_clim`` to a file object."""
        import png

        writer_kwargs = dict(width=self.width, height=self.height)
        if self.palette:
            writer_kwargs['palette'] = self.palette
        if self.color_format.alpha:
            # TODO do i really only need alpha=True if there's no palette?
            writer_kwargs['alpha'] = True
        writer = png.Writer(**writer_kwargs)

        # For a paletted image, I want to preserve Zhorken's good idea of
        # indicating the original bit depth with an sBIT chunk.  But PyPNG can't do
        # that directly, so instead I have to do some nonsense.
        # FIXME should probably just do that for everything?
        if self.palette:
            buf = io.BytesIO()
            writer.write(buf, self.pixels)

            # Read the PNG as chunks, and manually add an sBIT chunk
            buf.seek(0)
            png_reader = png.Reader(buf)
            chunks = list(png_reader.chunks())
            sbit = bytes([self.color_format.bit_depth] * 3)
            chunks.insert(1, ('sBIT', sbit))

            # Now write the chunks to the file
            png.write_chunks(f, chunks)

        else:
            # Otherwise, it's...  almost straightforward.
            writer.write(f, (itertools.chain(*row) for row in self.pixels))
