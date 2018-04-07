#!/usr/bin/env python2
"""
This is an unmaintained one-shot script, only included in the repo for
reference.
"""

from pokedex.db import connect, identifier_from_name
from pokedex.db.tables import Encounter, EncounterSlot, LocationArea
from pokedex.db.tables import EncounterMethod, Location, Pokemon, Version

session = connect()

def get_version(name):
    return session.query(Version).filter_by(identifier=identifier_from_name(name)).one()

def gift_data():
    R = get_version(u'red')
    B = get_version(u'blue')
    Y = get_version(u'yellow')
    return [
        # Gen I
        [ u'bulbasaur',   [ R, B ],  5, u'pallet-town' ],
        [ u'charmander',  [ R, B ],  5, u'pallet-town' ],
        [ u'squirtle',    [ R, B ],  5, u'pallet-town' ],
        [ u'pikachu',     [ Y    ],  5, u'pallet-town' ],
        [ u'bulbasaur',   [ Y    ], 10, u'cerulean-city'  ],
        [ u'charmander',  [ Y    ], 10, u'kanto-route-24' ],
        [ u'squirtle',    [ Y    ], 10, u'vermilion-city' ],

        [ u'aerodactyl', [ R, B, Y ], 30, u'pewter-city',   u'museum-of-science' ],
        [ u'magikarp',   [ R, B, Y ],  5, u'kanto-route-4', u'pokemon-center' ],
        [ u'omanyte',    [ R, B, Y ], 30, u'mt-moon',       u'b2f' ],
        [ u'kabuto',     [ R, B, Y ], 30, u'mt-moon',       u'b2f' ],
        [ u'hitmonlee',  [ R, B, Y ], 30, u'saffron-city',  u'fighting-dojo' ],
        [ u'hitmonchan', [ R, B, Y ], 30, u'saffron-city',  u'fighting-dojo' ],
        [ u'eevee',      [ R, B, Y ], 25, u'celadon-city',  u'celadon-mansion' ],
        [ u'lapras',     [ R, B, Y ], 15, u'saffron-city',  u'silph-co-7f' ],
    ]


gift_method = session.query(EncounterMethod).filter_by(identifier=u'gift').one()

for gift_data in gift_data():
    pokemon_name  = identifier_from_name(gift_data[0])
    versions      = gift_data[1]
    level         = identifier_from_name(str(gift_data[2]))
    location_name = identifier_from_name(gift_data[3])
    area_name       = None
    if len(gift_data) > 4:
        area_name     = identifier_from_name(gift_data[4])


    pokemon       = session.query(Pokemon     ).filter_by(identifier=pokemon_name                      ).one()
    location      = session.query(Location    ).filter_by(identifier=location_name                     ).one()
    location_area = session.query(LocationArea).filter_by(identifier=area_name, location_id=location.id).first()
    # Some of these don't exist yet
    if not location_area:
        location_area = LocationArea(
            location_id = location.id,
            game_index  = 0, # cause who knows what this means
            identifier  = area_name
        )
        session.add(location_area)
        session.commit()

    for version in versions:
        encounter_slot = session.query(EncounterSlot).filter_by(
            version_group_id    = version.version_group_id,
            encounter_method_id = gift_method.id
        ).first()

        if not encounter_slot:
            encounter_slot = EncounterSlot(
                version_group_id = version.version_group_id,
                encounter_method_id = gift_method.id,
                # No priority over or under other events/conditions
                slot                = None,
                # Rarity is meaningless for gifts
                rarity              = None,
            )
            session.add(encounter_slot)
            session.commit()

        encounter_info = {
            'version_id':        version.id,
            'location_area_id':  location_area.id,
            'encounter_slot_id': encounter_slot.id,
            'pokemon_id':        pokemon.id,
            'min_level':         level,
            'max_level':         level
        }
        encounter = session.query(Encounter).filter_by(**encounter_info).first()
        if not encounter:
            encounter = Encounter(**encounter_info)
            session.add(encounter)

    session.commit()
