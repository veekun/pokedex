"""Extract all the juicy details from a Gen I game.

This was a pain in the ass!  Thank you SO MUCH to:

    pokered
    pokeyellow
    vixie
    http://www.pastraiser.com/cpu/gameboy/gameboy_opcodes.html
"""
# TODO fix that docstring
# TODO note terminology somewhere: id, index, identifier
from collections import OrderedDict
import hashlib
import io
import logging
from pathlib import Path
import re
import sys

from classtools import reify
from construct import *

import pokedex.schema as schema

# TODO set this up to colorcode and use {} formatting
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
    0: 'medium',
    3: 'medium-slow',
    4: 'fast',
    5: 'slow',
}

EVOLUTION_TRIGGERS = {
    1: 'level-up',
    2: 'use-item',
    3: 'trade',
}

# TODO these are loci, not enums, so hardcoding all their identifiers here
# makes me nonspecifically uncomfortable
POKEMON_IDENTIFIERS = {
    1: 'bulbasaur',
    2: 'ivysaur',
    3: 'venusaur',
    4: 'charmander',
    5: 'charmeleon',
    6: 'charizard',
    7: 'squirtle',
    8: 'wartortle',
    9: 'blastoise',
    10: 'caterpie',
    11: 'metapod',
    12: 'butterfree',
    13: 'weedle',
    14: 'kakuna',
    15: 'beedrill',
    16: 'pidgey',
    17: 'pidgeotto',
    18: 'pidgeot',
    19: 'rattata',
    20: 'raticate',
    21: 'spearow',
    22: 'fearow',
    23: 'ekans',
    24: 'arbok',
    25: 'pikachu',
    26: 'raichu',
    27: 'sandshrew',
    28: 'sandslash',
    29: 'nidoran-f',
    30: 'nidorina',
    31: 'nidoqueen',
    32: 'nidoran-m',
    33: 'nidorino',
    34: 'nidoking',
    35: 'clefairy',
    36: 'clefable',
    37: 'vulpix',
    38: 'ninetales',
    39: 'jigglypuff',
    40: 'wigglytuff',
    41: 'zubat',
    42: 'golbat',
    43: 'oddish',
    44: 'gloom',
    45: 'vileplume',
    46: 'paras',
    47: 'parasect',
    48: 'venonat',
    49: 'venomoth',
    50: 'diglett',
    51: 'dugtrio',
    52: 'meowth',
    53: 'persian',
    54: 'psyduck',
    55: 'golduck',
    56: 'mankey',
    57: 'primeape',
    58: 'growlithe',
    59: 'arcanine',
    60: 'poliwag',
    61: 'poliwhirl',
    62: 'poliwrath',
    63: 'abra',
    64: 'kadabra',
    65: 'alakazam',
    66: 'machop',
    67: 'machoke',
    68: 'machamp',
    69: 'bellsprout',
    70: 'weepinbell',
    71: 'victreebel',
    72: 'tentacool',
    73: 'tentacruel',
    74: 'geodude',
    75: 'graveler',
    76: 'golem',
    77: 'ponyta',
    78: 'rapidash',
    79: 'slowpoke',
    80: 'slowbro',
    81: 'magnemite',
    82: 'magneton',
    83: 'farfetchd',
    84: 'doduo',
    85: 'dodrio',
    86: 'seel',
    87: 'dewgong',
    88: 'grimer',
    89: 'muk',
    90: 'shellder',
    91: 'cloyster',
    92: 'gastly',
    93: 'haunter',
    94: 'gengar',
    95: 'onix',
    96: 'drowzee',
    97: 'hypno',
    98: 'krabby',
    99: 'kingler',
    100: 'voltorb',
    101: 'electrode',
    102: 'exeggcute',
    103: 'exeggutor',
    104: 'cubone',
    105: 'marowak',
    106: 'hitmonlee',
    107: 'hitmonchan',
    108: 'lickitung',
    109: 'koffing',
    110: 'weezing',
    111: 'rhyhorn',
    112: 'rhydon',
    113: 'chansey',
    114: 'tangela',
    115: 'kangaskhan',
    116: 'horsea',
    117: 'seadra',
    118: 'goldeen',
    119: 'seaking',
    120: 'staryu',
    121: 'starmie',
    122: 'mr-mime',
    123: 'scyther',
    124: 'jynx',
    125: 'electabuzz',
    126: 'magmar',
    127: 'pinsir',
    128: 'tauros',
    129: 'magikarp',
    130: 'gyarados',
    131: 'lapras',
    132: 'ditto',
    133: 'eevee',
    134: 'vaporeon',
    135: 'jolteon',
    136: 'flareon',
    137: 'porygon',
    138: 'omanyte',
    139: 'omastar',
    140: 'kabuto',
    141: 'kabutops',
    142: 'aerodactyl',
    143: 'snorlax',
    144: 'articuno',
    145: 'zapdos',
    146: 'moltres',
    147: 'dratini',
    148: 'dragonair',
    149: 'dragonite',
    150: 'mewtwo',
    151: 'mew',
}

