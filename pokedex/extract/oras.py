"""Dumps data from Omega Ruby and Alpha Sapphire.

Filesystem reference: http://www.projectpokemon.org/wiki/ORAS_File_System
"""
import argparse
from collections import OrderedDict
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import struct
import warnings

from camel import Camel
from construct import (
    # Simple fields
    Const, Flag, Int16sl, Int16ul, Int8sl, Int8ul, Int32ul, Padding,
    # Structures and meta stuff
    Array, BitsInteger, BitsSwapped, Bitwise, Enum, Filter, FocusedSeq,
    GreedyRange, Pointer, PrefixedArray, Range, Struct, this,
    # temp
    Peek, Bytes,
)
import yaml

import pokedex.schema as schema
from .lib.garc import GARCFile, decrypt_xy_text

# TODO: ribbons!  080 in sumo

# TODO auto-detect rom vs romfs vs...  whatever

# TODO fix some hardcoding in here
# TODO finish converting garc parsing to use construct, if possible, i think (i would not miss substream)
# way way more sprite work in here...

# TODO would be nice to have meaningful names for the file structure instead of sprinkling hardcoded ones throughout

# SUMO file list:
# a/2/8/1   "photos" from the credits

GROWTH_RATES = {
    0: 'gr.medium',
    1: 'gr.slow-then-very-fast',
    2: 'gr.fast-then-very-slow',
    3: 'gr.medium-slow',
    4: 'gr.fast',
    5: 'gr.slow',
}
TYPES = {
    0: 't.normal',
    1: 't.fighting',
    2: 't.flying',
    3: 't.poison',
    4: 't.ground',
    5: 't.rock',
    6: 't.bug',
    7: 't.ghost',
    8: 't.steel',
    9: 't.fire',
    10: 't.water',
    11: 't.grass',
    12: 't.electric',
    13: 't.psychic',
    14: 't.ice',
    15: 't.dragon',
    16: 't.dark',
    17: 't.fairy',
}

# ja-Hrkt: hiragana/katakana
# zh-Hans: simplified
# zh-Hant: traditional
CANON_LANGUAGES = ('ja-Hrkt', 'ja', 'en', 'fr', 'it', 'de', 'es', 'ko', 'zh-Hans', 'zh-Hant')
ORAS_SCRIPT_FILES = {
    'ja-Hrkt': 'rom/a/0/7/1',
    'ja': 'rom/a/0/7/2',
    'en': 'rom/a/0/7/3',
    'fr': 'rom/a/0/7/4',
    'it': 'rom/a/0/7/5',
    'de': 'rom/a/0/7/6',
    'es': 'rom/a/0/7/7',
    'ko': 'rom/a/0/7/8',
}
SUMO_SCRIPT_FILES = {
    'ja-Hrkt': 'rom/a/0/3/0',
    'ja': 'rom/a/0/3/1',
    'en': 'rom/a/0/3/2',
    'fr': 'rom/a/0/3/3',
    'it': 'rom/a/0/3/4',
    'de': 'rom/a/0/3/5',
    'es': 'rom/a/0/3/6',
    'ko': 'rom/a/0/3/7',
    'zh-Hans': 'rom/a/0/3/8',
    'zh-Hant': 'rom/a/0/3/9',
}
ORAS_SCRIPT_ENTRIES = {
    'form-names': 5,
    # TODO these might be backwards, i'm just guessing
    'species-flavor-alpha-sapphire': 6,
    'species-flavor-omega-ruby': 7,
    'move-contest-flavor': 13,
    'move-names': 14,
    # Note: table 15 is also a list of move names, but with a few at the end
    # missing?  XY leftovers?
    'move-flavor': 16,
    'type-names': 18,
    'ability-flavor': 36,
    'ability-names': 37,
    'nature-names': 51,
    # Note that these place names come in pairs, in order to support X/Y's
    # routes, which had both numbers and traditional street names
    # TODO oughta rip those too!
    'zone-names': 90,
    'species-names': 98,

    # 113: item names, with macros to branch for pluralization
    # 114: copy of item names, but with "PP" in latin in korean (?!)
    # 115: item names in plural (maybe interesting?)
    'item-names': 116,  # singular
    'item-flavor': 117,
}
SUMO_SCRIPT_ENTRIES = {
    # 2: bag pockets
    # 81: ribbons

    'form-names': 114,
    # TODO a lot of these are missing
    'species-flavor-sun': 119,
    'species-flavor-moon': 120,
    'move-contest-flavor': 109,
    'move-names': 113,
    # TODO 19 is z-move names
    # Note: table 15 is also a list of move names, but with a few at the end
    # missing?  XY leftovers?
    'move-flavor': 112,
    'type-names': 107,
    'ability-flavor': 97,
    'ability-names': 96,
    'nature-names': 87,
    # Note that these place names come in pairs, in order to support X/Y's
    # routes, which had both numbers and traditional street names
    # TODO oughta rip those too!
    'zone-names': 67,
    # NOTE: 67 through 70 could be zone names, but could also be "where caught"
    # names for Pokémon
    'species-names': 55,
    'pokemon-height-flavor': 115,
    'genus-names': 116,
    'pokemon-weight-flavor': 117,
    'trainer-class-names': 106,
    'berry-names': 65,
    # 49 might be pokédex colors?  or maybe clothing colors

    # 38: item names, with macros to branch for pluralization
    # 114: copy of item names, but with "PP" in latin in korean (?!)
    # 37: item names in plural (maybe interesting?)
    'item-names': 36,  # singular
    'item-flavor': 35,
}
# The first element in each list is the name of the BASE form.
# If it's None, then the base form is a true default in some sense, and it'll
# have the same name as the species.  Mega Evolutions are a good example.
# Otherwise, there is no default; the form name will differ from the species
# name, and the first sprite will be saved under both names, e.g., Shellos.
# Note that this does NOT include megas -- those are pulled from game data.
FORM_NAMES = {
    # TODO alolan are of course new in SUMO
    # Rattata and Raticate
    19: (None, 'alola'),
    20: (None, 'alola', 'totem-alola'),
    # Cosplay Pikachu
    # TODO not in SUMO
    #25: (None, 'rock-star', 'belle', 'pop-star', 'phd', 'libre', 'cosplay'),
    25: (None, 'original-cap', 'hoenn-cap', 'sinnoh-cap', 'unova-cap', 'kalos-cap', 'alola-cap'),
    # Raichu
    26: (None, 'alola'),
    # Sandshrew and Sandslash
    27: (None, 'alola'),
    28: (None, 'alola'),
    # Vulpix and Ninetales
    37: (None, 'alola'),
    38: (None, 'alola'),
    # Diglett and Dugtrio
    50: (None, 'alola'),
    51: (None, 'alola'),
    # Meowth and Persian
    52: (None, 'alola'),
    53: (None, 'alola'),
    # Geodude, Graveler, and Golem
    74: (None, 'alola'),
    75: (None, 'alola'),
    76: (None, 'alola'),
    # Geodude, Graveler, and Golem
    88: (None, 'alola'),
    89: (None, 'alola'),
    # Exeggutor
    103: (None, 'alola'),
    # Marowak
    105: (None, 'alola'),
    # Unown
    201: tuple('abcdefghijklmnopqrstuvwxyz') + ('exclamation', 'question'),
    # Castform
    351: (None, 'sunny', 'rainy', 'snowy'),
    # Kyogre and Groudon
    382: (None, 'primal'),
    383: (None, 'primal'),
    # Deoxys
    386: ('normal', 'attack', 'defense', 'speed'),
    # Burmy and Wormadam
    412: ('plant', 'sandy', 'trash'),
    413: ('plant', 'sandy', 'trash'),
    # Cherrim
    421: ('overcast', 'sunshine'),
    # Shellos and Gastrodon
    422: ('west', 'east'),
    423: ('west', 'east'),
    # Rotom
    479: (None, 'heat', 'wash', 'frost', 'fan', 'mow'),
    # Giratina
    487: ('altered', 'origin'),
    # Shaymin
    492: ('land', 'sky'),
    # Arceus
    493: (
        'normal', 'fighting', 'flying', 'poison', 'ground', 'rock', 'bug',
        'ghost', 'steel', 'fire', 'water', 'grass', 'electric', 'psychic',
        'ice', 'dragon', 'dark', 'fairy',
    ),
    # Basculin
    550: ('red-striped', 'blue-striped'),
    # Darmanitan
    555: ('standard', 'zen'),
    # Deerling and Sawsbuck
    585: ('spring', 'summer', 'autumn', 'winter'),
    586: ('spring', 'summer', 'autumn', 'winter'),
    # Tornadus, Thundurus, and Landorus
    641: ('incarnate', 'therian'),
    642: ('incarnate', 'therian'),
    645: ('incarnate', 'therian'),
    # Kyurem
    646: (None, 'white', 'black'),
    # Keldeo
    647: ('ordinary', 'resolute'),
    # Meloetta
    648: ('aria', 'pirouette'),
    # Genesect
    649: (None, 'douse', 'shock', 'burn', 'chill'),
    # Greninja
    # TODO SUMO only
    # FIXME why is the second one here at all?
    658: (None, 'dupe', 'ash'),
    # Vivillon
    666: (
        'icy-snow', 'polar', 'tundra', 'continental', 'garden', 'elegant',
        'meadow', 'modern', 'marine', 'archipelago', 'high-plains',
        'sandstorm', 'river', 'monsoon', 'savanna', 'sun', 'ocean', 'jungle',
        'fancy', 'poke-ball',
    ),
    # Flabébé/Floette/Florges
    669: ('red', 'yellow', 'orange', 'blue', 'white'),
    670: ('red', 'yellow', 'orange', 'blue', 'white', 'eternal'),
    671: ('red', 'yellow', 'orange', 'blue', 'white'),
    # Furfrou
    676: (
        'natural', 'heart', 'star', 'diamond', 'debutante', 'matron', 'dandy',
        'la-reine', 'kabuki', 'pharaoh',
    ),
    # Meowstic
    # TODO uh oh, this is handled as forms in boxes but as gender in sprites, maybe?
    678: ('male', 'female'),
    # Aegislash
    681: ('shield', 'blade'),
    # Pumpkaboo/Gourgeist
    710: ('average', 'small', 'large', 'super'),
    711: ('average', 'small', 'large', 'super'),
    # Xerneas
    716: ('neutral', 'active'),
    # Zygarde
    # TODO SUMO only
    # TODO why are 10 and 50 duplicated?
    718: (None, '10', '10', '50', 'complete'),
    # Hoopa
    720: ('confined', 'unbound'),
    # Gumshoos
    735: (None, 'totem'),
    # Vikavolt
    738: (None, 'totem'),
    # Oricorio
    741: ('baile', 'pom-pom', 'pau', 'sensu'),
    # Lycanroc
    745: ('midday', 'midnight'),
    # Wishiwashi
    746: ('solo', 'school'),
    # Lurantis
    754: (None, 'totem'),
    # Salazzle
    758: (None, 'totem'),
    # Silvally
    773: (
        'normal', 'fighting', 'flying', 'poison', 'ground', 'rock', 'bug',
        'ghost', 'steel', 'fire', 'water', 'grass', 'electric', 'psychic',
        'ice', 'dragon', 'dark', 'fairy',
    ),
    # Minior
    774: (
        'red-meteor', 'orange-meteor', 'yellow-meteor', 'green-meteor',
        'blue-meteor', 'indigo-meteor', 'violet-meteor',
        'red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet',
    ),
    # Mimikyu
    778: ('disguised', 'busted', 'totem-disguised', 'totem-busted'),
    # Kommo-o
    784: (None, 'totem'),
    # Magearna
    801: (None, 'original'),
}


