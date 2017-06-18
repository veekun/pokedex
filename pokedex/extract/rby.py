"""Extract all the juicy details from a Gen I game.

This was a pain in the ass!  Thank you SO MUCH to:

    pokered
    pokeyellow
    vixie
    http://www.pastraiser.com/cpu/gameboy/gameboy_opcodes.html
"""
# TODO fix that docstring
# TODO note terminology somewhere: id, index, identifier
from collections import defaultdict
from collections import OrderedDict
import hashlib
import io
import logging
from pathlib import Path
import sys

from camel import Camel
from classtools import reify
from construct import (
    # Simple fields
    BitsInteger, Byte, Bytes, CString, Const, Flag, Int8ul, Int16ub, Int16ul,
    Padding, String,
    # Structures and meta stuff
    Adapter, Array, Bitwise, BitsSwapped, Construct, Embedded, Enum, Peek,
    Pointer, Struct, Subconstruct, Switch,
)

from pokedex.extract.lib.gbz80 import find_code
import pokedex.schema as schema

# TODO set this up to colorcode, probably put that...  elsewhere
log = logging.getLogger(__name__)

# Known official games, the languages they were released in, and hashes of
# their contents
GAME_RELEASE_MD5SUMS = {
    # Set 0: Original Red/Green, only released in Japan
    'jp-red': {
        'ja': [
            '912d4f77d118390a2e2c42b2016a19d4',  # original
            '4c44844f8d5aa3305a0cf2c95cf96333',  # revision A
        ],
    },
    'jp-green': {
        'ja': [
            'e30ffbab1f239f09b226477d84db1368',  # original
            '16ddd8897092936fbc0e286c6a6b23a2',  # revision A
        ],
    },

    # Set 1: Blue in Japan, split into Red and Blue worldwide
    'jp-blue': {
        'ja': ['c1adf0a77809ac91d905a4828888a2f0'],
    },
    'ww-red': {
        'de': ['8ed0e8d45a81ca34de625d930148a512'],
        'en': ['3d45c1ee9abd5738df46d2bdda8b57dc'],
        'es': ['463c241c8721ab1d1da17c91de9f8a32'],
        'fr': ['669700657cb06ed09371cdbdef69e8a3'],
        'it': ['6468fb0652dde30eb968a44f17c686f1'],
    },
    'ww-blue': {
        'de': ['a1ec7f07c7b4251d5fafc50622d546f8'],
        'en': ['50927e843568814f7ed45ec4f944bd8b'],
        'es': ['6e7663f908334724548a66fc9c386002'],
        'fr': ['35c8154c81abb2ab850689fd28a03515'],
        'it': ['ebe0742b472b3e80a9c6749f06181073'],
    },

    # Set 2: Yellow, pretty much the same everywhere
    # TODO is that true?
    # TODO missing other languages
    'yellow': {
        'en': ['d9290db87b1f0a23b89f99ee4469e34b'],
        'ja': [
            'aa13e886a47fd473da63b7d5ddf2828d',  # original
            '96c1f411671b6e1761cf31884dde0dbb',  # revision A
            '5d9c071cf6eb5f3a697bbcd9311b4d04',  # revision B
        ],
    }
}
# Same, but rearranged to md5 => (game, language)
GAME_RELEASE_MD5SUM_INDEX = {
    md5sum: (game, language)
    for (game, language_sums) in GAME_RELEASE_MD5SUMS.items()
    for (language, md5sums) in language_sums.items()
    for md5sum in md5sums
}


# ------------------------------------------------------------------------------
# Game structure stuff
#
# A lot of this was made much, much easier by the work done on pokered:
# https://github.com/pret/pokered
# Thank y'all so much!
# TODO possibly some of this should be in a shared place, not this file


GROWTH_RATES = {
    0: 'gr.medium',
    3: 'gr.medium-slow',
    4: 'gr.fast',
    5: 'gr.slow',
}

EVOLUTION_TRIGGERS = {
    1: 'ev.level-up',
    2: 'ev.use-item',
    3: 'ev.trade',
}

# TODO these are loci, not enums, so hardcoding all their identifiers here
# makes me nonspecifically uncomfortable
POKEMON_IDENTIFIERS = {
    1: 'p.bulbasaur',
    2: 'p.ivysaur',
    3: 'p.venusaur',
    4: 'p.charmander',
    5: 'p.charmeleon',
    6: 'p.charizard',
    7: 'p.squirtle',
    8: 'p.wartortle',
    9: 'p.blastoise',
    10: 'p.caterpie',
    11: 'p.metapod',
    12: 'p.butterfree',
    13: 'p.weedle',
    14: 'p.kakuna',
    15: 'p.beedrill',
    16: 'p.pidgey',
    17: 'p.pidgeotto',
    18: 'p.pidgeot',
    19: 'p.rattata',
    20: 'p.raticate',
    21: 'p.spearow',
    22: 'p.fearow',
    23: 'p.ekans',
    24: 'p.arbok',
    25: 'p.pikachu',
    26: 'p.raichu',
    27: 'p.sandshrew',
    28: 'p.sandslash',
    29: 'p.nidoran-f',
    30: 'p.nidorina',
    31: 'p.nidoqueen',
    32: 'p.nidoran-m',
    33: 'p.nidorino',
    34: 'p.nidoking',
    35: 'p.clefairy',
    36: 'p.clefable',
    37: 'p.vulpix',
    38: 'p.ninetales',
    39: 'p.jigglypuff',
    40: 'p.wigglytuff',
    41: 'p.zubat',
    42: 'p.golbat',
    43: 'p.oddish',
    44: 'p.gloom',
    45: 'p.vileplume',
    46: 'p.paras',
    47: 'p.parasect',
    48: 'p.venonat',
    49: 'p.venomoth',
    50: 'p.diglett',
    51: 'p.dugtrio',
    52: 'p.meowth',
    53: 'p.persian',
    54: 'p.psyduck',
    55: 'p.golduck',
    56: 'p.mankey',
    57: 'p.primeape',
    58: 'p.growlithe',
    59: 'p.arcanine',
    60: 'p.poliwag',
    61: 'p.poliwhirl',
    62: 'p.poliwrath',
    63: 'p.abra',
    64: 'p.kadabra',
    65: 'p.alakazam',
    66: 'p.machop',
    67: 'p.machoke',
    68: 'p.machamp',
    69: 'p.bellsprout',
    70: 'p.weepinbell',
    71: 'p.victreebel',
    72: 'p.tentacool',
    73: 'p.tentacruel',
    74: 'p.geodude',
    75: 'p.graveler',
    76: 'p.golem',
    77: 'p.ponyta',
    78: 'p.rapidash',
    79: 'p.slowpoke',
    80: 'p.slowbro',
    81: 'p.magnemite',
    82: 'p.magneton',
    83: 'p.farfetchd',
    84: 'p.doduo',
    85: 'p.dodrio',
    86: 'p.seel',
    87: 'p.dewgong',
    88: 'p.grimer',
    89: 'p.muk',
    90: 'p.shellder',
    91: 'p.cloyster',
    92: 'p.gastly',
    93: 'p.haunter',
    94: 'p.gengar',
    95: 'p.onix',
    96: 'p.drowzee',
    97: 'p.hypno',
    98: 'p.krabby',
    99: 'p.kingler',
    100: 'p.voltorb',
    101: 'p.electrode',
    102: 'p.exeggcute',
    103: 'p.exeggutor',
    104: 'p.cubone',
    105: 'p.marowak',
    106: 'p.hitmonlee',
    107: 'p.hitmonchan',
    108: 'p.lickitung',
    109: 'p.koffing',
    110: 'p.weezing',
    111: 'p.rhyhorn',
    112: 'p.rhydon',
    113: 'p.chansey',
    114: 'p.tangela',
    115: 'p.kangaskhan',
    116: 'p.horsea',
    117: 'p.seadra',
    118: 'p.goldeen',
    119: 'p.seaking',
    120: 'p.staryu',
    121: 'p.starmie',
    122: 'p.mr-mime',
    123: 'p.scyther',
    124: 'p.jynx',
    125: 'p.electabuzz',
    126: 'p.magmar',
    127: 'p.pinsir',
    128: 'p.tauros',
    129: 'p.magikarp',
    130: 'p.gyarados',
    131: 'p.lapras',
    132: 'p.ditto',
    133: 'p.eevee',
    134: 'p.vaporeon',
    135: 'p.jolteon',
    136: 'p.flareon',
    137: 'p.porygon',
    138: 'p.omanyte',
    139: 'p.omastar',
    140: 'p.kabuto',
    141: 'p.kabutops',
    142: 'p.aerodactyl',
    143: 'p.snorlax',
    144: 'p.articuno',
    145: 'p.zapdos',
    146: 'p.moltres',
    147: 'p.dratini',
    148: 'p.dragonair',
    149: 'p.dragonite',
    150: 'p.mewtwo',
    151: 'p.mew',
}

