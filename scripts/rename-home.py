#!/usr/bin/env python3
#
# this is an unmaintained one-shot script, provided for reference only
# it may not work or do what you expected
#

# Usage: rename-home.py src -o dest
# Renames sprites from src dir to dest dir.
# files in src dir should be named as in the HOME unity3d assets.
# files in dest dir will be named according to veekun conventions.

form_names = {
        25: ["", "original-cap", "hoenn-cap", "sinnoh-cap", "unova-cap", "kalos-cap", "alola-cap", "partner-cap", "partner"],
        133: ["", "partner"],
        201: ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
                "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
                "exclamation", "question"],
        351: ["", "sunny", "rainy", "snowy"],
        382: ["", "primal"],
        383: ["", "primal"],
        386: ["normal", "attack", "defense", "speed"],
        412: ["plant", "sandy", "trash"],
        413: ["plant", "sandy", "trash"],
        421: ["overcast", "sunshine"],
        422: ["west", "east"],
        423: ["west", "east"],
        479: ["", "heat", "wash", "frost", "fan", "mow"],
        487: ["altered", "origin"],
        492: ["land", "sky"],
        493: ["normal", "fighting", "flying", "poison", "ground",
                "rock", "bug", "ghost", "steel", "fire", "water", "grass",
                "electric", "psychic", "ice", "dragon", "dark", "fairy"],
        550: ["red-striped", "blue-striped"],
        555: ["standard", "zen", "standard-galar", "zen-galar"],
        585: ["spring", "summer", "autumn", "winter"],
        586: ["spring", "summer", "autumn", "winter"],
        592: ["male", "female"],
        593: ["male", "female"],
        641: ["incarnate", "therian"],
        642: ["incarnate", "therian"],
        645: ["incarnate", "therian"],
        646: ["", "white", "black"],
        647: ["ordinary", "resolute"],
        648: ["aria", "pirouette"],
        649: ["", "douse", "shock", "burn", "chill"],
        658: ["", "battle-bond", "ash"],
        666: ["icy-snow", "polar", "tundra", "continental", "garden",
                "elegant", "meadow", "modern", "marine", "archipelago",
                "high-plains", "sandstorm", "river", "monsoon", "savanna",
                "sun", "ocean", "jungle", "fancy", "poke-ball"],
        669: ["red", "yellow", "orange", "blue", "white"],
        670: ["red", "yellow", "orange", "blue", "white", "eternal"],
        671: ["red", "yellow", "orange", "blue", "white"],
        676: ["", "heart", "star", "diamond", "debutante",
                "matron", "dandy", "la-reine", "kabuki", "pharaoh"],
        678: ["male", "female"],
        681: ["shield", "blade"],
        710: ["average", "small", "large", "super"],
        711: ["average", "small", "large", "super"],
        716: ["neutral", "active"],
        718: ["", '10', '10-power-construct', '50-power-construct', 'complete'],
        720: ["", "unbound"],
        741: ('baile', 'pom-pom', 'pau', 'sensu'),
        744: ('', 'own-tempo'),
        745: ('midday', 'midnight', 'dusk'),
        746: ('solo', 'school'),
        773: ('normal', 'fighting', 'flying', 'poison', 'ground', 'rock',
              'bug', 'ghost', 'steel', 'fire', 'water', 'grass', 'electric',
              'psychic', 'ice', 'dragon', 'dark', 'fairy',),
        774: ('red-meteor', 'orange-meteor', 'yellow-meteor', 'green-meteor',
              'blue-meteor', 'indigo-meteor', 'violet-meteor', 'red', 'orange',
              'yellow', 'green', 'blue', 'indigo', 'violet',),
        778: ('disguised', 'busted', 'totem-disguised', 'totem-busted'),
        800: ["", "dusk", "dawn", "ultra"],
        801: ("", 'original'),
        845: ["", "gulping", "gorging"],
        849: ["amped", "low-key"],
        854: ["phony", "antique"],
        855: ["phony", "antique"],
        869: ["vanilla-cream", "ruby-cream", "matcha-cream", "mint-cream", "lemon-cream", "salted-cream", "ruby-swirl", "caramel-swirl", "rainbow-swirl"],
        875: ["ice", "noice"],
        876: ["male", "female"],
        877: ["full-belly", "hangry"],
        888: ["", "crowned-sword"],
        889: ["", "crowned-shield"],
        890: ["", "eternamax"],
        892: ["single-strike", "rapid-strike"],


        19: ["", "alola"],
        20: ["", "alola", "totem-alola"],
        26: ["", "alola"],
        27: ["", "alola"],
        28: ["", "alola"],
        37: ["", "alola"],
        38: ["", "alola"],
        50: ["", "alola"],
        51: ["", "alola"],
        52: ["", "alola", "galar"],
        53: ["", "alola"],
        74: ["", "alola"],
        75: ["", "alola"],
        76: ["", "alola"],
        88: ["", "alola"],
        89: ["", "alola"],
        103: ["", "alola"],
        105: ["", "alola", "totem"],
        735: ["", "totem"],
        738: ["", "totem"],
        743: ["", "totem"],
        752: ["", "totem"],
        754: ["", "totem"],
        758: ["", "totem"],
        777: ["", "totem"],
        784: ["", "totem"],


        77: ["", "galar"],
        78: ["", "galar"],
        79: ["", "galar"],
        80:  ["", "mega", "galar"],
        83: ["", "galar"],
        110: ["", "galar"],
        122: ["", "galar"],
        222: ["", "galar"],
        263: ["", "galar"],
        264: ["", "galar"],
        554: ["", "galar"],
        562: ["", "galar"],
        618: ["", "galar"],

        3:   ["", "mega"],
        6:   ["", "mega-x", "mega-y"],
        9:   ["", "mega"],
        15:  ["", "mega"],
        18:  ["", "mega"],
        65:  ["", "mega"],
        94:  ["", "mega"],
        115: ["", "mega"],
        127: ["", "mega"],
        130: ["", "mega"],
        142: ["", "mega"],
        150: ["", "mega-x", "mega-y"],
        181: ["", "mega"],
        208: ["", "mega"],
        212: ["", "mega"],
        214: ["", "mega"],
        229: ["", "mega"],
        248: ["", "mega"],
        254: ["", "mega"],
        257: ["", "mega"],
        260: ["", "mega"],
        282: ["", "mega"],
        302: ["", "mega"],
        303: ["", "mega"],
        306: ["", "mega"],
        308: ["", "mega"],
        310: ["", "mega"],
        319: ["", "mega"],
        323: ["", "mega"],
        334: ["", "mega"],
        354: ["", "mega"],
        359: ["", "mega"],
        362: ["", "mega"],
        373: ["", "mega"],
        376: ["", "mega"],
        380: ["", "mega"],
        381: ["", "mega"],
        384: ["", "mega"],
        428: ["", "mega"],
        475: ["", "mega"],
        445: ["", "mega"],
        448: ["", "mega"],
        460: ["", "mega"],
        531: ["", "mega"],
        719: ["", "mega"],
}