pokemon_struct = Struct(
    'stat_hp' / Int8ul,
    'stat_atk' / Int8ul,
    'stat_def' / Int8ul,
    'stat_speed' / Int8ul,
    'stat_spatk' / Int8ul,
    'stat_spdef' / Int8ul,
    'type1' / Int8ul,
    'type2' / Int8ul,
    'capture_rate' / Int8ul,
    'stage' / Int8ul,
    'effort' / Int16ul,
    'held_item1' / Int16ul,
    'held_item2' / Int16ul,
    'held_item3' / Int16ul,  # dark grass from bw, unused in oras?
    'gender_rate' / Int8ul,
    'steps_to_hatch' / Int8ul,
    'base_happiness' / Int8ul,
    'growth_rate' / Enum(Int8ul, **{v: k for (k, v) in GROWTH_RATES.items()}),
    'egg_group1' / Int8ul,
    'egg_group2' / Int8ul,
    'ability1' / Int8ul,
    'ability2' / Int8ul,
    'ability_hidden' / Int8ul,
    'safari_escape' / Int8ul,
    'form_species_start' / Int16ul,
    'form_sprite_start' / Int16ul,
    'form_count' / Int8ul,
    'color' / Int8ul,
    'base_exp' / Int16ul,
    'height' / Int16ul,
    'weight' / Int16ul,
    'machines' / BitsSwapped(Bitwise(Array(14 * 8, Flag))),
    Padding(2),
    'tutors' / Int32ul,
    'mystery1' / Int16ul,
    'mystery2' / Int16ul,
    'bp_tutors1' / Int32ul,  # unused in sumo
    'bp_tutors2' / Int32ul,  # unused in sumo
    'bp_tutors3' / Int32ul,  # unused in sumo
    'bp_tutors4' / Int32ul,  # sumo: big numbers for pikachu, eevee, snorlax, mew, starter evos, couple others??  maybe special z-move item?
    # TODO sumo is four bytes longer, not sure why, find out if those bytes are anything and a better way to express them
    GreedyRange(Const(b'\x00')),
)

pokemon_mega_evolutions_struct = Filter(this.number != 0, Range(
    # XY and ORAS have 3 of these, but the third never seems to be populated.
    # SUMO just has 2.
    2, 3,
    Struct(
        'number' / Int16ul,
        'mode' / Int16ul,
        'mega_stone_itemid' / Int16ul,
        Padding(2),
    )
))

egg_moves_struct = Struct(
    'moveids' / PrefixedArray(Int16ul, Int16ul),
)

egg_moves_struct = Struct(
    'first_form_id' / Int16ul,  # TODO SUMO ONLY
    'moveids' / PrefixedArray(Int16ul, Int16ul),
)

level_up_moves_struct = GreedyRange(
    Struct(
        'moveid' / Int16sl,
        'level' / Int16sl,
    ),
)

