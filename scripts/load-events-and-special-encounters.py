# Encoding: UTF-8
"""Load events and special encounters from a CSV file

This is an unmaintained one-shot script, only included in the repo for reference.

Loads the data from an ad-hoc spreadsheet format, because for getting this stuff
together, flat is definitely better than nested.

"""

from __future__ import unicode_literals

import sys
import csv

from sqlalchemy.sql.expression import func
from sqlalchemy.orm import subqueryload
import sqlalchemy.orm.exc

from pokedex.db import connect, tables, util, load

session = connect()

reader = ([c.decode('utf-8') for c in l] for l in csv.reader(open(sys.argv[1])))
reader.next()  # discard line 1
column_names = reader.next()
print ','.join(column_names)

english = util.get(session, tables.Language, 'en')

def create_with_autoid(table):
    autoid = (session.query(func.max(table.id)).one()[0] or 0) + 1
    obj = table()
    obj.id = autoid
    return obj

# We need location_areas for places that don't have them yet
for location in session.query(tables.Location).options(subqueryload('areas')):
    if not location.areas:
        print 'Creating default area for', location.identifier
        area = create_with_autoid(tables.LocationArea)
        area.location = location
        session.add(area)

def trainer(name, number):
    if name is number is None:
        return None
    query = session.query(tables.Trainer).join(tables.Trainer.names)
    query = query.filter(tables.Trainer.names_table.name == name)
    query = query.filter(tables.Trainer.number == number)
    try:
        return query.one()
    except sqlalchemy.orm.exc.NoResultFound:
        trainer = create_with_autoid(tables.Trainer)
        trainer_name = tables.Trainer.names_table()
        trainer_name.local_language = english
        trainer_name.foreign_id = trainer.id
        trainer_name.name = name
        trainer.number = number
        session.add(trainer)
        session.add(trainer_name)
        return trainer

version_codes = (
        # 2-letter codes first!
        ('Xd', 'xd'),
        ('Co', 'colosseum'),
        ('Pt', 'platinum'),
        ('Hg', 'heartgold'),
        ('Ss', 'soulsilver'),

        ('R', 'red'),
        ('B', 'blue'),
        ('Y', 'yellow'),

        ('G', 'gold'),
        ('S', 'silver'),
        ('C', 'crystal'),

        ('R', 'ruby'),
        ('S', 'sapphire'),
        ('E', 'emerald'),
        ('F', 'firered'),
        ('L', 'leafgreen'),

        ('D', 'diamond'),
        ('P', 'pearl'),

        ('B', 'black'),
        ('W', 'white'),
    )

for line in reader:
    print ','.join(line)
    line_dict = dict(zip(column_names, line + [''] * 100))
    all_places = line_dict.pop('Place').split(',')
    for p_form_ident in line_dict.pop('Species/Form').split(','):
        p_form_ident = p_form_ident.strip()
        for place_ident in all_places:
            place_ident = place_ident.strip()

            dct = dict(line_dict)

            encounter_type = util.get(session, tables.SpecialEncounterType, dct.pop('Method'))
            species_ident, sp, form_ident = p_form_ident.partition(' ')
            species = util.get(session, tables.PokemonSpecies, species_ident)
            for pokemon_form in species.forms:
                if pokemon_form.form_identifier == (form_ident or None):
                    break
            else:
                raise ValueError('No such pkmn form: %s' % p_form_ident)
            if place_ident:
                location_ident, sp, area_ident = place_ident.partition(' ')
                location = util.get(session, tables.Location, location_ident)
                for location_area in location.areas:
                    if location_area.identifier == (area_ident or None):
                        break
                else:
                    raise ValueError('No such area: %s' % place_ident)
            else:
                location_area = None
            se_pokemon = create_with_autoid(tables.EventPokemon)
            se_pokemon.pokemon_form = pokemon_form
            se_pokemon.is_egg = bool(dct.pop('Egg'))
            se_pokemon.cost = dct.pop('Cost') or None
            session.add(se_pokemon)
            encounter = create_with_autoid(tables.SpecialEncounter)
            encounter.event_pokemon = se_pokemon
            encounter.type = encounter_type
            encounter.location_area = location_area
            se_pokemon.level = dct.pop('Lv.') or None
            se_pokemon.nickname = dct.pop('Name') or None
            session.add(encounter)
            if encounter_type == 'starter':
                print
            dct.pop('Notes')
            versions = dct.pop('Version')
            trade_for = dct.pop('Trade for')
            if trade_for:
                encounter.trade_species = util.get(session,
                        tables.PokemonSpecies, trade_for)
            se_pokemon.original_trainer = trainer(
                    dct.pop('OT Name') or None, dct.pop('OT №') or None)
            for code, version_ident in version_codes:
                part1, current_code, part2 = versions.partition(code)
                versions = part1 + part2
                if current_code:
                    entry = tables.SpecialEncounterVersion()
                    entry.encounter = encounter
                    entry.version = util.get(session, tables.Version, version_ident)
                    session.add(entry)
            assert not versions, 'Leftover versions: %s' % versions
            assert not any(dct.values()), 'stuff left over: %s' % ', '.join(
                    '%s=%s' % (k, v) for k, v in dct.items() if v)

print 'Dumping!'
load.dump(session, verbose=True, tables=[
        'special_encounters',
        'event_pokemon',
        'special_encounter_versions',
        'location_areas',
        'trainers',
        'trainer_names',
    ])

session.rollback()