sweets = ["strawberry", "berry", "love", "star", "clover", "flower", "ribbon"]

import os
import sys
import re
import argparse
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('-o', dest='dest')
args = parser.parse_args()

fn_re = re.compile("cap(?P<n>[0-9]{4})_f(?P<form>..)_s(?P<sex>.)(?:_128)?(?P<shiny>_r)?(?P<back>_b)?(?:_(?P<extra>[0-9]))?\.")
seen = set()
for file in sorted(os.listdir(args.src)):
    m = fn_re.match(file)
    if m is None:
        print("WARNING: unmatched file", file, file=sys.stderr)
        continue
    n = int(m.group('n'))
    form = int(m.group('form'))

    if n in (414, 664, 665) and form > 0:
        # 414 mothim - three identical forms
        # 664 scatterbug - identical forms
        # 665 spewpa - identical forms
        continue

    # 892 urshifu - form 81 = gigantamax single strike, form 82 = gigantamax rapid strike
    if n == 892:
        if form == 81:
            form_name = 'gigantamax-single-strike'
        elif form == 82:
            form_name = 'gigantamax-rapid-strike'
        else:
            form_name = form_names[n][form]

    # form 81 = gigantamax
    elif form == 81:
        form_name = 'gigantamax'

    else:
        try:
            form_name = form_names[n][form]
        except (KeyError, IndexError):
            form_name = ""

    if form > 0 and not form_name:
        print("WARNING: no form name for", file, file=sys.stderr)
        print("INFO:", m.group('n'), m.group('form'), m.group('sex'), m.group('back') or 'front', m.group('shiny') or 'normal', m.group('extra')or'', file=sys.stderr)
        continue

    dirs = []
    if m.group('back'):
        dirs += ['back']
    if m.group('shiny'):
        dirs += ['shiny']
    if m.group('sex') == '1':
        dirs += ['female']

    # 869 alcremie: its form determines the type of cream, and extra determines the sweet
    if n == 869:
        if form == 81:
            # gigantamax
            pass
        elif m.group('shiny'):
            # shiny alcremie uses the same sprites for all flavors
            form_name = sweets[int(m.group('extra'))]
        else:
            form_name = sweets[int(m.group('extra'))] + "-" + form_name
    else:
        if m.group('extra'):
            print("WARNING: unhandled extra on", file, file=sys.stderr)


    if form_name:
        new_name = "{}-{}.png".format(n, form_name)
    elif n == 0:
        new_name = "egg.png"
    else:
        new_name = "{}.png".format(n)
    if dirs:
        new_name = '/'.join(dirs) + '/' + new_name
    if new_name in seen:
        print("WARNING: duplicate file", new_name, file=sys.stderr)
    seen.add(new_name)

    if args.dest:
        if dirs:
            os.makedirs('/'.join([args.dest] + dirs), exist_ok=True)
        destfile = os.path.join(args.dest, new_name)
        if os.path.exists(destfile):
            print("ERROR: refusing to overwrite", destfile, file=sys.stderr)
            sys.exit(1)
        else:
            shutil.copyfile(os.path.join(args.src, file), destfile)
    else:
        print("cp", file.ljust(25), new_name)


