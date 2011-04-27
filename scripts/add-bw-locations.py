#!/usr/bin/env python2
"""
This is an unmaintained one-shot script, only included in the repo for
reference.
"""

from codecs import open

from pokedex.db import connect, identifier_from_name
from pokedex.db.tables import Language
from pokedex.db.tables import Location, LocationGameIndex

session = connect()

en = session.query(Language).filter_by(identifier='en').one() # English
ja = session.query(Language).filter_by(identifier='ja').one() # Japanese

with open("bw-location-names-en", "r", "utf-8") as f:
    en_names = [line.rstrip("\n") for line in f]
with open("bw-location-names-kanji", "r", "utf-8") as f:
    ja_names = [line.rstrip("\n") for line in f]

locations = {}
for i, name in enumerate(zip(en_names, ja_names)):
    if i == 0:
        continue

    en_name, ja_name = name
    if not en_name:
        continue

    if name in locations:
        loc = locations[name]
    else:
        loc = Location()
        if en_name:
            loc.name_map[en] = en_name
        if ja_name:
            loc.name_map[ja] = ja_name
        loc.region_id = 5 # Unova
        loc.identifier = identifier_from_name(en_name)

        locations[name] = loc

    lgi = LocationGameIndex()
    lgi.location = loc
    lgi.generation_id = 5 # Gen 5
    lgi.game_index = i

    session.add(loc)
    session.add(lgi)

session.commit()