TYPE_IDENTIFIERS = {
    0: 't.normal',
    1: 't.fighting',
    2: 't.flying',
    3: 't.poison',
    4: 't.ground',
    5: 't.rock',
    #6: 't.bird',
    7: 't.bug',
    8: 't.ghost',
    9: 't.steel',
    20: 't.fire',
    21: 't.water',
    22: 't.grass',
    23: 't.electric',
    24: 't.psychic',
    25: 't.ice',
    26: 't.dragon',
    27: 't.dark',
}

MOVE_IDENTIFIERS = {
    # TODO stupid hack for initial moveset
    0: '--',

    1: 'm.pound',
    2: 'm.karate-chop',
    3: 'm.double-slap',
    4: 'm.comet-punch',
    5: 'm.mega-punch',
    6: 'm.pay-day',
    7: 'm.fire-punch',
    8: 'm.ice-punch',
    9: 'm.thunder-punch',
    10: 'm.scratch',
    11: 'm.vice-grip',
    12: 'm.guillotine',
    13: 'm.razor-wind',
    14: 'm.swords-dance',
    15: 'm.cut',
    16: 'm.gust',
    17: 'm.wing-attack',
    18: 'm.whirlwind',
    19: 'm.fly',
    20: 'm.bind',
    21: 'm.slam',
    22: 'm.vine-whip',
    23: 'm.stomp',
    24: 'm.double-kick',
    25: 'm.mega-kick',
    26: 'm.jump-kick',
    27: 'm.rolling-kick',
    28: 'm.sand-attack',
    29: 'm.headbutt',
    30: 'm.horn-attack',
    31: 'm.fury-attack',
    32: 'm.horn-drill',
    33: 'm.tackle',
    34: 'm.body-slam',
    35: 'm.wrap',
    36: 'm.take-down',
    37: 'm.thrash',
    38: 'm.double-edge',
    39: 'm.tail-whip',
    40: 'm.poison-sting',
    41: 'm.twineedle',
    42: 'm.pin-missile',
    43: 'm.leer',
    44: 'm.bite',
    45: 'm.growl',
    46: 'm.roar',
    47: 'm.sing',
    48: 'm.supersonic',
    49: 'm.sonic-boom',
    50: 'm.disable',
    51: 'm.acid',
    52: 'm.ember',
    53: 'm.flamethrower',
    54: 'm.mist',
    55: 'm.water-gun',
    56: 'm.hydro-pump',
    57: 'm.surf',
    58: 'm.ice-beam',
    59: 'm.blizzard',
    60: 'm.psybeam',
    61: 'm.bubble-beam',
    62: 'm.aurora-beam',
    63: 'm.hyper-beam',
    64: 'm.peck',
    65: 'm.drill-peck',
    66: 'm.submission',
    67: 'm.low-kick',
    68: 'm.counter',
    69: 'm.seismic-toss',
    70: 'm.strength',
    71: 'm.absorb',
    72: 'm.mega-drain',
    73: 'm.leech-seed',
    74: 'm.growth',
    75: 'm.razor-leaf',
    76: 'm.solar-beam',
    77: 'm.poison-powder',
    78: 'm.stun-spore',
    79: 'm.sleep-powder',
    80: 'm.petal-dance',
    81: 'm.string-shot',
    82: 'm.dragon-rage',
    83: 'm.fire-spin',
    84: 'm.thunder-shock',
    85: 'm.thunderbolt',
    86: 'm.thunder-wave',
    87: 'm.thunder',
    88: 'm.rock-throw',
    89: 'm.earthquake',
    90: 'm.fissure',
    91: 'm.dig',
    92: 'm.toxic',
    93: 'm.confusion',
    94: 'm.psychic',
    95: 'm.hypnosis',
    96: 'm.meditate',
    97: 'm.agility',
    98: 'm.quick-attack',
    99: 'm.rage',
    100: 'm.teleport',
    101: 'm.night-shade',
    102: 'm.mimic',
    103: 'm.screech',
    104: 'm.double-team',
    105: 'm.recover',
    106: 'm.harden',
    107: 'm.minimize',
    108: 'm.smokescreen',
    109: 'm.confuse-ray',
    110: 'm.withdraw',
    111: 'm.defense-curl',
    112: 'm.barrier',
    113: 'm.light-screen',
    114: 'm.haze',
    115: 'm.reflect',
    116: 'm.focus-energy',
    117: 'm.bide',
    118: 'm.metronome',
    119: 'm.mirror-move',
    120: 'm.self-destruct',
    121: 'm.egg-bomb',
    122: 'm.lick',
    123: 'm.smog',
    124: 'm.sludge',
    125: 'm.bone-club',
    126: 'm.fire-blast',
    127: 'm.waterfall',
    128: 'm.clamp',
    129: 'm.swift',
    130: 'm.skull-bash',
    131: 'm.spike-cannon',
    132: 'm.constrict',
    133: 'm.amnesia',
    134: 'm.kinesis',
    135: 'm.soft-boiled',
    136: 'm.high-jump-kick',
    137: 'm.glare',
    138: 'm.dream-eater',
    139: 'm.poison-gas',
    140: 'm.barrage',
    141: 'm.leech-life',
    142: 'm.lovely-kiss',
    143: 'm.sky-attack',
    144: 'm.transform',
    145: 'm.bubble',
    146: 'm.dizzy-punch',
    147: 'm.spore',
    148: 'm.flash',
    149: 'm.psywave',
    150: 'm.splash',
    151: 'm.acid-armor',
    152: 'm.crabhammer',
    153: 'm.explosion',
    154: 'm.fury-swipes',
    155: 'm.bonemerang',
    156: 'm.rest',
    157: 'm.rock-slide',
    158: 'm.hyper-fang',
    159: 'm.sharpen',
    160: 'm.conversion',
    161: 'm.tri-attack',
    162: 'm.super-fang',
    163: 'm.slash',
    164: 'm.substitute',
    165: 'm.struggle',
}


