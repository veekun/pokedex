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
    c.Const(b'CRAG'),
    'header_size' / c.Int32ul,  # 28 in XY, 36 in SUMO
    'byte_order' / c.Const(c.Int16ul, 0xfeff),
    'mystery1' / c.Int16ul,  # 0x0400 in XY, 0x0600 in SUMO
    #c.Const(c.ULInt32('chunks_ct'), 4),
    'chunks_ct' / c.Int32ul,
    'data_offset' / c.Int32ul,
    'garc_length' / c.Int32ul,
    'last_length' / c.Int32ul,
    'unknown_sumo_stuff' / c.Bytes(lambda ctx: ctx.header_size - 28),
)
fato_header_struct = c.Struct(
    c.Const(b'OTAF'),
    'header_size' / c.Int32ul,
    'count' / c.Int16ul,
    c.Const(c.Int16ul, 0xffff),
    'fatb_offsets' / c.Array(c.this.count, c.Int32ul),
)
fatb_header_struct = c.Struct(
    c.Const(b'BTAF'),
    'fatb_length' / c.Int32ul,
    'count' / c.Int32ul,
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
        peek = ss.peek(1)
        if peek == b'\x11' and length >= 128:
            from .compressed import DecompressionError, LZSS11CompressedStream
            decompressor = LZSS11CompressedStream(ss)
            try:
                # TODO this sucks, remove it i guess
                decompressor.peek(2088)
            except DecompressionError:
                ss.seek(0)
                return ss
            else:
                return decompressor
        elif ss.peek(1) in b'\x10\x11' and length >= 128:
            # XXX this sucks but there's no real way to know for sure whether
            # data is compressed or not.  maybe just bake this into the caller
            # and let them deal with it, same way we do with text decoding?
            # TODO it would be nice if this could be done lazily for 'inspect'
            # purposes, since the first four bytes are enough to tell you the
            # size
            # FIXME make this work even for red herrings, maybe by finishing it
            # up and doing a trial decompression of the first x bytes
            #return CompressedStream(ss)
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
    0xe07f: 0x202f,  # nbsp
    0xe08d: 0x2026,  # ellipsis
    0xe08e: 0x2642,  # female sign
    0xe08f: 0x2640,  # male sign
}