move_struct = Struct(
    'type' / Enum(Int8ul, **{v:k for (k, v) in TYPES.items()}),
    'category' / Int8ul,
    'damage_class' / Int8ul,
    'power' / Int8ul,
    'accuracy' / Int8ul,
    'pp' / Int8ul,
    'priority' / Int8sl,
    'min_max_hits' / Int8ul,
    'caused_effect' / Int16sl,
    'effect_chance' / Int8ul,
    'status' / Int8ul,
    'min_turns' / Int8ul,
    'max_turns' / Int8ul,
    'crit_rate' / Int8ul,
    'flinch_chance' / Int8ul,
    'effect' / Int16ul,
    'recoil' / Int8sl,
    'healing' / Int8ul,
    'range' / Int8ul,            # ok
    'stat_change' / Bitwise(Array(6, BitsInteger(4))),
    'stat_amount' / Bitwise(Array(6, BitsInteger(4))),
    'stat_chance' / Bitwise(Array(6, BitsInteger(4))),
    'padding0' / Int8ul,         # ok
    'padding1' / Int8ul,         # ok
    'flags' / Int16ul,
    'padding2' / Int8ul,         # ok
    'extra' / Int8ul,
    # FIXME unsure whether this exists in ORAS; should use a length limiter in the parent
    'extra2' / Int32ul,
)
move_container_struct = FocusedSeq('records',
    Const(b'WD'),  # waza...  descriptions?
    'records' / PrefixedArray(Int16ul, FocusedSeq('move',
        'offset' / Int32ul,
        'move' / Pointer(this.offset, move_struct),
    )),
)

pokemon_sprite_struct = Struct(
    'index' / Int16ul,
    'female_index' / Int16ul,
    'form_index_offset' / Int32ul,
    'right_index_offset' / Int32ul,
    'form_count' / Int16ul,
    'right_count' / Int16ul,
)

encounter_struct = Struct(
    # TODO top 5 bits are form stuff
    'pokemon_id' / Int16ul,
    'min_level' / Int8ul,
    'max_level' / Int8ul,
)

encounter_table_struct = Struct(
    'walk_rate' / Int8ul,
    'long_grass_rate' / Int8ul,
    'hidden_rate' / Int8ul,
    'surf_rate' / Int8ul,
    'rock_smash_rate' / Int8ul,
    'old_rod_rate' / Int8ul,
    'good_rod_rate' / Int8ul,
    'super_rod_rate' / Int8ul,
    'horde_rate' / Int8ul,
    Const(b'\x00' * 5),
    Array(61, encounter_struct),
    Const(b'\x00' * 2),
)

ORAS_ENCOUNTER_SLOTS = [
    ('walk', (10, 10, 10, 10, 10, 10, 10, 10, 10, 5, 4, 1)),
    ('long-grass', (10, 10, 10, 10, 10, 10, 10, 10, 10, 5, 4, 1)),
    ('hidden', (60, 35, 5)),  # TODO guessing here!
    ('surf', (50, 30, 15, 4, 1)),
    ('rock-smash', (50, 30, 15, 4, 1)),
    ('old-rod', (60, 35, 5)),
    ('good-rod', (60, 35, 5)),
    ('super-rod', (60, 35, 5)),
    ('horde', ((60, 5), (35, 5), (5, 5))),
]

# The only thing really linking ORAS zones together is that they share the same
# overall location/place name, so use the index of that name as a key to match
# to an extant location
ORAS_ZONE_NAME_INDEX_TO_VEEKUN_LOCATION = {
    #170: Littleroot Town
    #172: Oldale Town
    174: 'dewford-town',
    #176: Lavaridge Town
    #178: Fallarbor Town
    #180: Verdanturf Town
    #182: Pacifidlog Town
    184: 'petalburg-city',
    186: 'slateport-city',
    #188: Mauville City
    #190: Rustboro City
    #192: Fortree City
    194: 'lilycove-city',
    196: 'mossdeep-city',
    198: 'sootopolis-city',
    200: 'ever-grande-city',
    #202: Pokémon League
    204: 'hoenn-route-101',
    206: 'hoenn-route-102',
    208: 'hoenn-route-103',
    210: 'hoenn-route-104',
    212: 'hoenn-route-105',
    214: 'hoenn-route-106',
    216: 'hoenn-route-107',
    218: 'hoenn-route-108',
    220: 'hoenn-route-109',
    222: 'hoenn-route-110',
    224: 'hoenn-route-111',
    226: 'hoenn-route-112',
    228: 'hoenn-route-113',
    230: 'hoenn-route-114',
    232: 'hoenn-route-115',
    234: 'hoenn-route-116',
    236: 'hoenn-route-117',
    238: 'hoenn-route-118',
    240: 'hoenn-route-119',
    242: 'hoenn-route-120',
    244: 'hoenn-route-121',
    246: 'hoenn-route-122',
    248: 'hoenn-route-123',
    250: 'hoenn-route-124',
    252: 'hoenn-route-125',
    254: 'hoenn-route-126',
    256: 'hoenn-route-127',
    258: 'hoenn-route-128',
    260: 'hoenn-route-129',
    262: 'hoenn-route-130',
    264: 'hoenn-route-131',
    266: 'hoenn-route-132',
    268: 'hoenn-route-133',
    270: 'hoenn-route-134',
    272: 'meteor-falls',
    274: 'rusturf-tunnel',
    #276: ???
    #278: Desert Ruins
    280: 'granite-cave',
    282: 'petalburg-woods',
    #284: Mt. Chimney
    286: 'jagged-pass',
    288: 'fiery-path',
    290: 'mt-pyre',
    #292: Team Aqua Hideout
    294: 'seafloor-cavern',
    296: 'cave-of-origin',
    298: 'hoenn-victory-road',
    300: 'shoal-cave',
    302: 'new-mauville',
    #304: Sea Mauville
    #306: Island Cave
    #308: Ancient Tomb
    #310: Sealed Chamber
    #312: Scorched Slab
    #314: Team Magma Hideout
    316: 'sky-pillar',
    #318: Battle Resort
    #320: Southern Island
    # TODO is this "abandoned-ship" from rse?
    #322: S.S. Tidal
    324: 'hoenn-safari-zone',
    #326: Mirage Forest
    #328: Mirage Cave
    #330: Mirage Island
    #332: Mirage Mountain
    #334: Trackless Forest
    #336: Pathless Plain
    #338: Nameless Cavern
    #340: Fabled Cave
    #342: Gnarled Den
    #344: Crescent Isle
    #346: Secret Islet
    #348: Soaring in the sky
    #350: Secret Shore
    #352: Secret Meadow
    #354: Secret Base
}
# TODO wait, in the yaml thing, where do the fanon names for these go?
ORAS_ZONE_INDEX_TO_VEEKUN_AREA = {
    # TODO oops i should be actually mapping these to areas in rse.  many of
    # them aren't split the same way, though.  uh oh.  if we make areas a more
    # first-class thing, then...  how do we deal with this?  e.g. route 104 is
    # two zones in oras but only one zone in rse.  it's easy enough to fudge
    # that with encounters, but what do you do about events etc?
    26: 'hoenn-route-104--north',
    27: 'hoenn-route-104--south',
    # TODO should i, maybe, indicate the type of terrain an area has...?
    30: 'hoenn-route-107',
    64: 'hoenn-route-107--underwater',

    # NOTE: split from rse
    38: 'hoenn-route-112--north',  # route 111 side
    39: 'hoenn-route-112--south',  # lavaridge town side

    35: 'hoenn-route-111',
    # NOTE: split from rse
    37: 'hoenn-route-111--desert',

    48: 'hoenn-route-120',
    # NOTE: new
    49: 'hoenn-route-120--tomb-area',

    53: 'hoenn-route-124',
    65: 'hoenn-route-124--underwater',

    55: 'hoenn-route-126',
    66: 'hoenn-route-126--underwater',

    57: 'hoenn-route-128',
    # NOTE: new
    68: 'hoenn-route-128--underwater',

    58: 'hoenn-route-129',
    # NOTE: new
    69: 'hoenn-route-129--underwater',

    59: 'hoenn-route-130',
    # NOTE: new
    70: 'hoenn-route-130--underwater',

    71: 'meteor-falls',
    74: 'meteor-falls--backsmall-room',  # TODO this name is dumb
    # NOTE: indistinguishable
    72: 'meteor-falls--back',
    73: 'meteor-falls--b1f',

    78: 'granite-cave--1f',
    79: 'granite-cave--b1f',
    80: 'granite-cave--b2f',

    # NOTE: indistinguishable
    86: 'mt-pyre--1f',
    87: 'mt-pyre--2f',
    88: 'mt-pyre--3f',
    89: 'mt-pyre--4f',

    90: 'mt-pyre--outside',

    # NOTE: indistinguishable; split from rse
    91: 'mt-pyre--summit-south',
    533: 'mt-pyre--summit-north',

    # NOTE: many sets of these are indistinguishable; ALL split from rse
    99: 'seafloor-cavern--entrance',
    100: 'seafloor-cavern--room-1',
    101: 'seafloor-cavern--room-2',
    102: 'seafloor-cavern--room-5',
    103: 'seafloor-cavern--room-6',
    104: 'seafloor-cavern--room-3',
    105: 'seafloor-cavern--room-7',
    106: 'seafloor-cavern--room-4',
    107: 'seafloor-cavern--room-8',
    108: 'seafloor-cavern--room-9',
    109: 'seafloor-cavern--room-10',

    # NOTE: indistinguishable
    112: 'cave-of-origin--entrance',
    113: 'cave-of-origin--1f',
    114: 'cave-of-origin--b1f',
    115: 'cave-of-origin--b2f',
    116: 'cave-of-origin--b3f',
    # NOTE: new?  rse had this room but had no encounters in it
    452: 'cave-of-origin--b4f',

    # NOTE: indistinguishable
    123: 'hoenn-victory-road--entrance',  # NOTE: new
    124: 'hoenn-victory-road--1f',
    125: 'hoenn-victory-road--b1f',
    # NOTE: new; rse had b2f instead
    126: 'hoenn-victory-road--2f',
}