def unbank(*args):
    """Convert a "bank" identifier, XX:YYYY, to a real address.  The Game Boy
    is all about banks internally, and it's what pokered uses, so I've kept
    them intact in this file.

    The scheme is fairly simple:
    - XX is the bank; YYYY is an address.  Banks are 0x4000 bytes.
    - For bank 00, YYYY is already a real address, and should be between 0x0000
      and 0x4000.
    - For any other bank, YYYY is between 0x4000 and 0x8000, and they're just
      arranged in order.  So for bank 01, YYYY is already a real address; for
      bank 02, you add 0x4000; and so on.

    Accepts either two ints (XX and YYYY) or a string in the form 'XX:YYYY'.
    """
    if len(args) == 1:
        banked_address, = args
        banks, addrs = banked_address.split(':')
        bank = int(banks, 16)
        addr = int(addrs, 16)
    else:
        bank, addr = args

    if bank:
        assert 0x4000 <= addr < 0x8000
        return addr + (bank - 1) * 0x4000
    else:
        assert 0 <= addr < 0x4000
        return addr


def bank(addr):
    """Inverse of the above transformation."""
    if addr < 0x4000:
        return 0, addr
    bank, addr = divmod(addr, 0x4000)
    addr += 0x4000
    return bank, addr


JA_CHARMAP = dict(enumerate([
    # 0x
    # 00 appears at the beginning of a lot of Pokédex entries?
    "", "イ゛", "ヴ", "エ゛", "オ゛", "ガ", "ギ", "グ",
    "ゲ", "ゴ", "ザ", "ジ", "ズ", "ゼ", "ゾ", "ダ",
    # 1x
    "ヂ", "ヅ", "デ", "ド", "ナ゛", "ニ゛", "ヌ゛", "ネ゛",
    "ノ゛", "バ", "ビ", "ブ", "ボ", "マ゛", "ミ゛", "ム゛",
    # 2x
    "ィ゛", "あ゛", "い゛", "ゔ", "え゛", "お゛", "が", "ぎ",
    "ぐ", "げ", "ご", "ざ", "じ", "ず", "ぜ", "ぞ",
    # 3x
    "だ", "ぢ", "づ", "で", "ど", "な゛", "に゛", "ぬ゛",
    "ね゛", "の゛", "ば", "び", "ぶ", "べ", "ぼ", "ま゛",
    # 4x
    # 4F is the Pokédex newline
    # 4E is the dialogue newline (puts the cursor on the bottom line)
    "パ", "ピ", "プ", "ポ", "ぱ", "ぴ", "ぷ", "ぺ",
    "ぽ", "\f", "が　", "も゜", "�", "�", "\n", "\n",
    # 5x
    # 50 is the string terminator, represented by @ in pokered
    # 51 prompts for a button press, then clears the screen
    # 52 is the player's name
    # 53 is the rival's name
    # 55 prompts for a button press, then scrolls up one line
    # 57 ends dialogue, invisibly
    # 58 ends dialogue, visibly
    # 59 is the inactive Pokémon in battle
    # 5A is the active Pokémon in battle
    # 5F marks the end of a Pokédex entry, which automaticaly adds a period
    "@", "�", "�", "�", "ポケモン", "�", "……", "�",
    "�", "�", "�", "パソコン", "わざマシン", "トレーナー", "ロケットだん", "。",
    # 6x
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "V", "S", "L", "M", "：", "ぃ", "ぅ",
    # 7x
    # 79 - 7E are the TL, T/B, TR, L/R, BL, and BR of the text box
    "「", "」", "『", "』", "・", "…", "ぁ", "ぇ",
    "ぉ", "╔", "═", "╗", "║", "╚", "╝", "　",
    # 8x
    "ア", "イ", "ウ", "エ", "オ", "カ", "キ", "ク",
    "ケ", "コ", "サ", "シ", "ス", "セ", "ソ", "タ",
    # 9x
    "チ", "ツ", "テ", "ト", "ナ", "ニ", "ヌ", "ネ",
    "ノ", "ハ", "ヒ", "フ", "ホ", "マ", "ミ", "ム",
    # Ax
    "メ", "モ", "ヤ", "ユ", "ヨ", "ラ", "ル", "レ",
    "ロ", "ワ", "ヲ", "ン", "ッ", "ャ", "ュ", "ョ",
    # Bx
    "ィ", "あ", "い", "う", "え", "お", "か", "き",
    "く", "け", "こ", "さ", "し", "す", "せ", "そ",
    # Cx
    "た", "ち", "つ", "て", "と", "な", "に", "ぬ",
    "ね", "の", "は", "ひ", "ふ", "へ", "ほ", "ま",
    # Dx
    "み", "む", "め", "も", "や", "ゆ", "よ", "ら",
    "り", "る", "れ", "ろ", "わ", "を", "ん", "っ",
    # Ex
    "ゃ", "ゅ", "ょ", "ー", "゜", "゛", " ?", " !",
    "。", "ァ", "ゥ", "ェ", "▷", "▶", "▼", "♂",
    # Fx
    "円", "×", ".", "/", "ォ", "♀", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9",
]))

EN_CHARMAP = dict(enumerate([
    # 0x0X
    "", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x1X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x2X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x3X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 4x
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "\f", "�", "�", "�", "�", "\n", "\n",
    # 5x
    "@", "�", "�", "�", "POKé", "�", "……", "�",
    "�", "�", "�", "PC", "TM", "TRAINER", "ROCKET", ".",
    # 6x
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "V", "S", "L", "M", ":", "ぃ", "ぅ",
    # 7x
    "‘", "’", "“", "”", "・", "…", "ぁ", "ぇ",
    "ぉ", "╔", "═", "╗", "║", "╚", "╝", " ",
    # 8x
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "J", "K", "L", "M", "N", "O", "P",
    # 9x
    "Q", "R", "S", "T", "U", "V", "W", "X",
    "Y", "Z", "(", ")", " :", " ;", "[", "]",
    # Ax
    "a", "b", "c", "d", "e", "f", "g", "h",
    "i", "j", "k", "l", "m", "n", "o", "p",
    # Bx
    "q", "r", "s", "t", "u", "v", "w", "x",
    "y", "z", "é", "ʼd", "ʼl", "ʼs", "ʼt", "ʼv",
    # Cx
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # Dx
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # Ex
    "'", "ᴾₖ", "ᴹₙ", "-", "ʼr", "ʼm", " ?", " !",
    ".", "ァ", "ゥ", "ェ", "▷", "▶", "▼", "♂",
    # Fx
    # F0 is the currency symbol; this is the ruble sign, close enough
    "₽", "×", ".", "/", ",", "♀", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9",
]))

