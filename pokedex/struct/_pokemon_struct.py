# encoding: utf8
u"""Defines a construct `pokemon_struct`, containing the structure of a single
Pokémon saved within a game -- often seen as a .pkm file.  This is the same
format sent back and forth over the GTS.
"""

import datetime

from construct import *

# TODO:
# - strings should be validated, going both in and out
# - strings need to pad themselves when being re-encoded
# - strings sometimes need specific padding christ
# - date_met is not optional
# - some way to be more lenient with junk data, or at least
# - higher-level validation; see XXXes below
# - personality indirectly influences IVs due to PRNG use

pokemon_forms = {
    # Unown
    201: list('abcdefghijklmnopqrstuvwxyz') + ['exclamation', 'question'],

    # Deoxys
    386: ['normal', 'attack', 'defense', 'speed'],

    # Burmy and Wormadam
    412: ['plant', 'sandy', 'trash'],
    413: ['plant', 'sandy', 'trash'],

    # Shellos and Gastrodon
    422: ['west', 'east'],
    423: ['west', 'east'],

    # Rotom
    479: ['normal', 'heat', 'wash', 'frost', 'fan', 'mow'],

    # Giratina
    487: ['altered', 'origin'],

    # Shaymin
    492: ['land', 'sky'],

    # Arceus
    493: [
        'normal', 'fighting', 'flying', 'poison', 'ground', 'rock',
        'bug', 'ghost', 'steel', 'fire', 'water', 'grass',
        'thunder', 'psychic', 'ice', 'dragon', 'dark', 'unknown',
    ],
}