TYPE_IDENTIFIERS = {
    0: 'normal',
    1: 'fighting',
    2: 'flying',
    3: 'poison',
    4: 'ground',
    5: 'rock',
    #6: 'bird',
    7: 'bug',
    8: 'ghost',
    9: 'steel',
    20: 'fire',
    21: 'water',
    22: 'grass',
    23: 'electric',
    24: 'psychic',
    25: 'ice',
    26: 'dragon',
    27: 'dark',
}

MOVE_IDENTIFIERS = {
    # TODO stupid hack for initial moveset
    0: '--',

    1: 'pound',
    2: 'karate-chop',
    3: 'double-slap',
    4: 'comet-punch',
    5: 'mega-punch',
    6: 'pay-day',
    7: 'fire-punch',
    8: 'ice-punch',
    9: 'thunder-punch',
    10: 'scratch',
    11: 'vice-grip',
    12: 'guillotine',
    13: 'razor-wind',
    14: 'swords-dance',
    15: 'cut',
    16: 'gust',
    17: 'wing-attack',
    18: 'whirlwind',
    19: 'fly',
    20: 'bind',
    21: 'slam',
    22: 'vine-whip',
    23: 'stomp',
    24: 'double-kick',
    25: 'mega-kick',
    26: 'jump-kick',
    27: 'rolling-kick',
    28: 'sand-attack',
    29: 'headbutt',
    30: 'horn-attack',
    31: 'fury-attack',
    32: 'horn-drill',
    33: 'tackle',
    34: 'body-slam',
    35: 'wrap',
    36: 'take-down',
    37: 'thrash',
    38: 'double-edge',
    39: 'tail-whip',
    40: 'poison-sting',
    41: 'twineedle',
    42: 'pin-missile',
    43: 'leer',
    44: 'bite',
    45: 'growl',
    46: 'roar',
    47: 'sing',
    48: 'supersonic',
    49: 'sonic-boom',
    50: 'disable',
    51: 'acid',
    52: 'ember',
    53: 'flamethrower',
    54: 'mist',
    55: 'water-gun',
    56: 'hydro-pump',
    57: 'surf',
    58: 'ice-beam',
    59: 'blizzard',
    60: 'psybeam',
    61: 'bubble-beam',
    62: 'aurora-beam',
    63: 'hyper-beam',
    64: 'peck',
    65: 'drill-peck',
    66: 'submission',
    67: 'low-kick',
    68: 'counter',
    69: 'seismic-toss',
    70: 'strength',
    71: 'absorb',
    72: 'mega-drain',
    73: 'leech-seed',
    74: 'growth',
    75: 'razor-leaf',
    76: 'solar-beam',
    77: 'poison-powder',
    78: 'stun-spore',
    79: 'sleep-powder',
    80: 'petal-dance',
    81: 'string-shot',
    82: 'dragon-rage',
    83: 'fire-spin',
    84: 'thunder-shock',
    85: 'thunderbolt',
    86: 'thunder-wave',
    87: 'thunder',
    88: 'rock-throw',
    89: 'earthquake',
    90: 'fissure',
    91: 'dig',
    92: 'toxic',
    93: 'confusion',
    94: 'psychic',
    95: 'hypnosis',
    96: 'meditate',
    97: 'agility',
    98: 'quick-attack',
    99: 'rage',
    100: 'teleport',
    101: 'night-shade',
    102: 'mimic',
    103: 'screech',
    104: 'double-team',
    105: 'recover',
    106: 'harden',
    107: 'minimize',
    108: 'smokescreen',
    109: 'confuse-ray',
    110: 'withdraw',
    111: 'defense-curl',
    112: 'barrier',
    113: 'light-screen',
    114: 'haze',
    115: 'reflect',
    116: 'focus-energy',
    117: 'bide',
    118: 'metronome',
    119: 'mirror-move',
    120: 'self-destruct',
    121: 'egg-bomb',
    122: 'lick',
    123: 'smog',
    124: 'sludge',
    125: 'bone-club',
    126: 'fire-blast',
    127: 'waterfall',
    128: 'clamp',
    129: 'swift',
    130: 'skull-bash',
    131: 'spike-cannon',
    132: 'constrict',
    133: 'amnesia',
    134: 'kinesis',
    135: 'soft-boiled',
    136: 'high-jump-kick',
    137: 'glare',
    138: 'dream-eater',
    139: 'poison-gas',
    140: 'barrage',
    141: 'leech-life',
    142: 'lovely-kiss',
    143: 'sky-attack',
    144: 'transform',
    145: 'bubble',
    146: 'dizzy-punch',
    147: 'spore',
    148: 'flash',
    149: 'psywave',
    150: 'splash',
    151: 'acid-armor',
    152: 'crabhammer',
    153: 'explosion',
    154: 'fury-swipes',
    155: 'bonemerang',
    156: 'rest',
    157: 'rock-slide',
    158: 'hyper-fang',
    159: 'sharpen',
    160: 'conversion',
    161: 'tri-attack',
    162: 'super-fang',
    163: 'slash',
    164: 'substitute',
    165: 'struggle',
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


EN_TEXT_MAP = {
    # Sort of faux movement macros
    0x00: "",   # "Start text"?
    0x4E: "\n", # Move to next line
    0x49: "\f", # Start a new Pokédex page
    0x5F: ".",   # End of Pokédex entry, adds a period

    0x05: "ガ",
    0x06: "ギ",
    0x07: "グ",
    0x08: "ゲ",
    0x09: "ゴ",
    0x0A: "ザ",
    0x0B: "ジ",
    0x0C: "ズ",
    0x0D: "ゼ",
    0x0E: "ゾ",
    0x0F: "ダ",
    0x10: "ヂ",
    0x11: "ヅ",
    0x12: "デ",
    0x13: "ド",
    0x19: "バ",
    0x1A: "ビ",
    0x1B: "ブ",
    0x1C: "ボ",
    0x26: "が",
    0x27: "ぎ",
    0x28: "ぐ",
    0x29: "げ",
    0x2A: "ご",
    0x2B: "ざ",
    0x2C: "じ",
    0x2D: "ず",
    0x2E: "ぜ",
    0x2F: "ぞ",
    0x30: "だ",
    0x31: "ぢ",
    0x32: "づ",
    0x33: "で",
    0x34: "ど",
    0x3A: "ば",
    0x3B: "び",
    0x3C: "ぶ",
    0x3D: "べ",
    0x3E: "ぼ",
    0x40: "パ",
    0x41: "ピ",
    0x42: "プ",
    0x43: "ポ",
    0x44: "ぱ",
    0x45: "ぴ",
    0x46: "ぷ",
    0x47: "ぺ",
    0x48: "ぽ",
    0x80: "ア",
    0x81: "イ",
    0x82: "ウ",
    0x83: "エ",
    0x84: "ォ",
    0x85: "カ",
    0x86: "キ",
    0x87: "ク",
    0x88: "ケ",
    0x89: "コ",
    0x8A: "サ",
    0x8B: "シ",
    0x8C: "ス",
    0x8D: "セ",
    0x8E: "ソ",
    0x8F: "タ",
    0x90: "チ",
    0x91: "ツ",
    0x92: "テ",
    0x93: "ト",
    0x94: "ナ",
    0x95: "ニ",
    0x96: "ヌ",
    0x97: "ネ",
    0x98: "ノ",
    0x99: "ハ",
    0x9A: "ヒ",
    0x9B: "フ",
    0x9C: "ホ",
    0x9D: "マ",
    0x9E: "ミ",
    0x9F: "ム",
    0xA0: "メ",
    0xA1: "モ",
    0xA2: "ヤ",
    0xA3: "ユ",
    0xA4: "ヨ",
    0xA5: "ラ",
    0xA6: "ル",
    0xA7: "レ",
    0xA8: "ロ",
    0xA9: "ワ",
    0xAA: "ヲ",
    0xAB: "ン",
    0xAC: "ッ",
    0xAD: "ャ",
    0xAE: "ュ",
    0xAF: "ョ",
    0xB0: "ィ",
    0xB1: "あ",
    0xB2: "い",
    0xB3: "う",
    0xB4: "え",
    0xB5: "お",
    0xB6: "か",
    0xB7: "き",
    0xB8: "く",
    0xB9: "け",
    0xBA: "こ",
    0xBB: "さ",
    0xBC: "し",
    0xBD: "す",
    0xBE: "せ",
    0xBF: "そ",
    0xC0: "た",
    0xC1: "ち",
    0xC2: "つ",
    0xC3: "て",
    0xC4: "と",
    0xC5: "な",
    0xC6: "に",
    0xC7: "ぬ",
    0xC8: "ね",
    0xC9: "の",
    0xCA: "は",
    0xCB: "ひ",
    0xCC: "ふ",
    0xCD: "へ",
    0xCE: "ほ",
    0xCF: "ま",
    0xD0: "み",
    0xD1: "む",
    0xD2: "め",
    0xD3: "も",
    0xD4: "や",
    0xD5: "ゆ",
    0xD6: "よ",
    0xD7: "ら",
    0xD8: "り",
    0xD9: "る",
    0xDA: "れ",
    0xDB: "ろ",
    0xDC: "わ",
    0xDD: "を",
    0xDE: "ん",
    0xDF: "っ",
    0xE0: "ゃ",
    0xE1: "ゅ",
    0xE2: "ょ",
    0xE3: "ー",

    0x50: "@",
    0x54: "#",
    0x54: "POKé",
    0x75: "…",

    0x79: "┌",
    0x7A: "─",
    0x7B: "┐",
    0x7C: "│",
    0x7D: "└",
    0x7E: "┘",

    0x74: "№",

    0x7F: " ",
    0x80: "A",
    0x81: "B",
    0x82: "C",
    0x83: "D",
    0x84: "E",
    0x85: "F",
    0x86: "G",
    0x87: "H",
    0x88: "I",
    0x89: "J",
    0x8A: "K",
    0x8B: "L",
    0x8C: "M",
    0x8D: "N",
    0x8E: "O",
    0x8F: "P",
    0x90: "Q",
    0x91: "R",
    0x92: "S",
    0x93: "T",
    0x94: "U",
    0x95: "V",
    0x96: "W",
    0x97: "X",
    0x98: "Y",
    0x99: "Z",
    0x9A: "(",
    0x9B: ")",
    0x9C: ":",
    0x9D: ";",
    0x9E: "[",
    0x9F: "]",
    0xA0: "a",
    0xA1: "b",
    0xA2: "c",
    0xA3: "d",
    0xA4: "e",
    0xA5: "f",
    0xA6: "g",
    0xA7: "h",
    0xA8: "i",
    0xA9: "j",
    0xAA: "k",
    0xAB: "l",
    0xAC: "m",
    0xAD: "n",
    0xAE: "o",
    0xAF: "p",
    0xB0: "q",
    0xB1: "r",
    0xB2: "s",
    0xB3: "t",
    0xB4: "u",
    0xB5: "v",
    0xB6: "w",
    0xB7: "x",
    0xB8: "y",
    0xB9: "z",
    0xBA: "é",
    0xBB: "'d",
    0xBC: "'l",
    0xBD: "'s",
    0xBE: "'t",
    0xBF: "'v",
    0xE0: "'",
    0xE3: "-",
    0xE4: "'r",
    0xE5: "'m",
    0xE6: "?",
    0xE7: "!",
    0xE8: ".",
    0xED: "▶",
    0xEF: "♂",
    0xF0: "¥",
    0xF1: "×",
    0xF3: "/",
    0xF4: ",",
    0xF5: "♀",
    0xF6: "0",
    0xF7: "1",
    0xF8: "2",
    0xF9: "3",
    0xFA: "4",
    0xFB: "5",
    0xFC: "6",
    0xFD: "7",
    0xFE: "8",
    0xFF: "9",
}

JA_CHARMAP = {
    **EN_TEXT_MAP,
    0x05: "ガ",
    0x06: "ギ",
    0x07: "グ",
    0x08: "ゲ",
    0x09: "ゴ",
    0x0A: "ザ",
    0x0B: "ジ",
    0x0C: "ズ",
    0x0D: "ゼ",
    0x0E: "ゾ",
    0x0F: "ダ",
    0x10: "ヂ",
    0x11: "ヅ",
    0x12: "デ",
    0x13: "ド",
    0x19: "バ",
    0x1A: "ビ",
    0x1B: "ブ",
    0x1C: "ボ",
    0x26: "が",
    0x27: "ぎ",
    0x28: "ぐ",
    0x29: "げ",
    0x2A: "ご",
    0x2B: "ざ",
    0x2C: "じ",
    0x2D: "ず",
    0x2E: "ぜ",
    0x2F: "ぞ",
    0x30: "だ",
    0x31: "ぢ",
    0x32: "づ",
    0x33: "で",
    0x34: "ど",
    0x3A: "ば",
    0x3B: "び",
    0x3C: "ぶ",
    0x3D: "べ",
    0x3E: "ぼ",
    0x40: "パ",
    0x41: "ピ",
    0x42: "プ",
    0x43: "ポ",
    0x44: "ぱ",
    0x45: "ぴ",
    0x46: "ぷ",
    0x47: "ぺ",
    0x48: "ぽ",
    0x80: "ア",
    0x81: "イ",
    0x82: "ウ",
    0x83: "エ",
    0x84: "ォ",
    0x85: "カ",
    0x86: "キ",
    0x87: "ク",
    0x88: "ケ",
    0x89: "コ",
    0x8A: "サ",
    0x8B: "シ",
    0x8C: "ス",
    0x8D: "セ",
    0x8E: "ソ",
    0x8F: "タ",
    0x90: "チ",
    0x91: "ツ",
    0x92: "テ",
    0x93: "ト",
    0x94: "ナ",
    0x95: "ニ",
    0x96: "ヌ",
    0x97: "ネ",
    0x98: "ノ",
    0x99: "ハ",
    0x9A: "ヒ",
    0x9B: "フ",
    0x9C: "ホ",
    0x9D: "マ",
    0x9E: "ミ",
    0x9F: "ム",
    0xA0: "メ",
    0xA1: "モ",
    0xA2: "ヤ",
    0xA3: "ユ",
    0xA4: "ヨ",
    0xA5: "ラ",
    0xA6: "ル",
    0xA7: "レ",
    0xA8: "ロ",
    0xA9: "ワ",
    0xAA: "ヲ",
    0xAB: "ン",
    0xAC: "ッ",
    0xAD: "ャ",
    0xAE: "ュ",
    0xAF: "ョ",
    0xB0: "ィ",
    0xB1: "あ",
    0xB2: "い",
    0xB3: "う",
    0xB4: "え",
    0xB5: "お",
    0xB6: "か",
    0xB7: "き",
    0xB8: "く",
    0xB9: "け",
    0xBA: "こ",
    0xBB: "さ",
    0xBC: "し",
    0xBD: "す",
    0xBE: "せ",
    0xBF: "そ",
    0xC0: "た",
    0xC1: "ち",
    0xC2: "つ",
    0xC3: "て",
    0xC4: "と",
    0xC5: "な",
    0xC6: "に",
    0xC7: "ぬ",
    0xC8: "ね",
    0xC9: "の",
    0xCA: "は",
    0xCB: "ひ",
    0xCC: "ふ",
    0xCD: "へ",
    0xCE: "ほ",
    0xCF: "ま",
    0xD0: "み",
    0xD1: "む",
    0xD2: "め",
    0xD3: "も",
    0xD4: "や",
    0xD5: "ゆ",
    0xD6: "よ",
    0xD7: "ら",
    0xD8: "り",
    0xD9: "る",
    0xDA: "れ",
    0xDB: "ろ",
    0xDC: "わ",
    0xDD: "を",
    0xDE: "ん",
    0xDF: "っ",
    0xE0: "ゃ",
    0xE1: "ゅ",
    0xE2: "ょ",
    0xE3: "ー",
    0xE9: "ァ",
}
for n in range(0x100):
    if not n in JA_CHARMAP:
        JA_CHARMAP[n] = '�'

# ty, tachyon
DE_FR_TEXT_MAP = dict(enumerate([
    # 0x0X
    "�", "�", "�", "�", "�", "�", "�", "�",
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
    # 0x4X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x5X
    "", "�", "�", "�", "�", "�", "�", "�",
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
    "'", "P\u200dk", "M\u200dn", "-", "¿", "¡", "?", "!",
    ".", "ァ", "ゥ", "ェ", "▹", "▸", "▾", "♂",
    # 0xFX
    "$", "×", ".", "/", ",", "♀", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9",
]))
DE_FR_TEXT_MAP.update({
    0x00: "",   # "Start text"?
    0x4E: "\n", # Move to next line
    0x49: "\f", # Start a new Pokédex page
    0x5F: ".",   # End of Pokédex entry, adds a period
    0x54: "POKé",
})

ES_IT_CHARMAP = dict(enumerate([
    # 0x0X
    "�", "�", "�", "�", "�", "�", "�", "�",
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
    # 0x4X
    "�", "�", "�", "�", "�", "�", "�", "�",
    "�", "�", "�", "�", "�", "�", "�", "�",
    # 0x5X
    "@", "�", "�", "�", "�", "�", "�", "�",
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
    "y", "z", "à", "è", "é", "ù", "À", "Á",
    # 0xCX
    "Ä", "Ö", "Ü", "ä", "ö", "ü", "È", "É",
    "Ì", "Í", "Ñ", "Ò", "Ó", "Ù", "Ú", "á",
    # 0xDX
    "ì", "í", "ñ", "ò", "ó", "ú", "º", "&",
    "ʼd", "ʼl", "ʼm", "ʼr", "ʼs", "ʼt", "ʼv", " ",
    # 0xEX
    "'", "P\u200dk", "M\u200dn", "-", "¿", "¡", "?", "!",
    ".", "ァ", "ゥ", "ェ", "▹", "▸", "▾", "♂",
    # 0xFX
    "$", "×", ".", "/", ",", "♀", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9"
]))
ES_IT_CHARMAP.update({
    0x00: "",   # "Start text"?
    0x4E: "\n", # Move to next line
    0x49: "\f", # Start a new Pokédex page
    0x5F: ".",   # End of Pokédex entry, adds a period
    0x54: "POKé",
})


class PokemonString:
    """A string encoded using the goofy Gen I scheme."""
    def __init__(self, raw):
        self.raw = raw

    def decrypt(self, language):
        if language == 'ja':
            charmap = JA_CHARMAP
        elif language == 'en':
            charmap = EN_TEXT_MAP
        elif language in ('es', 'it'):
            charmap = ES_IT_CHARMAP
        elif language in ('de', 'fr'):
            charmap = DE_FR_TEXT_MAP
        else:
            raise ValueError("Not a known language: {!r}".format(language))

        return ''.join(
            charmap.get(ch, '�') for ch in self.raw)


class PokemonCString(Adapter):
    """Construct thing for `PokemonString`."""
    def __init__(self, name, length=None):
        # No matter which charmap, the "end of string" character is always
        # encoded as P
        if length is None:
            subcon = CString(name, terminators=b'P')
        else:
            subcon = String(name, length, padchar=b'P')
        super().__init__(subcon)

    def _encode(self, obj, context):
        raise NotImplementedError

    def _decode(self, obj, context):
        return PokemonString(obj)


class NullTerminatedArray(Subconstruct):
    _peeker = Peek(ULInt8('___'))
    __slots__ = ()

    def __init__(self, subcon):
        super().__init__(subcon)
        self._clear_flag(self.FLAG_COPY_CONTEXT)
        self._set_flag(self.FLAG_DYNAMIC)

    def _parse(self, stream, context):
        from construct.lib import ListContainer
        obj = ListContainer()
        orig_context = context
        while True:
            nextbyte = self._peeker.parse_stream(stream)
            if nextbyte == 0:
                break

            if self.subcon.conflags & self.FLAG_COPY_CONTEXT:
                context = orig_context.__copy__()

            # TODO what if we hit the end of the stream
            obj.append(self.subcon._parse(stream, context))

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
    'game_boy_header',
    # Entry point for the game; generally contains a jump to 0x0150
    String('entry_point', 4),
    # Nintendo logo; must be exactly this or booting will not continue
    Const(
        String('nintendo_logo', 48),
        bytes.fromhex("""
            CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D
            00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99
            BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E
        """.replace('\n', '')),
    ),
    String('title', 11, padchar=b'\x00'),
    String('manufacturer_code', 4),
    ULInt8('cgb_flag'),
    String('new_licensee_code', 2),
    ULInt8('sgb_flag'),  # 3 for super game boy support
    ULInt8('cartridge_type'),
    ULInt8('rom_size'),
    ULInt8('ram_size'),
    ULInt8('region_code'),  # 0 for japan, 1 for not japan
    ULInt8('old_licensee_code'),  # 0x33 means to use licensee_code
    ULInt8('game_version'),
    ULInt8('header_checksum'),
    UBInt16('cart_checksum'),
)