# There are 63 tutor move bits in use, but only 60 move tutors -- the moves
# appear to be largely inherited from B2W2 but these are just not exposed in
# ORAS
ORAS_UNUSED_MOVE_TUTORS = {'dark-pulse', 'roost', 'sleep-talk'}
# Unsure where this is in the binary
ORAS_NORMAL_MOVE_TUTORS = (
    'grass-pledge',
    'fire-pledge',
    'water-pledge',
    'frenzy-plant',
    'blast-burn',
    'hydro-cannon',
    'draco-meteor',
    'dragon-ascent',
)


# TODO ripe for being put in the pokedex codebase itself
def make_identifier(english_name):
    # TODO do nidoran too
    return re.sub('[. ]+', '-', english_name.lower())

@contextmanager
def read_garc(path):
    with path.open('rb') as f:
        yield GARCFile(f)


# XXX christ lol.  taken from SO.  fodder for camel maybe
def represent_ordereddict(dumper, data):
    value = []

    for item_key, item_value in data.items():
        node_key = dumper.represent_data(item_key)
        node_value = dumper.represent_data(item_value)

        value.append((node_key, node_value))

    return yaml.nodes.MappingNode(u'tag:yaml.org,2002:map', value)
yaml.add_representer(OrderedDict, represent_ordereddict)


def represent_tuple(dumper, data):
    return yaml.nodes.SequenceNode(
        u'tag:yaml.org,2002:seq',
        [dumper.represent_data(item) for item in data],
        flow_style=True,
    )
yaml.add_representer(tuple, represent_tuple)


def dump_to_yaml(data, f):
    # TODO gonna need a better way to handle flow style
    yaml.dump(
        data, f,
        default_flow_style=False,
        allow_unicode=True,
    )


def collect_text(texts, text_type, id):
    return OrderedDict(
        (language, texts[language][text_type][id])
        for language in CANON_LANGUAGES)