# ty, tachyon
DE_FR_CHARMAP = dict(enumerate([
    # 0x0X
    "", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x1X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x2X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x3X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 4x
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "\f", "�", "�", "�", "�", "\n", "\n",
    # 5x
    "@", "�", "�", "�", "POKé", "�", "……", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x6X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x7X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", " ",
    # 0x8X
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "J", "K", "L", "M", "N", "O", "P",
    # 0x9X
    "Q", "R", "S", "T", "U", "V", "W", "X",
    "Y", "Z", "(", ")", ":", ";", "[", "]",
    # 0xAX
    "a", "b", "c", "d", "e", "f", "g", "h",
    "i", "j", "k", "l", "m", "n", "o", "p",
    # 0xBX
    "q", "r", "s", "t", "u", "v", "w", "x",
    "y", "z", "à", "è", "é", "ù", "ß", "ç",
    # 0xCX
    "Ä", "Ö", "Ü", "ä", "ö", "ü", "ë", "ï",
    "â", "ô", "û", "ê", "î", "�", "�", "�",
    # 0xDX
    "�", "�", "�", "�", "cʼ", "dʼ", "jʼ", "lʼ",
    "mʼ", "nʼ", "pʼ", "sʼ", "ʼs", "tʼ", "uʼ", "yʼ",
    # 0xEX
    "'", "ᴾₖ", "ᴹₙ", "-", "¿", "¡", "?", "!",
    ".", "ァ", "ゥ", "ェ", "▹", "▸", "▾", "♂",
    # 0xFX
    "$", "×", ".", "/", ",", "♀", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9",
]))

ES_IT_CHARMAP = dict(enumerate([
    # 0x0X
    "", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x1X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x2X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x3X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 4x
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "\f", "�", "�", "�", "�", "\n", "\n",
    # 5x
    "@", "�", "�", "�", "POKé", "�", "……", "�",
    "�", "�", "�", "�", "�", "�", "�", ".",
    # 0x6X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x7X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", " ",
    # 0x8X
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "J", "K", "L", "M", "N", "O", "P",
    # 0x9X
    "Q", "R", "S", "T", "U", "V", "W", "X",
    "Y", "Z", "(", ")", ":", ";", "[", "]",
    # 0xAX
    "a", "b", "c", "d", "e", "f", "g", "h",
    "i", "j", "k", "l", "m", "n", "o", "p",
    # 0xBX
    "q", "r", "s", "t", "u", "v", "w", "x",
    "y", "z", "à", "è", "é", "ù", "À", "Á",
    # 0xCX
    "Ä", "Ö", "Ü", "ä", "ö", "ü", "È", "É",
    "Ì", "Í", "Ñ", "Ò", "Ó", "Ù", "Ú", "á",
    # 0xDX
    "ì", "í", "ñ", "ò", "ó", "ú", "º", "&",
    "ʼd", "ʼl", "ʼm", "ʼr", "ʼs", "ʼt", "ʼv", " ",
    # 0xEX
    "'", "ᴾₖ", "ᴹₙ", "-", "¿", "¡", "?", "!",
    ".", "ァ", "ゥ", "ェ", "▹", "▸", "▾", "♂",
    # 0xFX
    "$", "×", ".", "/", ",", "♀", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9",
]))

CHARACTER_MAPS = dict(
    ja=JA_CHARMAP,
    en=EN_CHARMAP,
    es=ES_IT_CHARMAP,
    it=ES_IT_CHARMAP,
    de=DE_FR_CHARMAP,
    fr=DE_FR_CHARMAP,
)


class PokemonString:
    """A string encoded using the goofy Gen I scheme."""
    def __init__(self, raw):
        self.raw = raw

    def decrypt(self, language):
        try:
            charmap = CHARACTER_MAPS[language]
        except KeyError:
            raise ValueError("Not a known language: {!r}".format(language))

        return ''.join(
            charmap.get(ch, '�') for ch in self.raw)


class PokemonCString(Adapter):
    """Construct thing for `PokemonString`."""
    def __init__(self, length=None):
        # No matter which charmap, the "end of string" character is always
        # encoded as P
        if length is None:
            subcon = CString(terminators=b'P')
        else:
            subcon = String(length, padchar=b'P')
        super().__init__(subcon)

    def _encode(self, obj, context):
        raise NotImplementedError

    def _decode(self, obj, context):
        return PokemonString(obj)


class MacroPokemonCString(Construct):
    """Similar to the above, but for strings that may contain the 0x17 "far
    load" macro, whose parameters may in turn contain the NUL byte 0x50 without
    marking the end of the string.  Yikes."""
    def _parse(self, stream, context, path):
        buf = bytearray()
        while True:
            byte, = stream.read(1)
            if byte == 0x17:
                # "Far load"
                addr_lo, addr_hi, bank = stream.read(3)
                offset = unbank(bank, addr_lo + addr_hi * 256)
                pos = stream.tell()
                try:
                    stream.seek(offset)
                    buf.extend(self._parse(stream, context, path).raw)
                finally:
                    stream.seek(pos)
            elif byte == 0x50:
                break
            elif byte == 0x5F:
                # 5F ends a Pokédex entry
                buf.append(byte)
                break
            else:
                buf.append(byte)

        return PokemonString(bytes(buf))


class NullTerminatedArray(Subconstruct):
    _peeker = Peek(Int8ul)
    __slots__ = ()

    def _parse(self, stream, context, path):
        from construct.lib import ListContainer
        obj = ListContainer()
        while True:
            nextbyte = self._peeker.parse_stream(stream)
            if nextbyte == 0:
                break

            # TODO what if we hit the end of the stream
            obj.append(self.subcon._parse(stream, context, path))

        # Consume the trailing zero
        stream.read(1)

        return obj

    def _build(self, obj, stream, context):
        raise NotImplementedError

    # TODO ???
    #def _sizeof(self, context):

def IdentEnum(subcon, mapping):
    return Enum(subcon, **{v: k for (k, v) in mapping.items()})



# Game Boy header, at 0x0100
# http://gbdev.gg8.se/wiki/articles/The_Cartridge_Header
# TODO hey!  i wish i had a little cli entry point that would spit this out for a game.  and do other stuff like scan for likely pokemon text or graphics.  that would be really cool in fact.  maybe put this in a gb module and make that exist sometime.
game_boy_header_struct = Struct(
    # Entry point for the game; generally contains a jump to 0x0150
    'entry_point' / String(4),
    # Nintendo logo; must be exactly this or booting will not continue
    'nintendo_logo' / Const(
        bytes.fromhex("""
            CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D
            00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99
            BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E
        """.replace('\n', '')),
    ),
    'title' / Bytes(11),
    'manufacturer_code' / Bytes(4),
    'cgb_flag' / Int8ul,
    'new_licensee_code' / Bytes(2),
    'sgb_flag' / Int8ul,  # 3 for super game boy support
    'cartridge_type' / Int8ul,
    'rom_size' / Int8ul,
    'ram_size' / Int8ul,
    'region_code' / Int8ul,  # 0 for japan, 1 for not japan
    'old_licensee_code' / Int8ul,  # 0x33 means to use licensee_code
    'game_version' / Int8ul,
    'header_checksum' / Int8ul,
    'cart_checksum' / Int16ub,
)


# The mother lode — Pokémon base stats
pokemon_struct = Struct(
    'pokedex_number' / Byte,
    'base_hp' / Byte,
    'base_attack' / Byte,
    'base_defense' / Byte,
    'base_speed' / Byte,
    'base_special' / Byte,
    'type1' / IdentEnum(Byte, TYPE_IDENTIFIERS),
    'type2' / IdentEnum(Byte, TYPE_IDENTIFIERS),
    'catch_rate' / Byte,
    'base_experience' / Byte,
    # TODO ????  "sprite dimensions"
    '_sprite_dimensions' / Byte,
    'front_sprite_pointer' / Int16ul,
    'back_sprite_pointer' / Int16ul,
    # TODO somehow rig this to discard trailing zeroes; there's a paddedstring that does it
    'initial_moveset' / Array(4, IdentEnum(Byte, MOVE_IDENTIFIERS)),
    'growth_rate' / IdentEnum(Byte, GROWTH_RATES),
    'machines' / BitsSwapped(Bitwise(Array(7 * 8, Flag))),
    Padding(1),
)