# The mother lode — Pokémon base stats
pokemon_struct = Struct(
    'pokemon',
    ULInt8('pokedex_number'),
    ULInt8('base_hp'),
    ULInt8('base_attack'),
    ULInt8('base_defense'),
    ULInt8('base_speed'),
    ULInt8('base_special'),
    IdentEnum(ULInt8('type1'), TYPE_IDENTIFIERS),
    IdentEnum(ULInt8('type2'), TYPE_IDENTIFIERS),
    ULInt8('catch_rate'),
    ULInt8('base_experience'),
    # TODO ????  "sprite dimensions"
    ULInt8('_sprite_dimensions'),
    ULInt16('front_sprite_pointer'),
    ULInt16('back_sprite_pointer'),
    # TODO somehow rig this to discard trailing zeroes; there's a paddedstring that does it
    Array(4, IdentEnum(ULInt8('initial_moveset'), MOVE_IDENTIFIERS)),
    IdentEnum(ULInt8('growth_rate'), GROWTH_RATES),
    # TODO argh, this is a single huge integer; i want an array, but then i lose the byteswapping!
    Bitwise(
        BitField('machines', 7 * 8, swapped=True),
    ),
    Padding(1),
)

pokemon_name_struct = PokemonCString('pokemon_name', 10)


evos_moves_struct = Struct(
    'evos_moves',
    NullTerminatedArray(
        Struct(
            'evolutions',
            IdentEnum(ULInt8('evo_trigger'), EVOLUTION_TRIGGERS),
            Embedded(Switch(
                'evo_arguments',
                lambda ctx: ctx.evo_trigger, {
                    'level-up': Struct(
                        '---',
                        ULInt8('evo_level'),
                    ),
                    'use-item': Struct(
                        '---',
                        # TODO item enum too wow!
                        ULInt8('evo_item'),
                        # TODO ??? always seems to be 1
                        ULInt8('evo_level'),
                    ),
                    # TODO ??? always seems to be 1 here too
                    'trade': Struct(
                        '---',
                        ULInt8('evo_level'),
                    ),
                },
            )),
            # TODO alas, the species here is a number, because it's an internal
            # id and we switch those back using data from the game...
            ULInt8('evo_species'),
        ),
    ),
    NullTerminatedArray(
        Struct(
            'level_up_moves',
            ULInt8('level'),
            IdentEnum(ULInt8('move'), MOVE_IDENTIFIERS),
            Peek(ULInt8('_end')),
        ),
    ),
)
evos_moves_pointer = Struct(
    'xxx',
    ULInt16('offset'),
    # TODO hardcoded as the same bank, ugh
    Pointer(lambda ctx: ctx.offset + (0xE - 1) * 0x4000, evos_moves_struct),
)

