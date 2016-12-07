"""Dumps data from Omega Ruby and Alpha Sapphire.

Filesystem reference: http://www.projectpokemon.org/wiki/ORAS_File_System
"""
import argparse
from collections import Counter
from collections import OrderedDict
from collections import defaultdict
from contextlib import contextmanager
import io
import itertools
import math
from pathlib import Path
import re
import shutil
import struct

from construct import Array, BitField, Bitwise, Magic, OptionalGreedyRange, Padding, Pointer, Struct, SLInt8, SLInt16, ULInt8, ULInt16, ULInt32
import png
import yaml

from .lib.garc import GARCFile, decrypt_xy_text
from .lib.text import merge_japanese_texts

# TODO auto-detect rom vs romfs vs...  whatever

# TODO fix some hardcoding in here
# TODO finish converting garc parsing to use construct, if possible, i think (i would not miss substream)
# way way more sprite work in here...

# TODO would be nice to have meaningful names for the file structure instead of sprinkling hardcoded ones throughout


CANON_LANGUAGES = ('ja', 'en', 'fr', 'it', 'de', 'es', 'ko')
ORAS_SCRIPT_FILES = {
    'ja-kana': 'rom/a/0/7/1',
    'ja-kanji': 'rom/a/0/7/2',
    'en': 'rom/a/0/7/3',
    'fr': 'rom/a/0/7/4',
    'it': 'rom/a/0/7/5',
    'de': 'rom/a/0/7/6',
    'es': 'rom/a/0/7/7',
    'ko': 'rom/a/0/7/8',
}
SUMO_SCRIPT_FILES = {
    'ja-kana': 'rom/a/0/3/0',
    'ja-kanji': 'rom/a/0/3/1',
    'en': 'rom/a/0/3/2',
    'fr': 'rom/a/0/3/3',
    'it': 'rom/a/0/3/4',
    'de': 'rom/a/0/3/5',
    'es': 'rom/a/0/3/6',
    'ko': 'rom/a/0/3/7',
    'zh-simplified': 'rom/a/0/3/8',
    'zh-traditional': 'rom/a/0/3/9',
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
# The first element in each list is the name of the BASE form -- if it's not
# None, the base form will be saved under two filenames
ORAS_EXTRA_SPRITE_NAMES = {
    # Cosplay Pikachu
    25: (None, 'rock-star', 'belle', 'pop-star', 'phd', 'libre', 'cosplay'),
    # Unown
    201: tuple('abcdefghijklmnopqrstuvwxyz') + ('exclamation', 'question'),
    # Castform
    351: (None, 'sunny', 'rainy', 'snowy'),
    # Kyogre and Groudon
    382: (None, 'primal',),
    383: (None, 'primal',),
    # Deoxys
    386: ('normal', 'attack', 'defense', 'speed'),
    # Burmy and Wormadam
    412: ('plant', 'sandy', 'trash'),
    413: ('plant', 'sandy', 'trash'),
    # Cherrim
    421: ('overcast', 'sunshine',),
    # Shellos and Gastrodon
    422: ('west', 'east',),
    423: ('west', 'east',),
    # Rotom
    479: (None, 'heat', 'wash', 'frost', 'fan', 'mow'),
    # Giratina
    487: ('altered', 'origin',),
    # Shaymin
    492: ('land', 'sky',),
    # Arceus
    493: (
        'normal', 'fighting', 'flying', 'poison', 'ground', 'rock', 'bug',
        'ghost', 'steel', 'fire', 'water', 'grass', 'electric', 'psychic',
        'ice', 'dragon', 'dark', 'fairy',
    ),
    # Basculin
    550: ('red-striped', 'blue-striped',),
    # Darmanitan
    555: ('standard', 'zen',),
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
    # Hoopa
    720: ('confined', 'unbound'),
}


pokemon_struct = Struct(
    'pokemon',
    ULInt8('stat_hp'),
    ULInt8('stat_atk'),
    ULInt8('stat_def'),
    ULInt8('stat_speed'),
    ULInt8('stat_spatk'),
    ULInt8('stat_spdef'),
    ULInt8('type1'),
    ULInt8('type2'),
    ULInt8('catch_rate'),
    ULInt8('stage'),
    ULInt16('effort'),
    ULInt16('held_item1'),
    ULInt16('held_item2'),
    ULInt16('held_item3'),  # dark grass from bw, unused in oras?
    ULInt8('gender_rate'),
    ULInt8('steps_to_hatch'),
    ULInt8('base_happiness'),
    ULInt8('exp_curve'),
    ULInt8('egg_group1'),
    ULInt8('egg_group2'),
    ULInt8('ability1'),
    ULInt8('ability2'),
    ULInt8('ability_dream'),
    ULInt8('safari_escape'),
    ULInt16('form_species_start'),
    ULInt16('form_sprite_start'),
    ULInt8('form_count'),
    ULInt8('color'),
    ULInt16('base_exp'),
    ULInt16('height'),
    ULInt16('weight'),
    Bitwise(
        BitField('machines', 14 * 8, swapped=True),
    ),
    Padding(2),
    ULInt32('tutors'),
    ULInt16('mystery1'),
    ULInt16('mystery2'),
    ULInt32('bp_tutors1'),  # unused in sumo
    ULInt32('bp_tutors2'),  # unused in sumo
    ULInt32('bp_tutors3'),  # unused in sumo
    ULInt32('bp_tutors4'),  # sumo: big numbers for pikachu, eevee, snorlax, mew, starter evos, couple others??  maybe special z-move item?
    # TODO sumo is four bytes longer, not sure why, find out if those bytes are anything and a better way to express them
    OptionalGreedyRange(Magic(b'\x00')),
)

pokemon_mega_evolutions_struct = Array(
    2,  # NOTE: 3 for XY/ORAS, but i don't think the third is ever populated?
    Struct(
        'pokemon_mega_evolutions',
        ULInt16('number'),
        ULInt16('mode'),
        ULInt16('mega_stone_itemid'),
        Padding(2),
    )
)

egg_moves_struct = Struct(
    'egg_moves',
    ULInt16('count'),
    Array(
        lambda ctx: ctx.count,
        ULInt16('moveids'),
    ),
)

egg_moves_struct = Struct(
    'egg_moves',
    ULInt16('first_form_id'),  # TODO SUMO ONLY
    ULInt16('count'),
    Array(
        lambda ctx: ctx.count,
        ULInt16('moveids'),
    ),
)

level_up_moves_struct = OptionalGreedyRange(
    Struct(
        'level_up_pair',
        SLInt16('moveid'),
        SLInt16('level'),
    ),
)

move_struct = Struct(
    'move',
    ULInt8('type'),
    ULInt8('category'),
    ULInt8('damage_class'),
    ULInt8('power'),
    ULInt8('accuracy'),
    ULInt8('pp'),
    SLInt8('priority'),
    ULInt8('min_max_hits'),
    SLInt16('caused_effect'),
    ULInt8('effect_chance'),
    ULInt8('status'),
    ULInt8('min_turns'),
    ULInt8('max_turns'),
    ULInt8('crit_rate'),
    ULInt8('flinch_chance'),
    ULInt16('effect'),
    SLInt8('recoil'),
    ULInt8('healing'),
    ULInt8('range'),            # ok
    Bitwise(
        BitField('stat_change', 24),
    ),
    Bitwise(
        BitField('stat_amount', 24),
    ),
    Bitwise(
        BitField('stat_chance', 24),
    ),
    ULInt8('padding0'),         # ok
    ULInt8('padding1'),         # ok
    ULInt16('flags'),
    ULInt8('padding2'),         # ok
    ULInt8('extra'),
)
move_container_struct = Struct(
    'move_container',
    Magic(b'WD'),  # waza...  descriptions?
    ULInt16('record_ct'),
    Array(
        lambda ctx: ctx.record_ct,
        Struct(
            'records',
            ULInt32('offset'),
            Pointer(lambda ctx: ctx.offset, move_struct),
        ),
    ),
)

pokemon_sprite_struct = Struct(
    'pokemon_sprite_config',
    ULInt16('index'),
    ULInt16('female_index'),
    ULInt32('form_index_offset'),
    ULInt32('right_index_offset'),
    ULInt16('form_count'),
    ULInt16('right_count'),
)

encounter_struct = Struct(
    'encounter',
    # TODO top 5 bits are form stuff
    ULInt16('pokemon_id'),
    ULInt8('min_level'),
    ULInt8('max_level'),
)

encounter_table_struct = Struct(
    'encounter_table',
    ULInt8('walk_rate'),
    ULInt8('long_grass_rate'),
    ULInt8('hidden_rate'),
    ULInt8('surf_rate'),
    ULInt8('rock_smash_rate'),
    ULInt8('old_rod_rate'),
    ULInt8('good_rod_rate'),
    ULInt8('super_rod_rate'),
    ULInt8('horde_rate'),
    Magic(b'\x00' * 5),
    Array(61, encounter_struct),
    Magic(b'\x00' * 2),
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

    # Japanese text is special!  It's written in both kanji and kana, and we
    # want to combine them
    texts['ja'] = {}
    #for entryname in ORAS_SCRIPT_ENTRIES:
    for entryname in SUMO_SCRIPT_ENTRIES:
        kanjis = texts['ja-kanji'][entryname]
        kanas = texts['ja-kana'][entryname]
        # But not if they're names of things.
        # (TODO this might not be true in the case of, say, towns?  in which
        # case, what do we do?  we want to ultimately put these in urls and
        # whatnot, right, but we don't want furigana there  :S  do we need a
        # separate "identifier" field /per language/?)
        assert len(kanas) == len(kanjis)
        if kanjis == kanas:
            texts['ja'][entryname] = kanjis
        else:
            texts['ja'][entryname] = [
                merge_japanese_texts(kanji, kana)
                for (kanji, kana) in zip(kanjis, kanas)
            ]
    del texts['ja-kanji']
    del texts['ja-kana']

    identifiers = {}
    identifiers['species'] = []
    for i, (species_name, form_name) in enumerate(itertools.zip_longest(
            texts['en']['species-names'],
            texts['en']['form-names'],
            )):
        if species_name:
            ident = make_identifier(species_name)
        else:
            # TODO proooooobably fix this
            ident = 'uhhhhh'
            #print("??????", i, species_name, form_name)
        if form_name:
            ident = ident + '-' + make_identifier(form_name)
        # TODO hold up, how are these /species/ identifiers?
        identifiers['species'].append(ident)
    identifiers['move'] = [
        make_identifier(name)
        for name in texts['en']['move-names']
    ]

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
                            pokemon_ident = identifiers['species'][enc.pokemon_id & 0x1ff]
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
        machineids = struct.unpack('<107H', f.read(2 * 107))
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
    # Pokémon structs
    # TODO SUMO 0/1/8 seems to contain the index for the "base" species
    pokemon_data = []
    with read_garc(root / 'rom/a/0/1/7') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/9/5') as garc:  # ORAS
        personals = [subfile[0].read() for subfile in garc]
    _pokemon_forms = {}  # "real" species id => (base species id, form name id)
    _next_name_form_id = 723  # TODO magic number
    for i, personal in enumerate(personals[:-1]):
        record = pokemon_struct.parse(personal)
        # TODO transform to an OD somehow probably
        pokemon_data.append(record)
        print(i, hex(record.bp_tutors4))
        #print("{:3d} {:15s} {} {:5d} {:5d}".format(
        #    i,
        #    identifiers['species'][baseid],
        #    ('0'*16 + bin(record.mystery1)[2:])[-16:],
        #    record.mystery2,
        #    record.stage,
        #))
        # TODO some pokemon have sprite starts but no species start, because their sprites vary obv
        if record.form_count > 1:
            # The form names appear to be all just jammed at the end in order,
            # completely unrelated to either of the "start" offsets here
            for offset in range(record.form_count - 1):
                #form_name = texts['en']['form-names'][_next_name_form_id]

                if record.form_species_start:
                    # TODO still no idea how "intangible" forms are being
                    # handled in the new schema
                    _pokemon_forms[record.form_species_start + offset] = i, _next_name_form_id

                _next_name_form_id += 1

        if record.form_species_start:
            for offset in range(record.form_count - 1):
                # TODO grab the form names argh
                identifiers['species'][record.form_species_start + offset] = identifiers['species'][i]

    #for i in range(723, 825 + 1):
    #    base_species_id, form_name_id = _pokemon_forms[i]
    #    species_name = texts['en']['species-names'][base_species_id]
    #    form_name = texts['en']['form-names'][form_name_id]
    #    print(i, species_name, '/', form_name)

    # -------------------------------------------------------------------------
    # Move stats
    movesets = OrderedDict()
    with read_garc(root / 'rom/a/0/1/1') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/8/9') as garc:  # ORAS
        # Only one subfile
        data = garc[0][0].read()
        container = move_container_struct.parse(data)
        for n, record in enumerate(container.records):
            m = record.move
            # TODO with the release of oras all moves have contest types and effects again!  where are they??
            #print("{:3d} {:20s} | {m.type:3d} {m.power:3d} {m.pp:2d} {m.accuracy:3d} / {m.priority:2d} {m.range:2d} {m.damage_class:1d} / {m.effect:3d} {m.caused_effect:3d} {m.effect_chance:3d}  --  {m.status:3d} {m.min_turns:3d} {m.max_turns:3d} {m.crit_rate:3d} {m.flinch_chance:3d} {m.recoil:4d} {m.healing:3d} / {m.stat_change:06x} {m.stat_amount:06x} {m.stat_chance:06x} / {m.padding0:3d} {m.padding1:3d} {m.flags:04x} {m.padding2:3d} {m.extra:3d}".format(
            #    n,
            #    identifiers['move'][n],
            #    m=record.move,
            #))

    # Egg moves
    with read_garc(root / 'rom/a/0/1/2') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/9/0') as garc:  # ORAS
        for i, subfile in enumerate(garc):
            ident = identifiers['species'][i]
            data = subfile[0].read()
            if not data:
                continue
            container = egg_moves_struct.parse(data)
            moveset = movesets.setdefault(ident, OrderedDict())
            eggset = moveset['egg'] = []
            for moveid in container.moveids:
                eggset.append(identifiers['move'][moveid])

    # Level-up moves
    with read_garc(root / 'rom/a/0/1/3') as garc:  # SUMO
    #with read_garc(root / 'rom/a/1/9/1') as garc:  # ORAS
        for i, subfile in enumerate(garc):
            ident = identifiers['species'][i]
            level_up_moves = subfile[0].read()
            moveset = movesets.setdefault(ident, OrderedDict())
            levelset = moveset['level'] = []
            lastlevel = None
            order = 1
            for pair in level_up_moves_struct.parse(level_up_moves):
                # End is indicated with -1, -1
                if pair.moveid <= 0:
                    break
                levelset.append((
                    pair.level,
                    identifiers['move'][pair.moveid],
                ))

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
        ident = identifiers['species'][i]
        moveset = movesets.setdefault(ident, OrderedDict())
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
            if not datum['machines'] & (1 << bit):
                continue
            machineset.append(moveident)

    with (out / 'movesets.yaml').open('w') as f:
        dump_to_yaml(movesets, f)


def get_mega_counts(root):
    """Return a dict mapping Pokémon ids to how many mega evolutions each one
    has.
    """
    mega_counts = {}  # pokemonid => number of mega evos
    #with read_garc(root / 'rom/a/1/9/3') as garc:  # oras
    with read_garc(root / 'rom/a/0/1/5') as garc:  # SUMO
        for pokemonid, subfile in enumerate(garc):
            mega_evos = pokemon_mega_evolutions_struct.parse_stream(subfile[0])
            mega_counts[pokemonid] = max(
                mega_evo.number for mega_evo in mega_evos)

    return mega_counts


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
            #raise ValueError("Pokemon {} doesn't have forms".format(pokemonid))
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


def write_clim_to_png(f, width, height, color_depth, palette, pixels):
    """Write the results of ``decode_clim`` to a file object."""
    writer_kwargs = dict(width=width, height=height)
    if palette:
        writer_kwargs['palette'] = palette
    else:
        # TODO do i really only need alpha=True if there's no palette?
        writer_kwargs['alpha'] = True
    writer = png.Writer(**writer_kwargs)

    # For a paletted image, I want to preserve Zhorken's good idea of
    # indicating the original bit depth with an sBIT chunk.  But PyPNG can't do
    # that directly, so instead I have to do some nonsense.
    if palette:
        buf = io.BytesIO()
        writer.write(buf, pixels)

        # Read the PNG as chunks, and manually add an sBIT chunk
        buf.seek(0)
        png_reader = png.Reader(buf)
        chunks = list(png_reader.chunks())
        sbit = bytes([color_depth] * 3)
        chunks.insert(1, ('sBIT', sbit))

        # Now write the chunks to the file
        png.write_chunks(f, chunks)

    else:
        # Otherwise, it's...  almost straightforward.
        writer.write(f, (itertools.chain(*row) for row in pixels))


def extract_box_sprites(root, out):
    namer = SpriteFileNamer(
        out, get_mega_counts(root), ORAS_EXTRA_SPRITE_NAMES)

    with (root / 'exe/code.bin').open('rb') as f:
        # Form configuration, used to put sprites in the right order
        # NOTE: in x/y the address is 0x0043ea98
        #f.seek(0x0047d650)  # ORAS
        f.seek(0x004999d0)  # SUMO
        # TODO magic number
        for n in range(722):
            sprite = pokemon_sprite_struct.parse_stream(f)
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
            if i == 0:
                # Dummy blank sprite, not interesting to us
                continue
            elif i == 333:
                # Duplicate Entei sprite that's not used
                continue
            elif i == len(garc) - 1:
                # Very last one is egg
                namer.inject(i, 'egg.png')

            data = subfile[0].read()
            width, height, color_depth, palette, pixels = decode_clim(data)

            # TODO this is bad.
            if 'right/' in namer.index_to_filenames[i][0]:
                for row in pixels:
                    row.reverse()

            with namer.open(i) as f:
                write_clim_to_png(f, width, height, color_depth, palette, pixels)


def extract_dex_sprites(root, out):
    # Some Pokémon have dex sprites for their forms, too, and they're all
    # clustered together, so we have to do a little work to fix the numbering.
    # Luckily the dex sprites are in the same order as the models
    # (unsurprising, as they're just model renders), which also tells us what
    # Pokémon have female forms.  The mega evolution map tells us which forms
    # are megas, and the rest are listed manually above as
    # ORAS_EXTRA_SPRITE_NAMES.

    namer = SpriteFileNamer(
        out, get_mega_counts(root), ORAS_EXTRA_SPRITE_NAMES)

    # TODO Meowstic is counted as simply female in here, but should probably be
    # saved with a form filename as well
    #with read_garc(root / 'rom/a/0/0/8') as garc:  # ORAS
    with read_garc(root / 'rom/a/0/9/4') as garc:  # SUMO
        f = garc[0][0]
        # TODO magic number
        for n in range(721):
            # Unlike /virtually everywhere else/, Pokémon are zero-indexed here
            pokemonid = n + 1
            # Index of the first model (also zero-indexed), how many models the
            # Pokémon has, and some flags
            start, count, flags = struct.unpack('<HBB', f.read(4))
            model_num = start + 1
            # For some asinine reason, Xerneas is counted as two separate
            # Pokémon in the dex sprites but not the models, so we have to
            # shift everything after it back by 1
            if pokemonid == 716:
                count = 2
            elif pokemonid >= 717:
                model_num += 1

            namer.add(model_num, pokemonid)
            form_count = count - 1  # discount "base" form
            total_model_count = model_num + count - 1

            # Don't know what flag 1 is; everything has it.
            # Flag 2 means the first alternate form is a female variant.
            if flags & 2:
                assert form_count > 0
                form_count -= 1
                model_num += 1
                namer.add(model_num, pokemonid, female=True)
            # Flag 4 just means there are more forms?
            if flags & 4:
                assert form_count

            for formid in range(1, form_count + 1):
                model_num += 1
                namer.add(model_num, pokemonid, formid)

    # And now, do the ripping
    #with read_garc(root / 'rom/a/2/6/3') as garc:  # ORAS
    with read_garc(root / 'rom/a/2/4/0') as garc:  # sun/moon demo
        from .lib.clim import decode_clim
        from .lib.etc1 import decode_etc1
        for i, subfile in enumerate(garc):
            shiny_prefix = None
            if i > total_model_count:
                i -= total_model_count
                # TODO this should be a real feature, as should the 'right'
                # hack in the other code
                shiny_prefix = 'shiny/'

            if i == 0:
                # Dummy blank sprite, not interesting to us
                continue
            elif 37 <= i <= 41:
                # Cosplay Pikachu's outfits -- the sprites are blank, so saving
                # these is not particularly useful
                continue

            data = subfile[0].read()
            with namer.open(i, prefix=shiny_prefix) as f:
                write_clim_to_png(f, *decode_etc1(data))
                #write_clim_to_png(f, *decode_clim(data))


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