evos_moves_struct = Struct(
    'evolutions' / NullTerminatedArray(
        Struct(
            'evo_trigger' / IdentEnum(Byte, EVOLUTION_TRIGGERS),
            'evo_arguments' / Embedded(Switch(
                lambda ctx: ctx.evo_trigger, {
                    'ev.level-up': Struct(
                        'evo_level' / Byte,
                    ),
                    'ev.use-item': Struct(
                        # TODO item enum too wow!
                        'evo_item' / Byte,
                        # TODO ??? always seems to be 1
                        'evo_level' / Byte,
                    ),
                    # TODO ??? always seems to be 1 here too
                    'ev.trade': Struct(
                        'evo_level' / Byte,
                    ),
                },
            )),
            # TODO alas, the species here is a number, because it's an internal
            # id and we switch those back using data from the game...
            'evo_species' / Byte,
        ),
    ),
    'level_up_moves' / NullTerminatedArray(
        Struct(
            'level' / Byte,
            'move' / IdentEnum(Byte, MOVE_IDENTIFIERS),
            '_end' / Peek(Byte),  # TODO what, what is this
        ),
    ),
)
evos_moves_pointer = Struct(
    'offset' / Int16ul,
    # TODO hardcoded as the same bank, ugh
    'evos_moves' / Pointer(lambda ctx: ctx.offset + (0xE - 1) * 0x4000, evos_moves_struct),
)

# There are actually two versions of this struct...  an imperial one, used by
# the US, and a metric one, used by the ENTIRE REST OF THE WORLD.  The imperial
# one has separate bytes for feet and inches, so it's a different size, making
# it completely incompatible.
pokedex_flavor_struct_metric = Struct(
    'genus' / PokemonCString(),
    'height_decimeters' / Int8ul,
    'weight_hectograms' / Int16ul,
    'flavor_text' / MacroPokemonCString(),
)
pokedex_flavor_struct_imperial = Struct(
    'genus' / PokemonCString(),
    'height_feet' / Int8ul,
    'height_inches' / Int8ul,
    'weight_decipounds' / Int16ul,
    'flavor_text' / MacroPokemonCString(),
)


class CartDetectionError(Exception):
    pass