def extract_data(root, out):
    # TODO big conceptual question for the yaml thing: how do we decide how the
    # identifiers work in the per-version data?  the "global" identifiers are
    # in theory based on the names from the latest version, and the game dump
    # scripts shouldn't have to care about what the latest version is
    # 1. make the canon data not be keyed by identifier (makes it hard to
    # follow what's going on in flavor text files etc, and unclear how to match
    # up items across versions)
    # 2. make each version's data keyed by its own identifiers (makes it hard
    # to align them all when loading everything, and unclear how to match up
    # items whose names change across versions)
    # 3. hardcode a mapping of version+identifier pairs to their current
    # identifiers, when they changed, which is a little ugly but also solves
    # all the match-up problems and is what we'd basically have to do anyway

    # -------------------------------------------------------------------------
    # Names and flavor text

    texts = {}
    #for lang, fn in ORAS_SCRIPT_FILES.items():
    for lang, fn in SUMO_SCRIPT_FILES.items():
        texts[lang] = {}
        with read_garc(root / fn) as garc:
            #for entryname, entryid in ORAS_SCRIPT_ENTRIES.items():
            for entryname, entryid in SUMO_SCRIPT_ENTRIES.items():
                entry = garc[entryid][0]
                texts[lang][entryname] = decrypt_xy_text(entry.read())

    identifiers = {}
    # FIXME should use a known list, mayyybe compare against this
    identifiers['species'] = list(map(make_identifier, texts['en']['species-names']))
    # This is totally wrong, but the Pokémon loop below fixes it as it goes
    # FIXME okay that bit at the end is dumb
    identifiers['pokémon'] = identifiers['species'][:] + [None] * 1000
    identifiers['move'] = list(map(make_identifier, texts['en']['move-names']))
    identifiers['item'] = list(map(make_identifier, texts['en']['item-names']))
    identifiers['ability'] = list(map(make_identifier, texts['en']['ability-names']))

    textdir = out / 'script'
    if not textdir.exists():
        textdir.mkdir()
    for lang in CANON_LANGUAGES:
        with (textdir / (lang + '.yaml')).open('w') as f:
            # TODO this should use identifiers, not be lists
            # TODO need to skip slot 0 which is junk
            dump_to_yaml(texts[lang], f)


    """
    # Encounters
    22:42 < magical> note to self: X/Y ambush encounters are found in DllField.cro, starting at 0xf40d0
    23:02 < magical> friend safari pokemon at 0x13d34a
    # TODO move mee elsewheeere -- actually all of these should be in their own pieces
    places = OrderedDict()
    name_index_to_place = {}
    name_index_counts = Counter()
    zones = {}
    zone_to_name_index = {}
    with read_garc(root / 'rom/a/0/1/3') as garc:
        # Fetch the pointer table from the encounter file first, mostly so we
        # can figure out which zones have no encounters at all.  For whatever
        # reason, a zone with no encounters still has data -- but it uses the
        # same pointer as the following zone.  I don't know if the pointers
        # were intended to be used as ranges or what, but it's a handy signal.
        f = garc[-1][0]
        # TODO SIGH, translate this to construct, i guess
        magic = f.read(2)
        assert magic == b'EN'
        num_records = int.from_bytes(f.read(2), 'little')
        encounter_pointers = []
        for n in range(num_records):
            encounter_pointers.append(int.from_bytes(f.read(4), 'little'))
        empty_zones = set()
        for n in range(num_records - 1):
            if encounter_pointers[n] == encounter_pointers[n + 1]:
                empty_zones.add(n)

        # Every file in this GARC is ZO (zonedata) except the last one, which
        # is a table of encounters for each zone.
        num_zones = len(garc) - 1
        for z in range(num_zones):
            if z in empty_zones:
                # TODO later we may want these, to hang events off of etc
                continue

            zone = OrderedDict()
            zone['game-index'] = z
            zones[z] = zone

            # TODO probably worth trying to parse this stuff for real later
            data = garc[z][0].read()
            name_index = int.from_bytes(data[56:58], 'little')
            name_bits = name_index >> 9
            name_index &= 0x1ff

            zone_to_name_index[z] = name_index
            name_index_counts[name_index] += 1

            # Create places as we go, but DO NOT assign zones to places yet,
            # since the logic for figuring out zone identifiers is different
            # for places with only one zone
            if name_index not in name_index_to_place:
                place = OrderedDict()
                place['unknown--gen6-name-bits'] = name_bits
                place['name'] = OrderedDict()
                place['alternate-name'] = OrderedDict()
                for language in CANON_LANGUAGES:
                    name, altname = (
                        texts[language]['zone-names'][name_index:name_index + 2])
                    place['name'][language] = name
                    if altname:
                        place['alternate-name'][language] = altname
                # Drop this dict entirely if there are no alt names
                if not place['alternate-name']:
                    del place['alternate-name']

                name_index_to_place[name_index] = place

                ident = ORAS_ZONE_NAME_INDEX_TO_VEEKUN_LOCATION.get(name_index)
                if not ident:
                    # Not in veekun yet...
                    place['veekun--new'] = True
                    ident = make_identifier(place['name']['en'])
                places[ident] = place
                # TODO ugh
                place['_identifier'] = ident

                place['zones'] = OrderedDict()

        # Some encounters are used more than once
        seen_encounters = {}
        for z, ptr in enumerate(encounter_pointers):
            if z in empty_zones:
                continue

            zone = zones[z]
            name_index = zone_to_name_index[z]
            place = name_index_to_place[name_index]

            # Now we have all the zones, so we can figure out identifiers and
            # assign the zone to its parent place
            identifier = place['_identifier']
            if name_index_counts[name_index] > 1:
                # TODO are these names /sometimes/ official?  e.g. doesn't
                # "B1F" appear sometimes?
                subidentifier = ORAS_ZONE_INDEX_TO_VEEKUN_AREA.get(z)
                if not subidentifier:
                    subidentifier = "oras-unknown-{}".format(z)

                identifier = "{}--{}".format(identifier, subidentifier)
            place['zones'][identifier] = zone

            # Snag the actual encounters, if any.
            zone['encounters'] = OrderedDict()
            # TODO dumb hack for soaring through the sky, which is...  nothing
            if not f.read(1):
                continue
            f.seek(ptr)
            encounter_table = encounter_table_struct.parse_stream(f)
            n = 0
            for method, chances in ORAS_ENCOUNTER_SLOTS:
                rate_attr = method.replace('-', '_') + '_rate'
                rate = getattr(encounter_table, rate_attr)
                # TODO where does rate fit in here?
                if rate == 0:
                    # TODO wrong for hordes
                    n += len(chances)
                    continue
                encounters = zone['encounters'][method] = []
                for chance in chances:
                    if isinstance(chance, tuple):
                        chance, groupsize = chance
                    else:
                        groupsize = 1
                    encounter = []
                    for _ in range(groupsize):
                        enc = encounter_table.encounter[n]
                        # TODO assert always zero when rate is zero, never zero when rate isn't
                        if enc.pokemon_id != 0:
                            if enc.min_level == enc.max_level:
                                levels = str(enc.min_level)
                            else:
                                levels = "{} - {}".format(enc.min_level, enc.max_level)
                            pokemon_ident = identifiers['pokémon'][enc.pokemon_id & 0x1ff]
                            pokemon_form_bits = enc.pokemon_id >> 9
                            # TODO maybe turn this into, i have no idea, a
                            # custom type?  something forcibly short??
                            # TODO what do i do with the form bits?
                            encounter.append("{} {}".format(pokemon_ident, levels))
                        n += 1

                    if groupsize == 1:
                        encounters.extend(encounter)
                    else:
                        encounters.append(encounter)

    with (out / 'places.yaml').open('w') as f:
        dump_to_yaml(places, f)
    return
    """


    # -------------------------------------------------------------------------
    # Scrape some useful bits from the binary
    with (root / 'exe/code.bin').open('rb') as f:
        # Tutored moves
        # TODO i think these are oras only?  do they exist in sumo?  xy?
        tutor_moves = dict(tutors=ORAS_NORMAL_MOVE_TUTORS)
        f.seek(0x004960f8)
        for n in range(1, 5):
            key = "bp_tutors{}".format(n)
            moves = tutor_moves[key] = []
            while True:
                moveid, = struct.unpack('<H', f.read(2))
                if moveid >= len(identifiers['move']):
                    break
                moves.append(identifiers['move'][moveid])

        # TMs
        machines = []
        #f.seek(0x004a67ee)  # ORAS
        f.seek(0x0049795a)  # SUMO
        # TODO magic number (107)
        machineids = struct.unpack('<107H', f.read(2 * 107))
        # TODO dunno if this is still true
        # Order appears to be based on some gen 4 legacy: TMs 1 through 92, HMs
        # 1 through 6, then the other eight TMs and the last HM.  But the bits
        # in the Pokémon structs are in the expected order of 1 through 100, 1
        # through 7
        machines = [
            identifiers['move'][moveid]
            for moveid in
                machineids[0:92] +
                machineids[98:106] +
                machineids[92:98] +
                machineids[106:]
        ]

    # -------------------------------------------------------------------------
    # Abilities
    all_abilities = OrderedDict()
    for i, identifier in enumerate(identifiers['ability']):
        if i == 0:
            # Dummy non-ability
            continue
        ability = all_abilities[identifier] = schema.Ability()
        ability.name = collect_text(texts, 'ability-names', i)
        ability.flavor_text = collect_text(texts, 'ability-flavor', i)
        print(repr(ability.flavor_text['en']))

    with (out / 'abilities.yaml').open('w') as f:
        f.write(Camel([schema.POKEDEX_TYPES]).dump(all_abilities))




    # -------------------------------------------------------------------------
    # Pokémon structs
    mega_evolutions = get_mega_evolutions(root)
    all_pokémon = OrderedDict()
    pokemon_data = []
    with read_garc(root / 'rom/a/0/1/7') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/9/5') as garc:  # ORAS
        personals = [subfile[0].read() for subfile in garc]
    _pokemon_forms = {}  # "real" species id => (base species id, form name id)
    _next_name_form_id = 803#723  # TODO magic numbers
    print("number of flavor texts", len(texts['en']['species-flavor-moon']))
    for i, personal in enumerate(personals[:-1]):
        record = pokemon_struct.parse(personal)

        # FIRST THINGS FIRST: let's deal with forms.
        # TODO some pokemon, like unown, /only/ have sprite variations, so they
        # don't have a form_species_start here.  what do i do about them?
        if (record.form_count > 1) != bool(record.form_species_start):
            print("!!! sprite-only forms, argh")
        # The > i check makes sure we don't run this bit a second time when we
        # hit the forms themselves
        if record.form_count > 1 and record.form_species_start > i:
            megas = mega_evolutions[i]
            if len(megas) == 1:
                assert i not in FORM_NAMES
                form_names = ['mega']
            elif len(megas) == 2:
                assert i not in FORM_NAMES
                form_names = ['mega-x', 'mega-y']
            else:
                assert not megas
                form_names = FORM_NAMES[i][1:]
                # Fix our own name if necessary
                if FORM_NAMES[i][0]:
                    identifiers['pokémon'][i] += '-' + FORM_NAMES[i][0]

            if record.form_count - 1 != len(form_names):
                print("!!!!! MISMATCH", record.form_count - 1, len(form_names))
            for offset in range(record.form_count - 1):
                # Form names appear to be all just jammed at the end in order,
                # completely unrelated to either of the "start" offsets here
                #form_name = texts['en']['form-names'][_next_name_form_id]

                # TODO still no idea how "intangible" forms are being
                # handled in the new schema
                _pokemon_forms[record.form_species_start + offset] = i, _next_name_form_id
                _next_name_form_id += 1

                identifiers['pokémon'][record.form_species_start + offset] = identifiers['species'][i] + '-' + form_names[offset]

        pokémon = schema.Pokémon()
        all_pokémon[identifiers['pokémon'][i]] = pokémon
        pokémon.game_index = i

        if i in _pokemon_forms:
            base_species_id, form_name_id = _pokemon_forms[i]
        else:
            base_species_id = i
            form_name_id = i
        # TODO i observe this is explicitly a species name, the one thing that
        # really is shared between forms
        pokémon.name = collect_text(texts, 'species-names', base_species_id)
        pokémon.genus = collect_text(texts, 'genus-names', base_species_id)
        # FIXME ho ho, hang on a second, forms have their own flavor text too!!
        # TODO well this depends on which game you're dumping
        pokémon.flavor_text = collect_text(texts, 'species-flavor-moon', base_species_id)
        # FIXME include form names?  only when they exist?  can that be
        # inconsistent between languages?

        pokémon.base_stats = {
            'hp': record.stat_hp,
            'attack': record.stat_atk,
            'defense': record.stat_def,
            'special-attack': record.stat_spatk,
            'special-defense': record.stat_spdef,
            'speed': record.stat_speed,
        }
        # FIXME pokémon.types = [record.type1]
        pokémon.capture_rate = record.capture_rate
        # TODO stage?
        # FIXME effort
        # Held items are a bit goofy; if the same item is in all three slots, it always appears!
        pokémon.held_items = {}
        if 0 != record.held_item1 == record.held_item2 == record.held_item3:
            pokémon.held_items[identifiers['item'][record.held_item1]] = 100
        else:
            if record.held_item1:
                pokémon.held_items[identifiers['item'][record.held_item1]] = 50
            if record.held_item2:
                pokémon.held_items[identifiers['item'][record.held_item2]] = 5
            if record.held_item3:
                pokémon.held_items[identifiers['item'][record.held_item3]] = 1

        # TODO i think this needs some normalizing?  maybe renaming because
        # this doesn't at all imply what it means
        pokémon.gender_rate = record.gender_rate

        pokémon.hatch_counter = record.steps_to_hatch
        pokémon.base_happiness = record.base_happiness
        pokémon.growth_rate = record.growth_rate
        # FIXME egg groups
        pokémon.abilities = [
            identifiers['ability'][ability]
            for ability in (record.ability1, record.ability2, record.ability_hidden)
        ]
        # FIXME safari escape??
        # FIXME form stuff
        # FIXME color
        pokémon.base_experience = record.base_exp
        # FIXME what units are these!
        pokémon.height = record.height
        pokémon.weight = record.weight

        pokémon.moves = {}




        # TODO transform to an OD somehow probably
        pokemon_data.append(record)
        print("{:4d} {:25s} {} {:5d} {:5d} {:20s} {:4d} {:4d} {:2d}".format(
            i,
            identifiers['pokémon'][i],
            ('0'*16 + bin(record.mystery1)[2:])[-16:],
            record.mystery2,
            record.stage,
            texts['en']['form-names'][i],
            record.form_species_start,
            record.form_sprite_start,
            record.form_count,
        ))

    #for i in range(723, 825 + 1):
    #    base_species_id, form_name_id = _pokemon_forms[i]
    #    species_name = texts['en']['species-names'][base_species_id]
    #    form_name = texts['en']['form-names'][form_name_id]
    #    print(i, species_name, '/', form_name)

    # -------------------------------------------------------------------------
    # Move stats
    #with read_garc(root / 'rom/a/1/8/9') as garc:  # ORAS
    with read_garc(root / 'rom/a/0/1/1') as garc:  # SUMO
        # Only one subfile
        # TODO assert this wherever i do it
        data = garc[0][0].read()
        print(Struct('magic' / Bytes(2), 'count' / Int16ul, 'pointers' / Array(16, Int32ul)).parse(data))
        print(move_struct.sizeof())
        records = move_container_struct.parse(data)
        for i, record in enumerate(records):
            #print(texts['en']['move-names'][i])
            #print(record)
            # TODO with the release of oras all moves have contest types and effects again!  where are they??
            print("{:3d} {:30s} | {m.type:10s} {m.category:3d} / {m.power:3d} {m.pp:2d} {m.accuracy:3d} / {m.priority:2d} {m.range:2d} {m.damage_class:1d} / {m.effect:3d} {m.caused_effect:3d} {m.effect_chance:3d}  --  {m.status:3d} {m.min_turns:3d} {m.max_turns:3d} {m.crit_rate:3d} {m.flinch_chance:3d} {m.recoil:4d} {m.healing:3d} / {m.stat_change!r} {m.stat_amount!r} {m.stat_chance!r} ~ {m.padding0:3d} {m.padding1:3d} {m.flags:04x} {m.padding2:3d} {m.extra:3d} {m.extra2:10d}".format(
                i,
                texts['en']['move-names'][i],
                m=record,
            ))
    return

    # Egg moves
    with read_garc(root / 'rom/a/0/1/2') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/9/0') as garc:  # ORAS
        print("number of egg moves:", len(garc))
        for i, subfile in enumerate(garc):
            ident = identifiers['pokémon'][i]
            data = subfile[0].read()
            if not data:
                continue
            container = egg_moves_struct.parse(data)
            print(i, ident, container.first_form_id, container.moveids)
            # FIXME: 961 pokémon, 1063 named forms, but 1048 egg movesets.
            # what?  they get completely out of order after 802 and i don't
            # know how to fix this.  didn't magical write some code...?
            if i > len(identifiers['species']):
                continue
            moveset = all_pokémon[ident].moves
            eggset = moveset['egg'] = []
            for moveid in container.moveids:
                eggset.append(identifiers['move'][moveid])

    # Level-up moves
    with read_garc(root / 'rom/a/0/1/3') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/9/1') as garc:  # ORAS
        print("number of level-up moves", len(garc))
        for i, subfile in enumerate(garc):
            ident = identifiers['pokémon'][i]
            level_up_moves = subfile[0].read()
            moveset = all_pokémon[ident].moves
            levelset = moveset['level'] = []
            lastlevel = None
            order = 1
            for pair in level_up_moves_struct.parse(level_up_moves):
                # End is indicated with -1, -1
                if pair.moveid <= 0:
                    break
                # FIXME this is a goofy-looking structure, but it makes the
                # yaml come out nicely?
                levelset.append({
                    pair.level: identifiers['move'][pair.moveid],
                })

                if pair.level == lastlevel:
                    order += 1
                else:
                    lastlevel = pair.level
                    order = 1

    # Evolution
    #with read_garc(root / 'rom/a/1/9/2') as garc:  # ORAS
    #with read_garc(root / 'rom/a/0/1/4') as garc:  # SUMO?
    #    for subfile in garc:
    #        evolution = subfile[0].read()
    #        print(repr(evolution))
    # Mega evolution
    #with read_garc(root / 'rom/a/1/9/3') as garc:  # ORAS
    #with read_garc(root / 'rom/a/0/1/5') as garc:  # SUMO?
    #    for subfile in garc:
    #        evolution = subfile[0].read()
    #        print(repr(evolution))
    # TODO what is a/1/9/4 (ORAS) or a/0/1/6 (SUMO)?  8 files of 404 bytes each
    # Baby Pokémon
    #with read_garc(root / 'rom/a/1/9/6') as garc:  # ORAS
    #with read_garc(root / 'rom/a/0/1/8') as garc:  # SUMO?
    #    for subfile in garc:
    #        baby_pokemon = subfile[0].read()
    #        print(repr(baby_pokemon))

    # Item stats
    # TODO
    #with read_garc(root / 'rom/a/1/9/7') as garc:  # ORAS
    with read_garc(root / 'rom/a/0/1/9') as garc:  # ORAS
        for subfile in garc:
            item_stats = subfile[0].read()

    # Tutor moves (from the personal structs)
    for i, datum in enumerate(pokemon_data):
        ident = identifiers['pokémon'][i]
        moveset = all_pokémon[ident].moves
        tutorset = moveset['tutor'] = []
        for key, tutors in tutor_moves.items():
            for bit, moveident in enumerate(tutors):
                if moveident in ORAS_UNUSED_MOVE_TUTORS:
                    continue
                if not datum[key] & (1 << bit):
                    continue
                tutorset.append(moveident)

        # TMs
        machineset = moveset['machine'] = []
        for bit, moveident in enumerate(machines):
            if not datum['machines'][bit]:
                continue
            machineset.append(moveident)

    with (out / 'pokemon.yaml').open('w') as f:
        #dump_to_yaml(all_pokémon, f)
        f.write(Camel([schema.POKEDEX_TYPES]).dump(all_pokémon))


