#!/usr/bin/env python2
# encoding: utf-8
# Adds locations to the database from the text dump.
#
# Usage: python add-oras-locations.py | psql pokedex

import os
import re
import io

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

    if identifier == '???':
        identifier = 'inside-of-truck'

    if not identifier.replace(u"-", u"").isalnum():
        raise ValueError(identifier)
    return identifier

ROOT = os.path.expanduser("~/xy/orips/text")

en = io.open(os.path.join(ROOT, 'en/90'), encoding='utf-8')

lang_idents = {
    'ja-kana': 'ja-Hrkt',
    'ja-kanji': 'ja',
}

foreign = []
for lang in 'ja-kana', 'ja-kanji', 'en', 'fr', 'it', 'de', 'es', 'ko':
    f = io.open(os.path.join(ROOT, lang, '90'), encoding='utf-8')
    foreign.append((lang_idents.get(lang, lang), f))

REGION_ID = 3
GENERATION_ID = 6
START_LINE = 170 # locations before this line were from X/Y

import pokedex.db
import pokedex.db.tables as t
session = pokedex.db.connect("postgresql:///pokedex")
existing_location_ids = set(x for x, in session.query(t.Location.identifier).all())
#print(existing_location_ids)

print("BEGIN;")
print("SELECT setval('locations_id_seq', max(id)) FROM locations;")
for i, name in enumerate(en):
    foreign_names = [(lang, next(iter).strip()) for lang, iter in foreign]
    if i == 0:
        continue
    if i < START_LINE:
        continue
    if name == '\n':
        continue
    try:
        ident = make_identifier(name.strip())
    except ValueError:
        continue
    if ident == 'safari-zone':
        ident = 'hoenn-safari-zone'
    elif ident == 'victory-road':
        ident = 'hoenn-victory-road'
    elif ident == 'pokemon-league':
        ident = 'hoenn-pokemon-league'
    elif ident.startswith("route-"):
        ident = 'hoenn-' + ident

    print("\echo '%s'" % ident)
    if ident in ('mystery-zone', 'faraway-place'):
        ## standard locations
        pass
    elif ident in existing_location_ids:
        ## location already exists from R/S,
        ## so keep the existing location and just replace the names

        print("""DELETE FROM location_names WHERE location_id = (SELECT id FROM locations where identifier = '%s');""" % ident)
    else:
        ## new location
        print("""INSERT INTO locations (identifier, region_id) VALUES ('%s', %s) RETURNING id;""" % (ident, REGION_ID))

    for lang, name in foreign_names:
        print("""INSERT INTO location_names (location_id, local_language_id, name) SELECT loc.id, lang.id, '%s' FROM locations loc, languages lang WHERE loc.identifier = '%s' AND (loc.region_id is NULL OR loc.region_id = %d) AND lang.identifier = '%s';""" % (name.encode("utf-8"), ident.encode("utf-8"), REGION_ID, lang))

    print("""INSERT INTO location_game_indices (location_id, generation_id, game_index) SELECT id, %s, %s FROM locations WHERE identifier='%s' AND (region_id is NULL OR region_id = %d) ON CONFLICT DO NOTHING;""" % (GENERATION_ID, i, ident.encode("utf-8"), REGION_ID))

#for pokemon_id, location_identifier in (462, 'kalos-route-13'), (470, 'kalos-route-20'), (471, 'frost-cavern'), (476, 'kalos-route-13'):
#    print("UPDATE pokemon_evolution SET location_id = (SELECT id FROM locations WHERE identifier = '%s') WHERE location_id is NULL AND evolved_species_id = %d;" % (location_identifier, pokemon_id))

print("COMMIT;")