# The entire gen 4 character table:
character_table_gen4 = {
    0x0002: u'ぁ',
    0x0003: u'あ',
    0x0004: u'ぃ',
    0x0005: u'い',
    0x0006: u'ぅ',
    0x0007: u'う',
    0x0008: u'ぇ',
    0x0009: u'え',
    0x000a: u'ぉ',
    0x000b: u'お',
    0x000c: u'か',
    0x000d: u'が',
    0x000e: u'き',
    0x000f: u'ぎ',
    0x0010: u'く',
    0x0011: u'ぐ',
    0x0012: u'け',
    0x0013: u'げ',
    0x0014: u'こ',
    0x0015: u'ご',
    0x0016: u'さ',
    0x0017: u'ざ',
    0x0018: u'し',
    0x0019: u'じ',
    0x001a: u'す',
    0x001b: u'ず',
    0x001c: u'せ',
    0x001d: u'ぜ',
    0x001e: u'そ',
    0x001f: u'ぞ',
    0x0020: u'た',
    0x0021: u'だ',
    0x0022: u'ち',
    0x0023: u'ぢ',
    0x0024: u'っ',
    0x0025: u'つ',
    0x0026: u'づ',
    0x0027: u'て',
    0x0028: u'で',
    0x0029: u'と',
    0x002a: u'ど',
    0x002b: u'な',
    0x002c: u'に',
    0x002d: u'ぬ',
    0x002e: u'ね',
    0x002f: u'の',
    0x0030: u'は',
    0x0031: u'ば',
    0x0032: u'ぱ',
    0x0033: u'ひ',
    0x0034: u'び',
    0x0035: u'ぴ',
    0x0036: u'ふ',
    0x0037: u'ぶ',
    0x0038: u'ぷ',
    0x0039: u'へ',
    0x003a: u'べ',
    0x003b: u'ぺ',
    0x003c: u'ほ',
    0x003d: u'ぼ',
    0x003e: u'ぽ',
    0x003f: u'ま',
    0x0040: u'み',
    0x0041: u'む',
    0x0042: u'め',
    0x0043: u'も',
    0x0044: u'ゃ',
    0x0045: u'や',
    0x0046: u'ゅ',
    0x0047: u'ゆ',
    0x0048: u'ょ',
    0x0049: u'よ',
    0x004a: u'ら',
    0x004b: u'り',
    0x004c: u'る',
    0x004d: u'れ',
    0x004e: u'ろ',
    0x004f: u'わ',
    0x0050: u'を',
    0x0051: u'ん',
    0x0052: u'ァ',
    0x0053: u'ア',
    0x0054: u'ィ',
    0x0055: u'イ',
    0x0056: u'ゥ',
    0x0057: u'ウ',
    0x0058: u'ェ',
    0x0059: u'エ',
    0x005a: u'ォ',
    0x005b: u'オ',
    0x005c: u'カ',
    0x005d: u'ガ',
    0x005e: u'キ',
    0x005f: u'ギ',
    0x0060: u'ク',
    0x0061: u'グ',
    0x0062: u'ケ',
    0x0063: u'ゲ',
    0x0064: u'コ',
    0x0065: u'ゴ',
    0x0066: u'サ',
    0x0067: u'ザ',
    0x0068: u'シ',
    0x0069: u'ジ',
    0x006a: u'ス',
    0x006b: u'ズ',
    0x006c: u'セ',
    0x006d: u'ゼ',
    0x006e: u'ソ',
    0x006f: u'ゾ',
    0x0070: u'タ',
    0x0071: u'ダ',
    0x0072: u'チ',
    0x0073: u'ヂ',
    0x0074: u'ッ',
    0x0075: u'ツ',
    0x0076: u'ヅ',
    0x0077: u'テ',
    0x0078: u'デ',
    0x0079: u'ト',
    0x007a: u'ド',
    0x007b: u'ナ',
    0x007c: u'ニ',
    0x007d: u'ヌ',
    0x007e: u'ネ',
    0x007f: u'ノ',
    0x0080: u'ハ',
    0x0081: u'バ',
    0x0082: u'パ',
    0x0083: u'ヒ',
    0x0084: u'ビ',
    0x0085: u'ピ',
    0x0086: u'フ',
    0x0087: u'ブ',
    0x0088: u'プ',
    0x0089: u'ヘ',
    0x008a: u'ベ',
    0x008b: u'ペ',
    0x008c: u'ホ',
    0x008d: u'ボ',
    0x008e: u'ポ',
    0x008f: u'マ',
    0x0090: u'ミ',
    0x0091: u'ム',
    0x0092: u'メ',
    0x0093: u'モ',
    0x0094: u'ャ',
    0x0095: u'ヤ',
    0x0096: u'ュ',
    0x0097: u'ユ',
    0x0098: u'ョ',
    0x0099: u'ヨ',
    0x009a: u'ラ',
    0x009b: u'リ',
    0x009c: u'ル',
    0x009d: u'レ',
    0x009e: u'ロ',
    0x009f: u'ワ',
    0x00a0: u'ヲ',
    0x00a1: u'ン',
    0x00a2: u'０',
    0x00a3: u'１',
    0x00a4: u'２',
    0x00a5: u'３',
    0x00a6: u'４',
    0x00a7: u'５',
    0x00a8: u'６',
    0x00a9: u'７',
    0x00aa: u'８',
    0x00ab: u'９',
    0x00ac: u'Ａ',
    0x00ad: u'Ｂ',
    0x00ae: u'Ｃ',
    0x00af: u'Ｄ',
    0x00b0: u'Ｅ',
    0x00b1: u'Ｆ',
    0x00b2: u'Ｇ',
    0x00b3: u'Ｈ',
    0x00b4: u'Ｉ',
    0x00b5: u'Ｊ',
    0x00b6: u'Ｋ',
    0x00b7: u'Ｌ',
    0x00b8: u'Ｍ',
    0x00b9: u'Ｎ',
    0x00ba: u'Ｏ',
    0x00bb: u'Ｐ',
    0x00bc: u'Ｑ',
    0x00bd: u'Ｒ',
    0x00be: u'Ｓ',
    0x00bf: u'Ｔ',
    0x00c0: u'Ｕ',
    0x00c1: u'Ｖ',
    0x00c2: u'Ｗ',
    0x00c3: u'Ｘ',
    0x00c4: u'Ｙ',
    0x00c5: u'Ｚ',
    0x00c6: u'ａ',
    0x00c7: u'ｂ',
    0x00c8: u'ｃ',
    0x00c9: u'ｄ',
    0x00ca: u'ｅ',
    0x00cb: u'ｆ',
    0x00cc: u'ｇ',
    0x00cd: u'ｈ',
    0x00ce: u'ｉ',
    0x00cf: u'ｊ',
    0x00d0: u'ｋ',
    0x00d1: u'ｌ',
    0x00d2: u'ｍ',
    0x00d3: u'ｎ',
    0x00d4: u'ｏ',
    0x00d5: u'ｐ',
    0x00d6: u'ｑ',
    0x00d7: u'ｒ',
    0x00d8: u'ｓ',
    0x00d9: u'ｔ',
    0x00da: u'ｕ',
    0x00db: u'ｖ',
    0x00dc: u'ｗ',
    0x00dd: u'ｘ',
    0x00de: u'ｙ',
    0x00df: u'ｚ',
    0x00e0: u'à',
    0x00e1: u'！',
    0x00e2: u'？',
    0x00e3: u'、',
    0x00e4: u'。',
    0x00e5: u'…',
    0x00e6: u'・',
    0x00e7: u'／',
    0x00e8: u'「',
    0x00e9: u'」',
    0x00ea: u'『',
    0x00eb: u'』',
    0x00ec: u'（',
    0x00ed: u'）',
    0x00ee: u'♂',
    0x00ef: u'♀',
    0x00f0: u'＋',
    0x00f1: u'ー',
    0x00f2: u'×',
    0x00f3: u'÷',
    0x00f4: u'=',
    0x00f5: u'~',
    0x00f6: u'：',
    0x00f7: u'；',
    0x00f8: u'．',
    0x00f9: u'，',
    0x00fa: u'♠',
    0x00fb: u'♣',
    0x00fc: u'♥',
    0x00fd: u'♦',
    0x00fe: u'★',
    0x00ff: u'◎',
    0x0100: u'○',
    0x0101: u'□',
    0x0102: u'△',
    0x0103: u'◇',
    0x0104: u'＠',
    0x0105: u'♪',
    0x0106: u'%',
    0x0107: u'☀',
    0x0108: u'☁',
    0x0109: u'☂',
    0x010a: u'☃',
    0x010f: u'⤴',
    0x0110: u'⤵',
    0x0112: u'円',
    0x0116: u'✉',
    0x011b: u'←',
    0x011c: u'↑',
    0x011d: u'↓',
    0x011e: u'→',
    0x0120: u'&',
    0x0121: u'0',
    0x0122: u'1',
    0x0123: u'2',
    0x0124: u'3',
    0x0125: u'4',
    0x0126: u'5',
    0x0127: u'6',
    0x0128: u'7',
    0x0129: u'8',
    0x012a: u'9',
    0x012b: u'A',
    0x012c: u'B',
    0x012d: u'C',
    0x012e: u'D',
    0x012f: u'E',
    0x0130: u'F',
    0x0131: u'G',
    0x0132: u'H',
    0x0133: u'I',
    0x0134: u'J',
    0x0135: u'K',
    0x0136: u'L',
    0x0137: u'M',
    0x0138: u'N',
    0x0139: u'O',
    0x013a: u'P',
    0x013b: u'Q',
    0x013c: u'R',
    0x013d: u'S',
    0x013e: u'T',
    0x013f: u'U',
    0x0140: u'V',
    0x0141: u'W',
    0x0142: u'X',
    0x0143: u'Y',
    0x0144: u'Z',
    0x0145: u'a',
    0x0146: u'b',
    0x0147: u'c',
    0x0148: u'd',
    0x0149: u'e',
    0x014a: u'f',
    0x014b: u'g',
    0x014c: u'h',
    0x014d: u'i',
    0x014e: u'j',
    0x014f: u'k',
    0x0150: u'l',
    0x0151: u'm',
    0x0152: u'n',
    0x0153: u'o',
    0x0154: u'p',
    0x0155: u'q',
    0x0156: u'r',
    0x0157: u's',
    0x0158: u't',
    0x0159: u'u',
    0x015a: u'v',
    0x015b: u'w',
    0x015c: u'x',
    0x015d: u'y',
    0x015e: u'z',
    0x015f: u'À',
    0x0160: u'Á',
    0x0161: u'Â',
    0x0163: u'Ä',
    0x0166: u'Ç',
    0x0167: u'È',
    0x0168: u'É',
    0x0169: u'Ê',
    0x016a: u'Ë',
    0x016b: u'Ì',
    0x016c: u'Í',
    0x016d: u'Î',
    0x016e: u'Ï',
    0x0170: u'Ñ',
    0x0171: u'Ò',
    0x0172: u'Ó',
    0x0173: u'Ô',
    0x0175: u'Ö',
    0x0176: u'×',
    0x0178: u'Ù',
    0x0179: u'Ú',
    0x017a: u'Û',
    0x017b: u'Ü',
    0x017e: u'ß',
    0x017f: u'à',
    0x0180: u'á',
    0x0181: u'â',
    0x0183: u'ä',
    0x0186: u'ç',
    0x0187: u'è',
    0x0188: u'é',
    0x0189: u'ê',
    0x018a: u'ë',
    0x018b: u'ì',
    0x018c: u'í',
    0x018d: u'î',
    0x018e: u'ï',
    0x0190: u'ñ',
    0x0191: u'ò',
    0x0192: u'ó',
    0x0193: u'ô',
    0x0195: u'ö',
    0x0196: u'÷',
    0x0198: u'ù',
    0x0199: u'ú',
    0x019a: u'û',
    0x019b: u'ü',
    0x019f: u'Œ',
    0x01a0: u'œ',
    0x01a3: u'ª',
    0x01a4: u'º',
    0x01a5: u'þ',
    0x01a6: u'Þ',
    0x01a7: u'ʳ',
    0x01a8: u'¥',
    0x01a9: u'¡',
    0x01aa: u'¿',
    0x01ab: u'!',
    0x01ac: u'?',
    0x01ad: u',',
    0x01ae: u'.',
    0x01af: u'…',
    0x01b0: u'·',
    0x01b1: u'/',
    0x01b2: u'‘',
    0x01b3: u'\'',
    0x01b3: u'’',
    0x01b4: u'“',
    0x01b5: u'”',
    0x01b6: u'„',
    0x01b7: u'«',
    0x01b8: u'»',
    0x01b9: u'(',
    0x01ba: u')',
    0x01bb: u'♂',
    0x01bc: u'♀',
    0x01bd: u'+',
    0x01be: u'-',
    0x01bf: u'*',
    0x01c0: u'#',
    0x01c1: u'=',
    0x01c2: u'&',
    0x01c3: u'~',
    0x01c4: u':',
    0x01c5: u';',
    0x01c6: u'♠',
    0x01c7: u'♣',
    0x01c8: u'♥',
    0x01c9: u'♦',
    0x01ca: u'★',
    0x01cb: u'◎',
    0x01cc: u'○',
    0x01cd: u'□',
    0x01ce: u'△',
    0x01cf: u'◇',
    0x01d0: u'@',
    0x01d1: u'♪',
    0x01d2: u'%',
    0x01d3: u'☀',
    0x01d4: u'☁',
    0x01d5: u'☂',
    0x01d6: u'☃',
    0x01db: u'⤴',
    0x01dc: u'⤵',
    0x01de: u' ',
    0xe000: u'\n',
    0x25bc: u'\f',
    0x25bd: u'\r',
}

