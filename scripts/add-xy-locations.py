# Adds locations to the database from the text dump.
#
# Usage: python add-xy-locations.py | psql pokedex

import re

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

    if identifier.startswith('route-'):
        identifier = 'kalos-' + identifier

    if not identifier.replace(u"-", u"").isalnum():
        raise ValueError(identifier)
    return identifier

en = open('rips/text/en/72')

foreign = []
foreign.append(('ja', open('rips/text/ja-kana/72')))
for lang in 'ja-kanji', 'en', 'fr', 'it', 'de', 'es', 'ko':
    f = open('rips/text/'+lang+'/72')
    foreign.append((lang, f))

print("BEGIN;")
print("UPDATE pokemon_evolution SET location_id = NULL WHERE location_id in (SELECT id FROM locations WHERE region_id = 6);")
print("DELETE FROM location_game_indices WHERE generation_id = 6;")
print("DELETE FROM location_names WHERE location_id IN (SELECT id FROM locations WHERE region_id = 6);")
print("DELETE FROM locations WHERE region_id=6;")
print("SELECT setval('locations_id_seq', max(id)) FROM locations;")
for i, name in enumerate(en):
    foreign_names = [(lang, next(iter).strip()) for lang, iter in foreign]
    if i == 0:
        continue
    if name == '\n':
        continue
    try:
        ident = make_identifier(name.strip())
    except ValueError:
        continue

    print("\echo '%s'" % ident)
    if ident not in ('mystery-zone', 'faraway-place'):
        print("""INSERT INTO locations (identifier, region_id) VALUES ('%s', %s) RETURNING id;""" % (ident, 6))
        for lang, name in foreign_names:
            print("""INSERT INTO location_names (location_id, local_language_id, name) SELECT loc.id, lang.id, '%s' FROM locations loc, languages lang WHERE loc.identifier = '%s' AND (loc.region_id is NULL OR loc.region_id = 6) AND lang.identifier = '%s';""" % (name, ident, lang))
    print("""INSERT INTO location_game_indices (location_id, generation_id, game_index) SELECT id, %s, %s FROM locations WHERE identifier='%s' AND (region_id is NULL OR region_id = 6);""" % (6, i, ident))

for pokemon_id, location_identifier in (462, 'kalos-route-13'), (470, 'kalos-route-20'), (471, 'frost-cavern'), (476, 'kalos-route-13'):
    print("UPDATE pokemon_evolution SET location_id = (SELECT id FROM locations WHERE identifier = '%s') WHERE location_id is NULL AND evolved_species_id = %d;" % (location_identifier, pokemon_id))

print("COMMIT;")
