# encoding: utf-8
# Adds locations to the database from the text dump.
#
# Usage: python add-sm-locations.py | psql pokedex

from __future__ import unicode_literals, print_function

import io
import os
import re
import sys

def make_identifier(name):
    """Make a string safe to use as an identifier.

    Valid characters are lowercase alphanumerics and "-". This function may
    raise ValueError if it can't come up with a suitable identifier.

    This function is useful for scripts which add things with names.
    """
    if isinstance(name, bytes):
        identifier = name.decode('utf-8')
    else:
        identifier = name
    identifier = identifier.lower()
    identifier = identifier.replace(u'+', u' plus ')
    identifier = re.sub(u'[ _–]+', u'-', identifier)
    identifier = re.sub(u"['./;’(),:]", u'', identifier)
    identifier = identifier.replace(u'é', u'e')

    if not identifier.replace(u"-", u"").isalnum():
        raise ValueError(identifier)
    return identifier

ROOT = os.path.expanduser("~/hacks/sm-encounters/textrip/text")
GENERATION_ID = 7
REGION_ID = 7

lang_idents = {
    'ja-kana': 'ja-Hrkt',
    'ja-kanji': 'ja',
}

foreign = []
for lang in 'ja-kana', 'ja-kanji', 'en', 'fr', 'it', 'de', 'es', 'ko', 'zh-Hans', 'zh-Hant':
    with io.open(os.path.join(ROOT, lang, '67'), encoding="utf-8") as f:
        names = []
        while True:
            name = f.readline()
            subtitle = f.readline()
            if not name:
                break
            names.append((name.strip(), subtitle.strip()))
    foreign.append((lang_idents.get(lang, lang), names))

print("BEGIN;")
#print("UPDATE pokemon_evolution SET location_id = NULL WHERE location_id in (SELECT id FROM locations WHERE region_id = 6);")
print("DELETE FROM location_game_indices WHERE generation_id = %d;" % GENERATION_ID)
print("DELETE FROM location_names WHERE location_id IN (SELECT id FROM locations WHERE region_id = %d);" % REGION_ID)
print("DELETE FROM locations WHERE region_id=%d;" % REGION_ID)
print("SELECT setval('locations_id_seq', max(id)) FROM locations;")
en = foreign[2][1]
for i, (name, subtitle) in enumerate(en):
    game_index = i * 2
    foreign_names = [(lang, names[i]) for lang, names in foreign]
    if i == 0:
        continue
    if name == '\n':
        continue
    try:
        ident = make_identifier(name.strip())
    except ValueError:
        print(("bad location: %s" % name).encode("utf-8"), file=sys.stderr)
        continue

    if ident.startswith('route-'):
        ident = 'alola-' + ident
    elif ident == 'pokemon-league':
        ident = 'alola-pokemon-league'

    if subtitle:
        try:
            subident = make_identifier(subtitle.strip())
        except ValueError:
            print(("bad location: %s %s" % (name, subtitle)).encode("utf-8"), file=sys.stderr)
            continue
        ident = ident + "--" + subident

    print("\echo '%s'" % ident)
    if ident in ('mystery-zone', 'faraway-place'):
        # standard locations
        pass
    elif ident == 'hano-grand-resort' and game_index == 102:
        # I have no idea why where are two "Hano Grand Resort" locations.
        # I think this one is unused
        pass
    else:
        print("""INSERT INTO locations (identifier, region_id) VALUES ('%s', %s) RETURNING id;""" % (ident, REGION_ID))

        for lang, (name, subtitle) in foreign_names:
            print(("""INSERT INTO location_names (location_id, local_language_id, name, subtitle) SELECT loc.id, lang.id, '%s', '%s' FROM locations loc, languages lang WHERE loc.identifier = '%s' AND (loc.region_id is NULL OR loc.region_id = %d) AND lang.identifier = '%s';""" % (name, subtitle, ident, REGION_ID, lang)).encode("utf-8"))

    print(("""INSERT INTO location_game_indices (location_id, generation_id, game_index) SELECT id, %s, %s FROM locations WHERE identifier='%s' AND (region_id is NULL OR region_id = %d);""" % (GENERATION_ID, game_index, ident, REGION_ID)).encode("utf-8"))

#for pokemon_id, location_identifier in (462, 'kalos-route-13'), (470, 'kalos-route-20'), (471, 'frost-cavern'), (476, 'kalos-route-13'):
#    print("UPDATE pokemon_evolution SET location_id = (SELECT id FROM locations WHERE identifier = '%s') WHERE location_id is NULL AND evolved_species_id = %d;" % (location_identifier, pokemon_id))

print("COMMIT;")