# Generation 5 uses UCS-16, with a few exceptions
character_table_gen5 = {
    # Here nintendo just didn't do their homework:
    0x247d: u'☂',
    0x247b: u'☁',
    0x247a: u'☀',
    0x2479: u'♪',
    0x2478: u'◇',
    0x2477: u'△',
    0x2476: u'□',
    0x2475: u'○',
    0x2474: u'◎',
    0x2473: u'★',
    0x2472: u'♦',
    0x2471: u'♥',
    0x2470: u'♣',
    0x246f: u'♠',
    0x246e: u'♀',
    0x246d: u'♂',
    0x246c: u'…',
    0x2468: u'÷',
    0x2467: u'×',
    0x21d4: u'⤴',
    0x2200: u'⤵',

    # These aren't direct equivalents, but better than nothing:
    0x0024: u'$',  # pokémoney sign
    0x21d2: u'☹',  # frowny face
    0x2203: u'ℤ',  # ZZ ligature
    0x2227: u'☺',  # smiling face
    0x2228: u'😁',  # grinning face
    0xffe2: u'😭',  # hurt face

    # The following duplicates & weird characters get to keep their positions
    # ①..⑦
    # 0x2460: halfwidth smiling face
    # 0x2461: grinning face
    # 0x2462: hurt face
    # 0x2463: frowny face
    # 0x2464: ⤴
    # 0x2465: ⤵
    # 0x2466: ZZ ligature
    # ⑩..⑫
    # 0x2469: superscript er
    # 0x246a: superscript re
    # 0x246b: superscript r
    # ⑾..⒇
    # 0x247e: halfwidth smiling face
    # 0x247f: halfwidth grinning face
    # 0x2480: halfwidth hurt face
    # 0x2481: halfwidth frowny face
    # 0x2482: halfwidth ⤴
    # 0x2483: halfwidth ⤵
    # 0x2484: halfwidth ZZ ligature
    # 0x2485: superscript e
    # 0x2486: PK ligature
    # 0x2487: MN ligature
}