class RBYCart:
    NUM_POKEMON = 151
    NUM_MOVES = 165
    NUM_MACHINES = 55

    def __init__(self, path):
        with path.open('rb') as f:
            self.data = f.read()
        self.stream = io.BytesIO(self.data)
        self.path = path

        # Scrape these first; language detection relies on examining text
        self.addrs = self.detect_addresses()

        self.game, self.language = self.detect_game()
        self.uses_metric = not self.language == 'en'

        # And snag this before anything else happens; prevents some silly
        # problems where a reified property seeks, then tries to read this, and
        # it ends up seeking again
        self.max_pokemon_index

    def detect_addresses(self):
        """The addresses of some important landmarks can vary between versions
        and languages.  Attempt to detect them automatically.

        Return a dict of raw file offsets.  The keys are the names used in the
        pokered project.
        """
        # The ideal approach is to find some assembly code that appears just
        # before the data of interest.  It's pretty hacky, but since
        # translators (and even modders) would have little reason to rearrange
        # functions or inject new ones in these odd places, it ought to work
        # well enough.  And it's better than ferreting out and hard-coding
        # piles of addresses.
        # The only hard part is that assembly code that contains an address
        # won't work, since that address will also vary per game.
        # Each of the landmarks used here appears in every official cartridge
        # exactly once.
        addresses = {}

        # This is an entire function used by the Pokédex and which immediately
        # precedes all the flavor text.
        asm_DrawTileLine = bytes.fromhex('c5d5 7019 0d20 fbd1 c1c9')
        try:
            idx = self.data.index(asm_DrawTileLine)
        except ValueError:
            raise CartDetectionError("Can't find flavor text pointers")
        addresses['PokedexEntryPointers'] = idx + len(asm_DrawTileLine)


        match = find_code(self.data, '''
        ;EvolutionAfterBattle:
            ldh a, [#hTilesetType]
            push af
            xor a
            ld [#wEvolutionOccurred], a
            dec a
            ld [#wWhichPokemon], a
            push hl
            push bc
            push de
            ld hl, #wPartyCount
            push hl

        ;Evolution_PartyMonLoop: ; loop over party mons
            ld hl, #wWhichPokemon
            inc [hl]
            pop hl
            inc hl
            ld a, [hl]
            cp $ff ; have we reached the end of the party?
            jp z, #_done
            ld [#wEvoOldSpecies], a
            push hl
            ld a, [#wWhichPokemon]
            ld c, a
            ld hl, #wCanEvolveFlags
            ld b, #FLAG_TEST
            call #Evolution_FlagAction
            ld a, c
            and a ; is the mon's bit set?
            jp z, #Evolution_PartyMonLoop ; if not, go to the next mon
            ld a, [#wEvoOldSpecies]
            dec a
            ld b, 0
            ld hl, #EvosMovesPointerTable
            add a, a
            rl b
            ld c, a
            add hl, bc
            ld a, [hl+]
            ld h, [hl]
            ld l, a
            push hl
            ld a, [#wcf91]
            push af
            xor a ; PLAYER_PARTY_DATA
            ld [#wMonDataLocation], a
            call #LoadMonData
            pop af
            ld [#wcf91], a
            pop hl
        ''',
            hTilesetType=0xD7,  # FFD7
        )
        if not match:
            raise CartDetectionError("Can't find evolution and moveset table")
        rem, inputs = match
        # As usual, there's no bank given...  but this code has to be in the
        # same bank as the data it loads!
        codebank, _ = bank(rem.start())
        addresses['EvosMovesPointerTable'] = unbank(
            codebank, inputs['EvosMovesPointerTable'])

        # Several lists of names are accessed by a single function, which looks
        # through a list of pointers to find the right set of names to use.
        # That's great news for me: I can just grab all of those delicious
        # pointers at once.  Here's an excerpt from GetName.
        match = find_code(self.data, '''
            inc d
            ;.skip
            ld hl, #NamePointers
            add hl,de
            ld a,[hl+]
            ldh [$96],a
            ld a,[hl]
            ldh [$95],a
            ldh a,[$95]
            ld h,a
            ldh a,[$96]
            ld l,a
            ld a,[#wd0b5]
            ld b,a
            ld c,0
            ;.nextName
            ld d,h
            ld e,l
            ;.nextChar
            ld a,[hl+]
            cp $50  ; terminator @, encoded
        ''')
        if not match:
            raise CartDetectionError("Can't find name array")
        rem, inputs = match
        start = inputs['NamePointers']
        name_pointers = Array(7, Int16ul).parse(
            self.data[start:start + 14])
        # One downside to the Game Boy memory structure is that banks are
        # not stored anywhere near their corresponding addresses.  Most
        # bank numbers are hardcoded here, but Pokémon names are in a different
        # bank in Japanese games, so we've gotta scrape the bank too...
        match = find_code(self.data, '''
        ;GetMonName::
            push hl
            ldh a,[#H_LOADEDROMBANK]
            push af
            ld a,#BANK_MonsterNames
        ''',
            H_LOADEDROMBANK=0xB8,  # full address is $FFB8; ldh adds the $FF
            MBC1RomBank=0x2000,
            MonsterNames=name_pointers[0]
        )
        if not match:
            raise CartDetectionError("Can't find Pokémon names")
        rem, inputs = match

        addresses['MonsterNames'] = unbank(
            inputs['BANK_MonsterNames'], name_pointers[0])
        addresses['MoveNames'] = unbank(0x2C, name_pointers[1])
        # 2: UnusedNames  (unused, obviously)
        addresses['ItemNames'] = unbank(0x01, name_pointers[3])
        # 4: wPartyMonOT  (only useful while the game is running)
        # 5: wEnemyMonOT  (only useful while the game is running)
        addresses['TrainerNames'] = unbank(0x0E, name_pointers[6])

        # Finding TMs is a bit harder.  They come right after a function for
        # looking up a TM number, which is very short and very full of
        # addresses.  So here's a regex.
        # `wd11e` is some address used all over the game for passing arguments
        # around, which unfortunately also differs from language to language.
        # In English it is, unsurprisingly, 0xD11E.
        # `TechnicalMachines` is the address we're looking for, which should
        # immediately follow what this matches.
        match = find_code(self.data, '''
            ld a, [#wd11e]
            dec a
            ld hl, #TechnicalMachines
            ld b, $0
            ld c, a
            add hl, bc
            ld a, [hl]
            ld [#wd11e], a
            ret
        ''')
        if match:
            rem, inputs = match
            # TODO this should mayybe also check that the address immediately follows this code
            matched_addr = inputs['TechnicalMachines']
            tentative_addr = rem.end()
            # Remember, addresses don't include the bank!
            _, banked_addr = bank(tentative_addr)
            if matched_addr == banked_addr:
                asm_wd11e_addr = inputs['wd11e']
                addresses['TechnicalMachines'] = tentative_addr
            else:
                raise RuntimeError
            # TODO should there really be more than one match?
        else:
            raise CartDetectionError("Can't find technical machines list")

        # Pokédex order is similarly tricky.  Much like the above, this
        # function converts a Pokémon's game index to its national dex number.
        # These are almost immediately after the Pokédex entries themselves,
        # but this actually seems easier than figuring out where a table of
        # pointers ends.
        match = find_code(self.data, '''
            push bc
            push hl
            ld a, [#wd11e]
            dec a
            ld hl, #PokedexOrder
            ld b, 0
            ld c, a
            add hl, bc
            ld a, [hl]
            ld [#wd11e], a
            pop hl
            pop bc
            ret
        ''', wd11e=asm_wd11e_addr)
        if match:
            rem, inputs = match
            matched_addr = inputs['PokedexOrder']
            tentative_addr = rem.end()
            # Remember, addresses don't include the bank!
            _, banked_addr = bank(tentative_addr)
            if matched_addr == banked_addr:
                addresses['PokedexOrder'] = tentative_addr
            else:
                raise RuntimeError
        else:
            raise CartDetectionError("Can't find Pokédex order")

        # Ah, but then, we have base stats.  These don't have code nearby;
        # they're just stuck immediately after moves.  Except in R/G, where
        # they appear /before/ moves!  And we don't know what version we're
        # running yet, because the addresses detected in this method are used
        # for language detection.  Hmm.
        # Here's plan B: look for the function that /loads/ base stats, and
        # scrape the address out of it.  This function is a bit hairy; I've had
        # to expand some of pokered's macros and rewrite the jumps to something
        # that the rudimentary code matcher can understand.  Also, there were
        # two edits made in Yellow: bank switching is done with a function
        # rather inlined, and Mew is no longer separate.
        # TODO i guess it would be nice if find_code could deal with this,
        # seeing as it IS just a regex, but i don't know how i'd cram the
        # syntax in without a real parser™
        rgb_bits = dict(
            bankswitch="""
                ldh [#H_LOADEDROMBANK], a
                ld [#MBC1RomBank], a
            """,
            mewjump="""
                cp #MEW
                jr z,#mew
            """,
            mewblock="""
                jr #done2
                ;.mew
                ld hl, #MewBaseStats
                ld de, #wMonHeader
                ld bc, #MonBaseStatsLength
                ld a, #BANK_MewBaseStats
                call #FarCopyData
            """,
        )
        yellow_bits = dict(
            bankswitch="""
                call #BankswitchCommon
            """,
            mewjump="",
            mewblock="",
        )
        for bits in (rgb_bits, yellow_bits):
            code = '''
                ldh a, [#H_LOADEDROMBANK]
                push af
                ld a, #BANK_BaseStats
                {bankswitch}
                push bc
                push de
                push hl
                ld a, [#wd11e]
                push af
                ld a,[#wd0b5]
                ld [#wd11e],a
                ld de,#FossilKabutopsPic
                ld b,$66 ; size of Kabutops fossil and Ghost sprites
                cp #FOSSIL_KABUTOPS ; Kabutops fossil
                jr z,#specialID1
                ld de,#GhostPic
                cp #MON_GHOST ; Ghost
                jr z,#specialID2
                ld de,#FossilAerodactylPic
                ld b,$77 ; size of Aerodactyl fossil sprite
                cp #FOSSIL_AERODACTYL ; Aerodactyl fossil
                jr z,#specialID3
                {mewjump}
                ld a, #IndexToPokedexPredef
                call #IndexToPokedex   ; convert pokemon ID in [wd11e] to pokedex number
                ld a,[#wd11e]
                dec a
                ld bc, #MonBaseStatsLength
                ld hl, #BaseStats
                call #AddNTimes
                ld de, #wMonHeader
                ld bc, #MonBaseStatsLength
                call #CopyData
                jr #done1
                ;.specialID
                ld hl, #wMonHSpriteDim
                ld [hl], b ; write sprite dimensions
                inc hl
                ld [hl], e ; write front sprite pointer
                inc hl
                ld [hl], d
                {mewblock}
            '''.format(**bits)

            match = find_code(
                self.data,
                code,
                # These are constants; I left them in the above code for clarity
                H_LOADEDROMBANK=0xB8,  # full address is $FFB8; ldh adds the $FF
                MBC1RomBank=0x2000,
                # This was scraped previously
                wd11e=asm_wd11e_addr,
            )
            if match:
                rem, inputs = match
                addresses['BaseStats'] = unbank(
                    inputs['BANK_BaseStats'], inputs['BaseStats'])
                if 'MewBaseStats' in inputs:
                    addresses['MewBaseStats'] = unbank(
                        inputs['BANK_MewBaseStats'], inputs['MewBaseStats'])
                else:
                    addresses['MewBaseStats'] = None
                break
        else:
            raise CartDetectionError("Can't find base stats")

        return addresses

    def detect_game(self):
        """Given a cart image, return the game and language.

        This is a high-level interface; it prints stuff to stdout and raises
        exceptions.  Its two helpers do not.
        """
        # TODO raise, don't print to stdout
        # We have checksums for each of the games, but we also want to support
        # a heuristic so this same code can be used for trimmed carts,
        # bootlegs, fan hacks, corrupted carts, and other interesting variants.
        # Try both, and warn if they don't agree.
        game_c, language_c = self.detect_game_checksum()
        game_h, language_h = self.detect_game_heuristic()
        game = game_c or game_h
        language = language_c or language_h
        if game and language:
            print("Detected {filename} as {game}, {language}".format(
                filename=self.path.name, game=game, language=language))
        else:
            print("Can't figure out what game {filename} is!  ".format(
                filename=self.path.name), end='')
            if game:
                # TODO should probably be a way to override this
                print("It seems to be {}, but I can't figure out the language.".format(game))
            elif language:
                print("It seems to use {} text, but I can't figure out the version.".format(language))
            else:
                print("Nothing about it is familiar to me.")
            print("Bailing, sorry  :(")
            sys.exit(1)

        # Warn about a potentially bad checksum
        if not game_c or not language_c:
            log.warn(
                "Hmm.  I don't recognize the checksum for %s, but I'll "
                "continue anyway.",
                self.path.name)
        elif game_c != game_h or language_c != language_h:
            log.warn(
                "This is very surprising.  The checksum indicates that this "
                "game should be %s, %s, but I detected it as %s, %s.  Probably "
                "my fault, not yours.  Continuing anyway.",
                game_c, language_c, game_h, language_h)

        return game, language

    def detect_game_checksum(self):
        h = hashlib.md5()
        h.update(self.data)
        md5sum = h.hexdigest()

        return GAME_RELEASE_MD5SUM_INDEX.get(md5sum, (None, None))

    def detect_game_heuristic(self):
        # Okay, so, fun story: there's nothing /officially/ distinguishing the
        # games.  There's a flag in the cartridge header that's 0 for Japan and
        # 1 for anywhere other than Japan, but every copy of the game I've seen
        # has it set to anything other than 0 or 1, so that doesn't seem
        # particularly reliable.  I can't find any official and documented
        # difference.  It's as if they just changed the text, reassembled, and
        # called it a day.  In fact that's probably exactly what happened.

        # That makes life a little more difficult, so let's take this a step at
        # a time.  We can get the name of the game for free, at least, from the
        # cartridge header.
        self.stream.seek(0x100)
        header = game_boy_header_struct.parse_stream(self.stream)
        # Nintendo decided to lop off the last five bytes of the title for
        # other purposes /after/ creating the Game Boy, so the last three
        # letters of e.g.  POKEMON YELLOW end up in the manufacturer code.
        # Let's just, ah, put those back on.
        title = header.title + header.manufacturer_code.rstrip(b'\x00')
        if title == b'POKEMON RED':
            version = 'red'
        elif title == b'POKEMON GREEN':
            version = 'green'
        elif title == b'POKEMON BLUE':
            version = 'blue'
        elif title == b'POKEMON YELLOW':
            version = 'yellow'
        else:
            version = None

        # There's still a problem here: "red" might mean the Red from
        # Red/Green, released only in Japan; or the Red from Red/Blue, the pair
        # released worldwide, based on Japanese Blue.
        # Easy way to tell: Red and Green are the only games in the entire
        # series to use a half megabyte cartridge.  Any other game, even if
        # trimmed, will be just barely too big to fit in that size.
        if header.rom_size == 4:  # 512K -> Red/Green
            if version == 'red':
                game = 'jp-red'
            elif version == 'green':
                game = 'jp-green'
            else:
                # No other game is this size
                game = None
        elif header.rom_size == 5:  # 1M -> Red/Blue/Yellow
            if version == 'green':
                # Doesn't make sense; there was no green game bigger than 512K
                game = None
            elif version == 'red':
                game = 'ww-red'
            elif version == 'blue':
                # Can't know which Blue this is until we get the language
                game = None
            else:
                game = version
        else:  # ???
            return None, None

        # Now for language.  If the game is Japanese Red or Green, then it must
        # be in Japanese, so we're done.
        if game in ('jp-red', 'jp-green'):
            language = 'ja'
            return game, language

        # Otherwise, the only way to be absolutely sure is to find some text
        # and see what language it's in.
        self.stream.seek(self.addrs['ItemNames'])
        # Item 0 is MASTER BALL.  The first item with a different name in every
        # single language is item 4, TOWN MAP, so chew through five names.
        single_string_struct = PokemonCString()
        for _ in range(5):
            name = single_string_struct.parse_stream(self.stream)

        for language, expected_name in [
                ('de', 'KARTE'),
                ('en', 'TOWN MAP'),
                ('es', 'MAPA PUEBLO'),
                ('fr', 'CARTE'),
                ('it', 'MAPPA CITTÀ'),
                ('ja', 'タウンマップ'),
            ]:
            if name.decrypt(language) == expected_name:
                break
        else:
            # TODO raise probably
            language = None

        # Blue is a special case, remember
        if game is None and version == 'blue':
            if language is None:
                pass
            elif language == 'ja':
                game = 'jp-blue'
            else:
                game = 'ww-blue'

        # And done!
        return game, language

    ### From here it's all reified properties that extract on demand

    @reify
    def pokedex_order(self):
        """Maps internal Pokémon indices to the more familiar Pokédex order.

        Note that this maps to ONE LESS THAN National Dex number, so lists
        can be zero-indexed.
        """
        # Fetch the conversions between internal numbering and Pokédex order,
        # because that's a thing Gen 1 does, for some reason.
        self.stream.seek(self.addrs['PokedexOrder'])
        # I don't know exactly how many numbers are in this array, but it's
        # more than the number of Pokémon, because there are some MISSINGNO
        # gaps.  It's single bytes anyway, so I'm going to keep reading them
        # until I've seen every valid dex number.
        unseen_dex_numbers = set(range(1, self.NUM_POKEMON + 1))
        internal_to_dex_order = {}
        for index, dex_number in enumerate(self.stream.read(256), start=1):
            if dex_number == 0:
                continue
            internal_to_dex_order[index] = dex_number - 1
            unseen_dex_numbers.remove(dex_number)

            if not unseen_dex_numbers:
                break
        assert not unseen_dex_numbers
        return internal_to_dex_order

    @reify
    def max_pokemon_index(self):
        """Largest valid value of a Pokémon index.  Note that not every index
        between 0 and this number is necessarily a valid Pokémon; many of them
        are Missingno.  Only numbers that appear in `pokedex_order` are legit.
        """
        return max(self.pokedex_order)

    @reify
    def pokemon_names(self):
        """List of Pokémon names, in Pokédex order."""
        ret = [None] * self.NUM_POKEMON

        self.stream.seek(self.addrs['MonsterNames'])
        # TODO i don't like this, but they don't have explicit terminators...
        if self.language == 'ja':
            name_length = 5
        else:
            name_length = 10
        for index, pokemon_name in enumerate(Array(self.max_pokemon_index, PokemonCString(name_length)).parse_stream(self.stream), start=1):
            try:
                id = self.pokedex_order[index]
            except KeyError:
                continue
            ret[id] = pokemon_name.decrypt(self.language)

        return ret

    @reify
    def machine_moves(self):
        """List of move identifiers corresponding to TMs/HMs."""
        self.stream.seek(self.addrs['TechnicalMachines'])
        return Array(self.NUM_MACHINES, IdentEnum(Byte, MOVE_IDENTIFIERS)).parse_stream(self.stream)

    @reify
    def pokemon_records(self):
        """List of pokemon_structs."""
        self.stream.seek(self.addrs['BaseStats'])
        # Mew's data is, awkwardly, stored separately pre-Yellow
        if self.addrs['MewBaseStats']:
            records = Array(self.NUM_POKEMON - 1, pokemon_struct).parse_stream(self.stream)
            self.stream.seek(self.addrs['MewBaseStats'])
            records.append(pokemon_struct.parse_stream(self.stream))
        else:
            records = Array(self.NUM_POKEMON, pokemon_struct).parse_stream(self.stream)

        return records

    @reify
    def pokemon_evos_and_moves(self):
        """List of evos_moves_structs, including both evolutions and level-up
        moves.
        """
        ret = [None] * self.NUM_POKEMON
        self.stream.seek(self.addrs['EvosMovesPointerTable'])
        for index, pointer in enumerate(Array(self.max_pokemon_index, evos_moves_pointer).parse_stream(self.stream), start=1):
            try:
                id = self.pokedex_order[index]
            except KeyError:
                continue

            ret[id] = pointer.evos_moves
        return ret

    @reify
    def pokedex_entries(self):
        """List of pokedex_flavor_structs."""
        ret = [None] * self.NUM_POKEMON
        dex_bank, _ = bank(self.addrs['PokedexEntryPointers'])
        if self.uses_metric:
            pokedex_flavor_struct = pokedex_flavor_struct_metric
        else:
            pokedex_flavor_struct = pokedex_flavor_struct_imperial

        self.stream.seek(self.addrs['PokedexEntryPointers'])
        # This address is just an array of pointers
        for index, address in enumerate(Array(self.max_pokemon_index, Int16ul).parse_stream(self.stream), start=1):
            try:
                id = self.pokedex_order[index]
            except KeyError:
                continue

            self.stream.seek(unbank(dex_bank, address))
            ret[id] = pokedex_flavor_struct.parse_stream(self.stream)

        return ret

    @reify
    def move_names(self):
        self.stream.seek(self.addrs['MoveNames'])
        return Array(self.NUM_MOVES, PokemonCString()).parse_stream(self.stream)