def get_mega_evolutions(root):
    """Return a dict mapping Pokémon ids to a list of mega evolution records.
    """
    megas = {}
    #with read_garc(root / 'rom/a/1/9/3') as garc:  # oras
    with read_garc(root / 'rom/a/0/1/5') as garc:  # SUMO
        for pokemonid, subfile in enumerate(garc):
            megas[pokemonid] = pokemon_mega_evolutions_struct.parse_stream(subfile[0])

    return megas


class SpriteFileNamer:
    """Do you have a big set of sprites, and a separate list of stuff
    identifying them, as happens in XY and ORAS?  I will sort that all out for
    you.
    """
    def __init__(self, out, mega_counts, form_names):
        self.out = out
        self.mega_counts = mega_counts
        self.form_names = form_names

        self.index_to_filenames = defaultdict(list)
        self.seen = set()

    def add(self, index, pokemonid, formid=0, right=False, back=False, shiny=False, female=False):
        # Check that we don't try to do the same one twice
        if index in self.index_to_filenames:
            raise ValueError("Index {} is already {}".format(
                index, self.index_to_filenames[index]))

        key = (pokemonid, formid, right, back, shiny, female)
        if key in self.seen:
            raise ValueError("Duplicate sprite: {!r}".format(key))
        self.seen.add(key)

        # Figure out the form name
        # TODO this assumes a Pokémon cannot have both forms and mega
        # evolutions, which is true...  for now
        if pokemonid in self.form_names:
            form = self.form_names[pokemonid][formid]
        elif formid == 0:
            form = None
        elif self.mega_counts[pokemonid]:
            if self.mega_counts[pokemonid] == 1:
                form = ['mega'][formid - 1]
            elif self.mega_counts[pokemonid] == 2:
                form = ['mega-x', 'mega-y'][formid - 1]
            else:
                raise ValueError(
                    "Don't know how to name {} mega evolutions for Pokémon {}"
                    .format(self.mega_counts[pokemonid], pokemonid))
        else:
            # TODO should use warnings for this so it works for new games
            warnings.warn("Don't know any forms for Pokemon {}".format(pokemonid))
            form = "form-{}".format(formid)

        # Construct the directory
        parts = []
        if right:
            parts.append('right')
        if back:
            parts.append('back')
        if shiny:
            parts.append('shiny')
        if female:
            parts.append('female')

        # Build the final filename
        bare_filename = "{}.png".format(pokemonid)
        if form:
            parts.append("{}-{}.png".format(pokemonid, form))
        else:
            parts.append(bare_filename)
        filename = '/'.join(parts)
        self.index_to_filenames[index].append(filename)

        # For named "default" forms, create two output files
        if form and formid == 0:
            parts[-1] = bare_filename
            self.index_to_filenames[index].append('/'.join(parts))

        # Special case for Meowstic: duplicate its female form as a formless
        # female sprite
        if form == 'female' and not female:
            parts.insert(-1, 'female')
            parts[-1] = bare_filename
            self.index_to_filenames[index].append('/'.join(parts))

    def inject(self, index, filename):
        """Manually specify the filename for an index.  Helpful for edge cases
        like egg sprites.
        """
        if index in self.index_to_filenames:
            raise ValueError("Index {} is already {}".format(
                index, self.index_to_filenames[index]))

        self.index_to_filenames[index].append(filename)

    # TODO we oughta create aliases for any that are missing?
    # pumpkaboo/gourgeist and arceus don't have separate box icons, for
    # example.
    @contextmanager
    def open(self, index, prefix=None):
        out = self.out
        if prefix:
            out /= prefix

        filenames = self.index_to_filenames[index]

        if len(filenames) == 0:
            raise RuntimeError("Don't have filenames for index {}".format(index))

        fn = out / filenames[0]
        if not fn.parent.exists():
            fn.parent.mkdir(parents=True)
        with fn.open('wb') as f:
            yield f

        for path in filenames[1:]:
            fn2 = out / path
            # TODO this duplication is annoying and we can probably do it in
            # one fell swoop instead of constantly rechecking, maybe during the
            # same timeframe that we fill in missing forms
            if not fn2.parent.exists():
                fn2.parent.mkdir(parents=True)
            shutil.copyfile(str(fn), str(fn2))