def LittleEndianBitStruct(*args):
    """Construct's bit structs read a byte at a time in the order they appear,
    reading each bit from most to least significant.  Alas, this doesn't work
    at all for a 32-bit bit field, because the bytes are 'backwards' in
    little-endian files.

    So this acts as a bit struct, but reverses the order of bytes before
    reading/writing, so ALL the bits are read from most to least significant.
    """
    return Buffered(
        BitStruct(*args),
        encoder=lambda s: s[::-1],
        decoder=lambda s: s[::-1],
        resizer=lambda _: _,
    )


class StringWithOriginal(unicode):
    pass


class PokemonStringAdapter(Adapter):
    u"""Base adapter for names

    Encodes/decodes Pokémon-formatted text stored in a regular String struct.

    Returns an unicode subclass that has an ``original`` attribute with the
    original unencoded value, complete with trash bytes.
    On write, if the ``original`` is found, it is written with no regard to the
    string value.
    This ensures the trash bytes get written back untouched if the string is
    unchanged.
    """
    def __init__(self, field, length):
        super(PokemonStringAdapter, self).__init__(field)
        self.length = length

    def _decode(self, obj, context):
        decoded_text = obj.decode('utf16')

        # Real string ends at the \uffff character
        if u'\uffff' in decoded_text:
            decoded_text = decoded_text[0:decoded_text.index(u'\uffff')]

        result = StringWithOriginal(
            decoded_text.translate(self.character_table))
        result.original = obj  # save original with "trash bytes"
        return result

    def _encode(self, obj, context):
        try:
            original = obj.original
        except AttributeError:
            length = self.length
            padded_text = (obj + u'\uffff' + '\x00' * length)
            decoded_text = padded_text.translate(self.inverse_character_table)
            return decoded_text.encode('utf-16LE')[:length]
        else:
            if self._decode(original, context) != obj:
                raise ValueError("String and original don't match")
            return original