# TODO this is not correctly using my half-baked "slice" idea
class WriterWrapper:
    def __init__(self, locus, language):
        self.__dict__.update(dict(
            locus=locus,
            language=language,
        ))

    def __setattr__(self, key, value):
        # TODO yeah this is fucking ludicrous
        attr = type(self.locus).__dict__[key]
        # TODO i think my descriptor stuff needs some work here if i have to root around in __dict__
        if isinstance(attr, schema._Localized):
            if key not in self.locus.__dict__:
                langdict = {}
                setattr(self.locus, key, langdict)
            else:
                langdict = getattr(self.locus, key)
            langdict[self.language] = value
        else:
            if key in self.locus.__dict__:
                oldvalue = getattr(self.locus, key)
                if value != oldvalue:
                    raise ValueError(
                        "Trying to set {!r}'s {} to {!r}, but it already "
                        "has a different value: {!r}"
                        .format(self.locus, key, value, oldvalue))

            setattr(self.locus, key, value)


def main(base_root):
    # TODO does this need to take arguments?  or like, sprite mode i guess
    carts = defaultdict(dict)  # game => language => RBYCart
    for filename in sys.argv[1:]:
        cart = RBYCart(Path(filename))
        game_carts = carts[cart.game]
        if cart.language in game_carts:
            print(
                "WARNING: ignoring {0.path} because it's the same game and "
                "language ({0.game}, {0.language}) as {1.path}"
                .format(cart, game_carts[cart.language]))
            continue
        game_carts[cart.language] = cart

    for game, game_carts in sorted(carts.items()):
        print()
        print("Dumping", game)
        if game in GAME_RELEASE_MD5SUMS:
            got_languages = game_carts.keys()
            expected_languages = GAME_RELEASE_MD5SUMS[game].keys()
            extra_languages = got_languages - expected_languages
            if extra_languages:
                print(
                    "WARNING: don't recognize languages {}"
                    .format(', '.join(sorted(extra_languages))))

            missing_languages = expected_languages - got_languages
            if missing_languages:
                print(
                    "WARNING: missing cartridges for {} — this dump will "
                    "be incomplete!"
                    .format(', '.join(sorted(missing_languages))))

        root = base_root / game
        root.mkdir(exist_ok=True)

        pokemons = None
        for language, cart in sorted(game_carts.items()):
            if pokemons is None:
                pokemons = OrderedDict([
                    (POKEMON_IDENTIFIERS[id + 1], schema.Pokemon())
                    for id in range(cart.NUM_POKEMON)
                ])

            for id in range(cart.NUM_POKEMON):
                pokemon = pokemons[POKEMON_IDENTIFIERS[id + 1]]
                writer = WriterWrapper(pokemon, language)

                writer.name = cart.pokemon_names[id]

                record = cart.pokemon_records[id]
                # TODO put this in construct
                types = [record.type1]
                if record.type1 != record.type2:
                    types.append(record.type2)

                writer.types = types
                writer.base_stats = {
                    'hp': record.base_hp,
                    'attack': record.base_attack,
                    'defense': record.base_defense,
                    'speed': record.base_speed,
                    'special': record.base_special,
                }
                writer.growth_rate = record.growth_rate
                writer.base_experience = record.base_experience
                #writer.pokedex_numbers = dict(kanto=record.pokedex_number)

                # Starting moves are stored with the Pokémon; other level-up
                # moves are stored with evolutions
                level_up_moves = [
                    {1: move}
                    for move in record.initial_moveset
                    # TODO UGH
                    if move != '--'
                ]
                for level_up_move in cart.pokemon_evos_and_moves[id].level_up_moves:
                    level_up_moves.append({
                        level_up_move.level: level_up_move.move,
                    })
                writer.moves = {
                    'level-up': level_up_moves,
                    'machines': [
                        move for (has_machine, move) in zip(
                            record.machines, cart.machine_moves)
                        if has_machine],
                }

                # Evolution
                # TODO alas, the species here is a number, because it's an
                # internal id and we switch those back using data from the
                # game...
                evolutions = []
                for evo_datum in cart.pokemon_evos_and_moves[id].evolutions:
                    evo = {
                        'into': POKEMON_IDENTIFIERS[cart.pokedex_order[evo_datum.evo_species] + 1],
                        'trigger': evo_datum.evo_trigger,
                        'minimum-level': evo_datum.evo_level,
                    }
                    # TODO insert the item trigger!
                    evolutions.append(evo)
                writer.evolutions = evolutions

                # Pokédex flavor
                flavor_struct = cart.pokedex_entries[id]
                writer.genus = flavor_struct.genus.decrypt(language)
                writer.flavor_text = flavor_struct.flavor_text.decrypt(language)
                if cart.uses_metric:
                    writer.height = 1000 * flavor_struct.height_decimeters
                    writer.weight = 100000000 * flavor_struct.weight_hectograms
                else:
                    writer.height = 254 * (
                        12 * flavor_struct.height_feet
                        + flavor_struct.height_inches)
                    writer.weight = 45359237 * flavor_struct.weight_decipounds

        fn = root / 'pokemon.yaml'
        print('Writing', fn)
        with fn.open('w') as f:
            f.write(Camel([schema.POKEDEX_TYPES]).dump(pokemons))


if __name__ == '__main__':
    # TODO yeah fix this up
    main(Path('pokedex/data'))