def extract_box_sprites(root, out):
    mega_counts = {
        id: len(megas)
        for (id, megas) in get_mega_evolutions(root).items()
    }
    namer = SpriteFileNamer(out, mega_counts, FORM_NAMES)

    with (root / 'exe/code.bin').open('rb') as f:
        # Form configuration, used to put sprites in the right order
        # NOTE: in x/y the address is 0x0043ea98
        #f.seek(0x0047d650)  # ORAS
        f.seek(0x004999d0)  # SUMO
        # Discard dummy zero sprite
        pokemon_sprite_struct.parse_stream(f)
        n = 0
        while True:
            sprite = pokemon_sprite_struct.parse_stream(f)
            # This is not particularly reliable, but the data immediately
            # following this list is some small 32-bit values, so the female
            # index will be (illegally) zero
            if not sprite.female_index:
                break

            n += 1
            namer.add(sprite.index, n)
            if sprite.female_index != sprite.index:
                namer.add(sprite.female_index, n, female=True)
            # Note that these addresses are relative to RAM, and the binary is
            # loaded into RAM starting at 0x100000, so we need to subtract that
            # to get a file position
            pos = f.tell()
            form_indices = ()
            right_indices = ()

            if sprite.form_index_offset:
                f.seek(sprite.form_index_offset - 0x100000)
                form_indices = struct.unpack(
                    "<{}H".format(sprite.form_count),
                    f.read(2 * sprite.form_count),
                )
                for form, form_idx in enumerate(form_indices):
                    # Ignore the first form, since it's the default and thus
                    # covered by `index` already
                    if form == 0:
                        continue
                    if form_idx == sprite.index:
                        continue
                    namer.add(form_idx, n, form)

            if sprite.right_index_offset:
                f.seek(sprite.right_index_offset - 0x100000)
                right_indices = struct.unpack(
                    "<{}H".format(sprite.right_count),
                    f.read(2 * sprite.right_count),
                )
                if sprite.form_count:
                    assert sprite.right_count == sprite.form_count
                    for form, (form_idx, right_idx) in enumerate(zip(form_indices, right_indices)):
                        if form_idx == right_idx:
                            continue
                        namer.add(right_idx, n, form, right=True)
                else:
                    assert sprite.right_count == 2
                    assert right_indices[0] == right_indices[1]
                    if right_indices[0] != sprite.index:
                        namer.add(right_indices[0], n, right=True)

            f.seek(pos)

    pokemon_sprites_dir = out
    if not pokemon_sprites_dir.exists():
        pokemon_sprites_dir.mkdir()
    # with read_garc(root / 'rom/a/0/9/1') as garc:  # ORAS
    # TODO what's in 2/5/3?
    with read_garc(root / 'rom/a/0/6/2') as garc:  # SUMO
        from .lib.clim import decode_clim
        for i, subfile in enumerate(garc):
            # TODO ORAS ONLY
            #elif i == 333:
            #    # Duplicate Entei sprite that's not used
            #    continue
            if i == len(garc) - 1:
                # Very last one is egg
                namer.inject(i, 'egg.png')

            # TODO this is bad.
            if not namer.index_to_filenames[i]:
                # Unused sprite -- e.g. index 0, or one of the dummies in SUMO
                continue

            data = subfile[0].read()
            image_data = decode_clim(data)

            # TODO this is bad.
            if 'right/' in namer.index_to_filenames[i][0]:
                image_data.mirror()

            with namer.open(i) as f:
                image_data.write_to_png(f)