def make_pokemon_string_adapter(table, generation):
    class _SpecificAdapter(PokemonStringAdapter):
        character_table = table
        inverse_character_table = dict((ord(v), k) for k, v in
            table.iteritems())
    _SpecificAdapter.__name__ = 'PokemonStringAdapterGen%s' % generation
    return _SpecificAdapter

PokemonStringAdapterGen4 = make_pokemon_string_adapter(character_table_gen4, 4)
PokemonStringAdapterGen5 = make_pokemon_string_adapter(character_table_gen5, 5)


class DateAdapter(Adapter):
    """Converts between a three-byte string and a Python date.

    Only dates in 2000 or later will work!
    """
    def _decode(self, obj, context):
        if obj == '\x00\x00\x00':
            return None

        y, m, d = (ord(byte) for byte in obj)
        y += 2000
        return datetime.date(y, m, d)

    def _encode(self, obj, context):
        if obj is None:
            return '\x00\x00\x00'

        y, m, d = obj.year - 2000, obj.month, obj.day
        return ''.join(chr(n) for n in (y, m, d))

class LeakyEnum(Adapter):
    """An Enum that allows unknown values"""
    def __init__(self, sub, **values):
        super(LeakyEnum, self).__init__(sub)
        self.values = values
        self.inverted_values = dict((v, k) for k, v in values.items())
        assert len(values) == len(self.inverted_values)

    def _encode(self, obj, context):
        return self.values.get(obj, obj)

    def _decode(self, obj, context):
        return self.inverted_values.get(obj, obj)


# Docs: http://projectpokemon.org/wiki/Pokemon_NDS_Structure
# http://projectpokemon.org/wiki/Pokemon_Black/White_NDS_Structure
# http://projectpokemon.org/forums/showthread.php?11474-Hex-Values-and-Trashbytes-in-B-W#post93598