pokedex_flavor_struct = Struct(
    'pokedex_flavor',
    PokemonCString('species'),
    # TODO HA HA FUCK ME, SOME GAMES USE METRIC SOME (OK JUST THE US) USE IMPERIAL
    #ULInt8('height_feet'),
    #ULInt8('height_inches'),
    #ULInt16('weight_pounds'),
    ULInt8('height_decimeters'),
    ULInt16('weight_hectograms'),
    # This appears to technically be a string containing a single macro, for
    # "load other string from this address", but it always takes this same form
    # so there's no need to actually evaluate it.
    Const(ULInt8('macro'), 0x17),  # 0x17 is the "far" macro
    ULInt16('address'),
    ULInt8('bank'),
    Const(ULInt8('nul'), 0x50),  # faux nul marking the end of the string
    Pointer(
        lambda ctx: ctx.address + (ctx.bank - 1) * 0x4000,
        PokemonCString('flavor_text'),
    ),
)
# TODO this works very awkwardly as a struct
pokedex_flavor_pointer = Struct(
    'xxx',
    ULInt16('offset'),
    # TODO hardcoded 0x10, same bank
    # TODO this has to be on-demand because missingno's struct is actually bogus!
    OnDemandPointer(lambda ctx: ctx.offset + (0x10 - 1) * 0x4000, pokedex_flavor_struct),
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
        addresses = {
            # These seem to always be the same.  Not sure why!
            'BaseStats': unbank('0E:43DE'),
            'MewBaseStats': unbank('01:425B'),
        }

        # For everything else, the general approach is to find some assembly
        # code that appears just before the data of interest.  It's pretty
        # hacky, but since translators (and even modders) would have little
        # reason to rearrange functions or inject new ones in these odd places,
        # it ought to work well enough.  And it's better than ferreting out and
        # hard-coding piles of addresses.
        # The only hard part is that assembly code that contains an address
        # won't work, since that address will also vary per game.
        # Each of the landmarks used here appears in every official cartridge
        # exactly once.

        # This is an entire function used by the Pokédex and which immediately
        # precedes all the flavor text.
        asm_DrawTileLine = bytes.fromhex('c5d5 7019 0d20 fbd1 c1c9')
        try:
            idx = self.data.index(asm_DrawTileLine)
        except ValueError:
            raise CartDetectionError("Can't find flavor text pointers")
        addresses['PokedexEntryPointers'] = idx + len(asm_DrawTileLine)

        # This is a helper function for figuring out moves, followed by another
        # 5-byte function, then the table of evolutions and moves.
        asm_WriteMonMoves_ShiftMoveData = bytes.fromhex('0e03 131a 220d 20fa c9')
        try:
            idx = self.data.index(asm_WriteMonMoves_ShiftMoveData)
        except ValueError:
            raise CartDetectionError("Can't find evolution and moveset table")
        addresses['EvosMovesPointerTable'] = idx + len(asm_WriteMonMoves_ShiftMoveData) + 5

        # Finding TMs is a bit harder.  They come right after a function for
        # looking up a TM number, which is very short and very full of
        # addresses.  So here's a regex.
        # `wd11e` is some address used all over the game for passing arguments
        # around, which unfortunately also differs from language to language.
        # In English it is, unsurprisingly, 0xD11E.
        # `TechnicalMachines` is the address we're looking for, which should
        # immediately follow what this matches.
        asm_TMToMove_rx = re.compile(rb'''
            \xfa (..)   # ld a, [wd11e]
            \x3d        # dec a
            \x21 (..)   # ld hl, TechnicalMachines
            \x06 \x00   # ld b, $0
            \x4f        # ld c, a
            \x09        # add hl, bc
            \x7e        # ld a, [hl]
            \xea \1     # ld [wd11e], a
            \xc9        # ret
        ''', flags=re.DOTALL | re.VERBOSE)
        for match in asm_TMToMove_rx.finditer(self.data):
            matched_addr = ULInt16('...').parse(match.group(2))
            tentative_addr = match.end()
            # Remember, addresses don't include the bank!
            _, banked_addr = bank(tentative_addr)
            if matched_addr == banked_addr:
                asm_wd11e_addr = match.group(1)
                addresses['TechnicalMachines'] = tentative_addr
                break
            # TODO should there really be more than one match?
        else:
            raise CartDetectionError("Can't find technical machines list")

        # Pokédex order is similarly tricky.  Much like the above, this
        # function converts a Pokémon's game index to its national dex number.
        # These are almost immediately after the Pokédex entries themselves,
        # but this actually seems easier than figuring out where a table of
        # pointers ends.
        asm_IndexToPokedex_rx = re.compile(rb'''
            \xc5        # push bc
            \xe5        # push hl
            \xfa (..)   # ld a,[wd11e]
            \x3d        # dec a
            \x21 (..)   # ld hl,PokedexOrder
            \x06 \x00   # ld b,0
            \x4f        # ld c,a
            \x09        # add hl,bc
            \x7e        # ld a,[hl]
            \xea \1     # ld [wd11e],a
            \xe1        # pop hl
            \xc1        # pop bc
            \xc9        # ret
        ''', flags=re.DOTALL | re.VERBOSE)
        for match in asm_IndexToPokedex_rx.finditer(self.data):
            matched_addr = ULInt16('...').parse(match.group(2))
            tentative_addr = match.end()
            # Remember, addresses don't include the bank!
            _, banked_addr = bank(tentative_addr)
            if matched_addr == banked_addr and asm_wd11e_addr == match.group(1):
                addresses['PokedexOrder'] = tentative_addr
                break
        else:
            raise CartDetectionError("Can't find Pokédex order")

        # This is assembly code that appears near the end of a function called
        # WaitForSoundToFinish.
        end_of_WaitForSoundToFinish = bytes.fromhex('afb6 23b6 2323 b6')
        try:
            idx = self.data.index(end_of_WaitForSoundToFinish)
        except ValueError:
            raise CartDetectionError("Can't find name array")
        # There are a couple more bytes in the function, but they involve an
        # address so they can't be searched for.  Red/Green/Blue have four;
        # Yellow has an extra 'and', which is annoying, but at least easy to
        # handle.
        start = idx + len(end_of_WaitForSoundToFinish)
        if self.data[start] == 0xA7:
            # Yellow; skip one more byte
            start += 1
        start += 4

        name_pointers = Array(7, ULInt16('dummy')).parse(self.data[start:start + 14])
        # One downside to the Game Boy memory structure is that banks are not
        # stored anywhere near their corresponding addresses, so the bank
        # numbers are hardcoded here.  They're fairly unlikely to change
        # between games.  Right?  Probably?
        addresses['MonsterNames'] = unbank(0x07, name_pointers[0])
        addresses['MoveNames'] = unbank(0x2C, name_pointers[1])
        # 2: UnusedNames  (unused, obviously)
        addresses['ItemNames'] = unbank(0x01, name_pointers[3])
        # 4: wPartyMonOT  (only useful while the game is running)
        # 5: wEnemyMonOT  (only useful while the game is running)
        addresses['TrainerNames'] = unbank(0x0E, name_pointers[6])

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
                "Hmm.  I don't recognize the checksum for {}, but I'll "
                "continue anyway.",
                self.path.name)
        elif game_c != game_h or language_c != language_h:
            log.warn(
                "This is very surprising.  The checksum indicates that this "
                "game should be {}, {}, but I detected it as {}, {}.  Probably "
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
        single_string_struct = PokemonCString('dummy')
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
        for index, pokemon_name in enumerate(Array(self.max_pokemon_index, pokemon_name_struct).parse_stream(self.stream), start=1):
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
        return Array(self.NUM_MACHINES, IdentEnum(ULInt8('move'), MOVE_IDENTIFIERS)).parse_stream(self.stream)

    @reify
    def pokemon_records(self):
        """List of pokemon_structs."""
        self.stream.seek(self.addrs['BaseStats'])
        records = Array(self.NUM_POKEMON - 1, pokemon_struct).parse_stream(self.stream)
        # Mew's data is, awkwardly, stored separately
        self.stream.seek(self.addrs['MewBaseStats'])
        records.append(pokemon_struct.parse_stream(self.stream))

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
        self.stream.seek(self.addrs['PokedexEntryPointers'])
        for index, pointer in enumerate(Array(self.max_pokemon_index, pokedex_flavor_pointer).parse_stream(self.stream), start=1):
            try:
                id = self.pokedex_order[index]
            except KeyError:
                continue

            ret[id] = pointer.pokedex_flavor.value

            record = pokemon_records_by_internal[index]
            pokedex_flavor = pointer.pokedex_flavor.value
            # TODO FUCKKKK IMPERIALLLLL
            #record.height = pokedex_flavor.height_feet * 12 + pokedex_flavor.height_inches
            #record.weight = pokedex_flavor.weight_pounds
            record.height = pokedex_flavor.height_decimeters
            record.weight = pokedex_flavor.weight_hectograms

            record.species = pokedex_flavor.species.decrypt(language)
            record.flavor_text = pokedex_flavor.flavor_text.decrypt(language)

    @reify
    def move_names(self):
        self.stream.seek(self.addrs['MoveNames'])
        return Array(NUM_MOVES, PokemonCString('move_name')).parse_stream(self.stream)



class RBYLoader:
    def __init__(self, *carts):
        self.carts = carts
        # TODO require all the same game

    def load(self):
        pass


# TODO would be slick to convert this to a construct...  construct
def bitfield_to_machines(bits, machine_moves):
    machines = []
    for i, move in enumerate(machine_moves, start=1):
        bit = bits & 0x1
        bits >>= 1
        if bit:
            machines.append(move)

    return machines


class WriterWrapper:
    def __init__(self, locus, language):
        self.locus = locus
        self.language = language

    def __setattr__(self, key, value):
        # TODO finish this...
        # 1. disallow reassigning an existing attr with a value
        setattr(self.locus, key, value)

    def __getattr__(self, key):
        return getattr(self.locus, key)


def main():
    # TODO does this need to take arguments?  or like, sprite mode i guess
    carts = []
    for filename in sys.argv[1:]:
        cart = RBYCart(Path(filename))
        carts.append(cart)

    #loader = RBYLoader(*carts)
    pokemons = OrderedDict([
        (POKEMON_IDENTIFIERS[id + 1], schema.Pokemon())
        for id in range(carts[0].NUM_POKEMON)
    ])
    for cart in carts:
        for id in range(cart.NUM_POKEMON):
            pokemon = pokemons[POKEMON_IDENTIFIERS[id + 1]]
            #writer = WriterWrapper(pokemon)
            writer = pokemon

            # TODO LOLLLL
            if 'name' not in writer.__dict__:
                writer.name = {}
            writer.name[cart.language] = cart.pokemon_names[id]

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

            # Starting moves are stored with the Pokémon; other level-up moves are
            # stored with evolutions
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
            # TODO LOLLLL
            if 'moves' not in writer.__dict__:
                writer.moves = {}
            writer.moves['level-up'] = level_up_moves
            writer.moves['machines'] = bitfield_to_machines(
                record.machines, cart.machine_moves)

            # Evolution
            # TODO alas, the species here is a number, because it's an internal id
            # and we switch those back using data from the game...
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


    from camel import Camel
    print(Camel([schema.POKEDEX_TYPES]).dump(pokemons))



if __name__ == '__main__':
    main()