# For whatever reason, the Chinese Pokémon names in Sun and Moon use a set of
# PUA characters starting at U+E800.  No other Chinese text does this.
# The following table was reverse-engineered from Bulbapedia's set of names,
# with some manual fixes.  It applies without conflicts, but I can't
# /guarantee/ its correctness.
XY_CHAR_MAP.update((0xe800 + i, ord(char)) for (i, char) in enumerate(
    # Perhaps interesting: these appear to be the same set of characters in two
    # scripts, but many of them are written the same way in both scripts, and
    # they still get two encodings.  The names must have been encoded in two
    # separate passes.

    # Simplified
    "蛋妙蛙种子草花小火龙恐喷杰尼龟卡咪水箭绿毛虫铁甲蛹巴大蝶独角壳针蜂波比鸟拉达烈雀"
    "嘴阿柏蛇怪皮丘雷穿山鼠王多兰娜后朗力诺可西六尾九胖丁超音蝠走路臭霸派斯特球摩鲁蛾"
    "地三喵猫老鸭哥猴暴蒂狗风速蚊香蝌蚪君泳士凯勇基胡腕豪喇叭芽口呆食玛瑙母毒刺拳石隆"
    "岩马焰兽磁合一葱嘟利海狮白泥舌贝鬼通耿催眠貘引梦人钳蟹巨霹雳电顽弹椰树嘎啦飞腿郎"
    "快头瓦双犀牛钻吉蔓藤袋墨金鱼星宝魔墙偶天螳螂迷唇姐击罗肯泰鲤普百变伊布边菊化盔镰"
    "刀翼急冻闪你哈克幻叶月桂竺葵锯鳄蓝立咕夜鹰芭瓢安圆丝蛛叉字灯笼古然咩羊茸美丽露才"
    "皇毽棉长手向日蜻蜓乌沼太阳亮黑暗鸦妖未知图腾果翁麒麟奇榛佛托土弟蝎钢千壶赫狃熊圈"
    "熔蜗猪珊瑚炮章桶信使翅戴加象顿２惊鹿犬无畏战舞娃奶罐幸福公炎帝幼沙班洛亚凤时木守"
    "宫森林蜥蜴稚鸡壮躍狼纹直冲茧狩猎盾粉莲童帽乐河橡实鼻狡猾傲骨燕鸥莉奈朵溜糖雨蘑菇"
    "斗笠懒獭过动猿请假居忍面者脱妞吼爆幕下掌朝北优雅勾魂眼那恰姆落正拍負萤甜蔷薇溶吞"
    "牙鲨鲸驼煤炭跳噗晃斑颚蚁漠仙歌青绵七夕鼬斩饭匙鰍鲶虾兵螯秤念触摇篮羽丑纳飘浮泡隐"
    "怨影诅咒巡灵彷徨热带铃勃梭雪冰护豹珍珠樱空棘爱心哑属艾欧盖固坐祈代希苗台猛曼拿儿"
    "狸法师箱蟀勒伦琴含羞苞槌城结贵妇绅蜜女帕兹潜兔随卷耳魅东施铛响坦铜镜钟盆聒噪陆尖"
    "咬不良骷荧光霓虹自舔狂远Ｚ由卢席恩骑色霏莱谢米尔宙提主暖炒武刃丸剑探步哨约扒酷冷"
    "蚀豆鸽高雉幔庞滚蝙螺钉差搬运匠修建蟾蜍投摔打包保足蜈蚣车轮精根裙野蛮鲈混流氓红倒"
    "狒殿滑巾征哭具死神棺原肋始祖破灰尘索沫栗德单卵细胞造鹅倍四季萌哎呀败轻蜘坚齿组麻"
    "鳗宇烛幽晶斧嚏几何敏捷功夫父赤驹劈司令炸雄秃丫首恶燃烧毕云酋迪耶塔赛里狐呱贺掘彩"
    "蓓洁能鞘芳芙妮好鱿贼脚铠垃藻臂枪伞咚碎黏钥朽南瓜嗡哲裴格枭狙射炽咆哮虎漾壬笃啄铳"
    "少强锹农胜虻鬃弱坏驴仔重挽滴伪睡罩盗着竹疗环智挥猩掷胆噬堡爷参性：银伴陨枕戈谜拟"
    "Ｑ磨舵鳞杖璞・鸣哞鳍科莫迦虛吾肌费束辉纸御机夏"

    # Traditional
    # Perhaps also interesting: the Ｑ near the end of this block goes unused.
    # The Ｑ in Mimikyu's name is left unencoded in traditional Chinese (but
    # not in simplified).
    "蛋妙蛙種子草花小火龍恐噴傑尼龜卡咪水箭綠毛蟲鐵甲蛹巴大蝶獨角殼針蜂波比鳥拉達烈雀"
    "嘴阿柏蛇怪皮丘雷穿山鼠王多蘭娜后朗力諾可西六尾九胖丁超音蝠走路臭霸派斯特球摩魯蛾"
    "地三喵貓老鴨哥猴爆蒂狗風速蚊香蝌蚪君泳士凱勇基胡腕豪喇叭芽口呆食瑪瑙母毒刺拳石隆"
    "岩馬焰獸磁合一蔥嘟利海獅白泥舌貝鬼通耿催眠貘引夢人鉗蟹巨霹靂電頑彈椰樹嘎啦飛腿郎"
    "快頭瓦雙犀牛鑽吉蔓藤袋墨金魚星寶魔牆偶天螳螂迷唇姐擊羅肯泰鯉暴普百變伊布邊菊化盔"
    "鐮刀翼急凍閃你哈克幻葉月桂竺葵鋸鱷藍立咕夜鷹芭瓢安圓絲蛛叉字燈籠古然咩羊茸美麗露"
    "才皇毽棉長手向日蜻蜓烏沼太陽亮黑暗鴉妖未知圖騰果翁麒麟奇榛佛托土弟蠍鋼千壺赫狃熊"
    "圈熔蝸豬珊瑚砲章桶信使翅戴加象頓２驚鹿犬無畏戰舞娃奶罐幸福公炎帝幼沙班洛亞鳳時木"
    "守宮森林蜥蜴稚雞壯躍狼紋直衝繭狩獵盾粉蓮童帽樂河橡實鼻狡猾傲骨燕鷗莉奈朵溜糖雨蘑"
    "菇斗笠懶獺過動猿請假居忍面者脫妞吼幕下掌朝北優雅勾魂眼那恰姆落正拍負螢甜薔薇溶吞"
    "牙鯊鯨駝煤炭跳噗晃斑顎蟻漠仙歌青綿七夕鼬斬飯匙鰍鯰蝦兵螯秤念觸搖籃羽醜納飄浮泡隱"
    "怨影詛咒巡靈彷徨熱帶鈴勃梭雪冰護豹珍珠櫻空棘愛心啞屬艾歐蓋固坐祈代希苗台猛曼拿兒"
    "狸法師箱蟀勒倫琴含羞苞槌城結貴婦紳蜜女帕茲潛兔隨捲耳魅東施鐺響坦銅鏡鐘盆聒噪陸尖"
    "咬不良骷光霓虹自舔狂遠Ｚ由盧席恩騎色霏萊謝米爾宙提主暖炒武刃丸劍探步哨約扒酷冷蝕"
    "豆鴿高雉幔龐滾蝙螺釘差搬運匠修建蟾蜍投摔打包保足蜈蚣車輪毬精根裙野蠻鱸混流氓紅倒"
    "狒殿滑巾徵哭具死神棺原肋始祖破灰塵索沫栗德單卵細胞造鵝倍四季萌哎呀敗輕蜘堅齒組麻"
    "鰻宇燭幽晶斧嚏幾何敏捷功夫父赤駒劈司令炸雄禿丫首惡燃燒畢雲酋迪耶塔賽里狐呱賀掘彩"
    "蓓潔能鞘芳芙妮好魷賊腳鎧垃藻臂槍傘咚碎黏鑰朽南瓜嗡哲裴格梟狙射熾咆哮虎漾壬篤啄銃"
    "少強鍬農勝虻鬃弱壞驢仔重挽滴偽睡罩盜著竹療環智揮猩擲膽噬堡爺參性：銀伴隕枕戈謎擬"
    "Ｑ磨舵鱗杖璞・鳴哞鰭科莫迦虛吾肌費束輝紙御機夏"
))

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

                cutoff = max(total_subfiles // 10, 1)
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