def make_pokemon_struct(generation):
    """Make a pokemon struct class for the given generation
    """
    leaves_or_nature = {
        4: BitStruct('shining_leaves',
                Padding(2),
                Flag('crown'),
                Flag('leaf5'),
                Flag('leaf4'),
                Flag('leaf3'),
                Flag('leaf2'),
                Flag('leaf1'),
            ),
        5: ULInt8('nature_id'),
    }[generation]

    padding_or_hidden_ability = {
        4: Padding(1),
        5: Flag('hidden_ability'),
    }[generation]

    PokemonStringAdapter = {
        4: PokemonStringAdapterGen4,
        5: PokemonStringAdapterGen5,
    }[generation]

    return Struct('pokemon_struct',
        # Header
        ULInt32('personality'),  # XXX aughgh http://bulbapedia.bulbagarden.net/wiki/Personality
        Padding(2),
        ULInt16('checksum'),  # XXX should be checked or calculated

        # Block A
        ULInt16('national_id'),
        ULInt16('held_item_id'),
        ULInt16('original_trainer_id'),
        ULInt16('original_trainer_secret_id'),
        ULInt32('exp'),
        ULInt8('happiness'),
        ULInt8('ability_id'),  # XXX needs to match personality + species
        BitStruct('markings',
            Padding(2),
            Flag('diamond'),
            Flag('star'),
            Flag('heart'),
            Flag('square'),
            Flag('triangle'),
            Flag('circle'),
        ),
        LeakyEnum(ULInt8('original_country'),
            jp=1,
            us=2,
            fr=3,
            it=4,
            de=5,
            es=7,
            kr=8,
        ),

        # XXX sum cannot surpass 510
        ULInt8('effort_hp'),
        ULInt8('effort_attack'),
        ULInt8('effort_defense'),
        ULInt8('effort_speed'),
        ULInt8('effort_special_attack'),
        ULInt8('effort_special_defense'),

        ULInt8('contest_cool'),
        ULInt8('contest_beauty'),
        ULInt8('contest_cute'),
        ULInt8('contest_smart'),
        ULInt8('contest_tough'),
        ULInt8('contest_sheen'),

        LittleEndianBitStruct('sinnoh_ribbons',
            Padding(4),
            Flag('premier_ribbon'),
            Flag('classic_ribbon'),
            Flag('carnival_ribbon'),
            Flag('festival_ribbon'),
            Flag('blue_ribbon'),
            Flag('green_ribbon'),
            Flag('red_ribbon'),
            Flag('legend_ribbon'),
            Flag('history_ribbon'),
            Flag('record_ribbon'),
            Flag('footprint_ribbon'),
            Flag('gorgeous_royal_ribbon'),
            Flag('royal_ribbon'),
            Flag('gorgeous_ribbon'),
            Flag('smile_ribbon'),
            Flag('snooze_ribbon'),
            Flag('relax_ribbon'),
            Flag('careless_ribbon'),
            Flag('downcast_ribbon'),
            Flag('shock_ribbon'),
            Flag('alert_ribbon'),
            Flag('world_ability_ribbon'),
            Flag('pair_ability_ribbon'),
            Flag('multi_ability_ribbon'),
            Flag('double_ability_ribbon'),
            Flag('great_ability_ribbon'),
            Flag('ability_ribbon'),
            Flag('sinnoh_champ_ribbon'),
        ),

        # Block B
        ULInt16('move1_id'),
        ULInt16('move2_id'),
        ULInt16('move3_id'),
        ULInt16('move4_id'),
        ULInt8('move1_pp'),
        ULInt8('move2_pp'),
        ULInt8('move3_pp'),
        ULInt8('move4_pp'),
        ULInt8('move1_pp_ups'),
        ULInt8('move2_pp_ups'),
        ULInt8('move3_pp_ups'),
        ULInt8('move4_pp_ups'),

        Embed(LittleEndianBitStruct('ivs',
            Flag('is_nicknamed'),
            Flag('is_egg'),
            BitField('iv_special_defense', 5),
            BitField('iv_special_attack', 5),
            BitField('iv_speed', 5),
            BitField('iv_defense', 5),
            BitField('iv_attack', 5),
            BitField('iv_hp', 5),
        )),
        LittleEndianBitStruct('hoenn_ribbons',
            Flag('world_ribbon'),
            Flag('earth_ribbon'),
            Flag('national_ribbon'),
            Flag('country_ribbon'),
            Flag('sky_ribbon'),
            Flag('land_ribbon'),
            Flag('marine_ribbon'),
            Flag('effort_ribbon'),
            Flag('artist_ribbon'),
            Flag('victory_ribbon'),
            Flag('winning_ribbon'),
            Flag('champion_ribbon'),
            Flag('tough_ribbon_master'),
            Flag('tough_ribbon_hyper'),
            Flag('tough_ribbon_super'),
            Flag('tough_ribbon'),
            Flag('smart_ribbon_master'),
            Flag('smart_ribbon_hyper'),
            Flag('smart_ribbon_super'),
            Flag('smart_ribbon'),
            Flag('cute_ribbon_master'),
            Flag('cute_ribbon_hyper'),
            Flag('cute_ribbon_super'),
            Flag('cute_ribbon'),
            Flag('beauty_ribbon_master'),
            Flag('beauty_ribbon_hyper'),
            Flag('beauty_ribbon_super'),
            Flag('beauty_ribbon'),
            Flag('cool_ribbon_master'),
            Flag('cool_ribbon_hyper'),
            Flag('cool_ribbon_super'),
            Flag('cool_ribbon'),
        ),
        Embed(EmbeddedBitStruct(
            BitField('alternate_form_id', 5),
            Enum(BitField('gender', 2),
                genderless = 2,
                male = 0,
                female = 1,
            ),
            Flag('fateful_encounter'),
        )),
        leaves_or_nature,
        padding_or_hidden_ability,
        Padding(1),
        ULInt16('pt_egg_location_id'),
        ULInt16('pt_met_location_id'),

        # Block C
        PokemonStringAdapter(String('nickname', 22), 22),
        Padding(1),
        LeakyEnum(ULInt8('original_version'),
            sapphire = 1,
            ruby = 2,
            emerald = 3,
            firered = 4,
            leafgreen = 5,
            heartgold = 7,
            soulsilver = 8,
            diamond = 10,
            pearl = 11,
            platinum = 12,
            orre = 15,
        ),
        LittleEndianBitStruct('sinnoh_contest_ribbons',
            Padding(12),
            Flag('tough_ribbon_master'),
            Flag('tough_ribbon_ultra'),
            Flag('tough_ribbon_great'),
            Flag('tough_ribbon'),
            Flag('smart_ribbon_master'),
            Flag('smart_ribbon_ultra'),
            Flag('smart_ribbon_great'),
            Flag('smart_ribbon'),
            Flag('cute_ribbon_master'),
            Flag('cute_ribbon_ultra'),
            Flag('cute_ribbon_great'),
            Flag('cute_ribbon'),
            Flag('beauty_ribbon_master'),
            Flag('beauty_ribbon_ultra'),
            Flag('beauty_ribbon_great'),
            Flag('beauty_ribbon'),
            Flag('cool_ribbon_master'),
            Flag('cool_ribbon_ultra'),
            Flag('cool_ribbon_great'),
            Flag('cool_ribbon'),
        ),
        Padding(4),

        # Block D
        PokemonStringAdapter(String('original_trainer_name', 16), 16),
        DateAdapter(String('date_egg_received', 3)),
        DateAdapter(String('date_met', 3)),
        ULInt16('dp_egg_location_id'),
        ULInt16('dp_met_location_id'),
        ULInt8('pokerus'),  # Warning : Values changed in gen 5
        ULInt8('dppt_pokeball'),
        EmbeddedBitStruct(
            Enum(Flag('original_trainer_gender'),
                male = False,
                female = True,
            ),
            BitField('met_at_level', 7),
        ),
        LeakyEnum(ULInt8('encounter_type'),
            special = 0,        # egg; pal park; event; honey tree; shaymin
            grass = 2,          # or darkrai
            dialga_palkia = 4,
            cave = 5,           # or giratina or hall of origin
            water = 7,
            building = 9,
            safari_zone = 10,   # includes great marsh
            gift = 12,          # starter; fossil; ingame trade?
            # distortion_world = ???,
            hgss_gift = 24,     # starter; fossil; bebe's eevee  (pt only??)
        ),
        ULInt8('hgss_pokeball'),
        Padding(1),
    )