def extract_dex_sprites(root, out):
    # Some Pokémon have dex sprites for their forms, too, and they're all
    # clustered together, so we have to do a little work to fix the numbering.
    # Luckily the dex sprites are in the same order as the models
    # (unsurprising, as they're just model renders), which also tells us what
    # Pokémon have female forms.  The mega evolution map tells us which forms
    # are megas, and the rest are listed manually above as FORM_NAMES.

    mega_counts = {
        id: len(megas)
        for (id, megas) in get_mega_evolutions(root).items()
    }
    namer = SpriteFileNamer(out, mega_counts, FORM_NAMES)

    # TODO Meowstic is counted as simply female in here, but should probably be
    # saved with a form filename as well
    # TODO should skip the extra komala and the totem forms
    #with read_garc(root / 'rom/a/0/0/8') as garc:  # ORAS
    with read_garc(root / 'rom/a/0/9/4') as garc:  # SUMO
        f = garc[0][0]
        pokemonid = 0
        while True:
            pokemonid += 1
            data = f.read(4)
            # All zeroes means we're done.  Maybe.  More data follows after
            # this, but it doesn't seem to be the same format, and I don't know
            # what exactly it's for.
            if data == b'\x00\x00\x00\x00':
                break

            # Index of the first model (also zero-indexed), how many models the
            # Pokémon has, and some flags
            start, count, flags = struct.unpack('<HBB', data)
            # TODO this was CHANGED for SUMO -- for ORAS all the shiny sprites are a second block at the end!
            #model_num = start + 1
            model_num = start * 2 + 1
            #print("pokemon {:3d} -- start {:4d} ({:4d}) -- count {:2d} -- flags {:08b}".format(pokemonid, start, model_num, count, flags))
            # Fix a few odd disconnects between the model listing and the
            # actual dex sprites.
            # TODO there must be a dex sprite index somewhere, this is silly
            # Xerneas has two models, but three dex sprites
            if pokemonid == 716:
                count = 2
            # Lurantis has two models, but one dex sprite
            if pokemonid == 754:
                count = 1
                flags &= ~4
            # Salazzle has two models, but one dex sprite
            if pokemonid == 758:
                count = 1
                flags &= ~4
            # Komala has one model, but two dex sprites
            # FIXME probably skip extracting it at all
            if pokemonid == 775:
                count = 2
            # The above all naturally throw later numbering off; compensate
            if 716 < pokemonid <= 754:
                model_num += 2
            elif 758 < pokemonid <= 775:
                model_num -= 2

            namer.add(model_num, pokemonid)
            # TODO SUMO ONLY (should be += 1 for ORAS)
            namer.add(model_num + 1, pokemonid, shiny=True)
            model_num += 2

            form_count = count - 1  # discount "base" form
            # TODO this is only used for ORAS, and should be done another way anyway
            total_model_count = model_num + count - 1

            # Don't know what flag 1 is; everything has it.
            # Flag 2 means the first alternate form is female.
            if flags & 2:
                assert form_count > 0
                form_count -= 1
                namer.add(model_num, pokemonid, female=True)
                namer.add(model_num + 1, pokemonid, female=True, shiny=True)
                model_num += 2
            # Flag 4 just means there are more forms?
            if flags & 4:
                assert form_count

            for formid in range(1, form_count + 1):
                namer.add(model_num, pokemonid, formid)
                namer.add(model_num + 1, pokemonid, formid, shiny=True)
                model_num += 2

    # And now, do the ripping
    #with read_garc(root / 'rom/a/2/6/3') as garc:  # ORAS
    with read_garc(root / 'rom/a/2/4/0') as garc:  # SUMO
        from .lib.clim import decode_clim
        from .lib.etc1 import decode_etc1
        for i, subfile in enumerate(garc):
            if i == 0:
                # Dummy sprite, not interesting to us
                continue

            data = subfile[0].read()
            """
            with open("{}/{}.png".format(str(out), i), 'wb') as f:
                write_clim_to_png(f, *decode_etc1(data))
            continue
            # TODO THIS IS ALL ORAS ONLY
            shiny_prefix = None
            if i > total_model_count:
                i -= total_model_count
                # TODO this should be a real feature, as should the 'right'
                # hack in the other code
                shiny_prefix = 'shiny/'

            elif 37 <= i <= 41:
                # Cosplay Pikachu's outfits -- the sprites are blank, so saving
                # these is not particularly useful
                continue
            """

            data = subfile[0].read()
            with namer.open(i) as f:
                decode_etc1(data).write_to_png(f)
            # TODO ORAS
            #with namer.open(i, prefix=shiny_prefix) as f:
            #    decode_clim(data).write_to_png(f)


def _munge_source_arg(strpath):
    path = Path(strpath)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(
            "{!r} is not a directory".format(strpath))

    # TODO something something romfs, exefs
    return path

def make_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument('what', choices=('data', 'dex-sprites', 'box-sprites'), help='what to extract')
    # TODO should verify that this is an actual game dump, and find the rom/exe
    p.add_argument('source', type=_munge_source_arg, help='path to an unpacked game image')
    p.add_argument('dest', type=_munge_source_arg, help='directory to dump the results into')

    return p


def main(args):
    parser = make_arg_parser()
    args = parser.parse_args(args)

    # TODO support 'all', and just make some subdirectories per thing
    # TODO or maybe merge all the sprite things together since stuff will need moving around anyway idk
    if args.what == 'data':
        extract_data(args.source, args.dest)
    elif args.what == 'dex-sprites':
        extract_dex_sprites(args.source, args.dest)
    elif args.what == 'box-sprites':
        extract_box_sprites(args.source, args.dest)


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
