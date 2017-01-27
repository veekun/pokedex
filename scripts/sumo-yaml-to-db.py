import itertools
from pathlib import Path

from camel import Camel
from sqlalchemy.orm import Load

import pokedex.db
import pokedex.db.tables as t
import pokedex.main as main
import pokedex.schema as schema


out = Path('moon-out')
session = pokedex.db.connect('postgresql:///veekun_pokedex')
camel = Camel([schema.POKEDEX_TYPES])

# While many tables do have a primary key with a sequence, those sequences are
# all initialized to 1 because the data was loaded manually instead of using
# nextval().  That's a pain in the ass for us, so this fixes them up.
for table_name, table in pokedex.db.metadata.tables.items():
    if hasattr(table.c, 'id') and table.c.id.autoincrement:
        session.execute("""
            SELECT setval(pg_get_serial_sequence('{table_name}', 'id'),
                coalesce(max(id), 0) + 1, false)
            FROM {table_name} WHERE id < 10000;
            """.format(table_name=table_name))

db_languages = {}
for language in session.query(t.Language).all():
    db_languages[language.identifier] = language
session.local_language_id = db_languages['en'].id

# Insert some requisite new stuff if it doesn't already exist
db_sumo_generation = session.query(t.Generation).get(7)
if db_sumo_generation:
    db_sumo_version_group = session.query()
else:
    # Distinguish simplified and traditional Chinese
    db_languages['zh'].identifier = 'zh-Hant'
    for db_language in db_languages.values():
        if db_language.order > db_languages['zh'].order:
            db_language.order += 1
    session.add(t.Language(
        id=12,
        iso639='zh', iso3166='cn', identifier='zh-Hans', official=True,
        order=db_languages['zh'].order + 1,
    ))

    # Use standard names for Japanese
    db_languages['ja'].identifier = 'ja-Hrkt'
    db_languages['ja-kanji'].identifier = 'ja'
    session.flush()

    # Refresh language list
    db_languages = {}
    for language in session.query(t.Language).all():
        db_languages[language.identifier] = language
    db_en = db_languages['en']

    # Versions
    # TODO these all need names in other languages too
    db_alola = t.Region(identifier='alola')
    db_alola.name_map[db_en] = 'Alola'
    session.add(db_alola)
    db_sumo_generation = t.Generation(
        id=7, identifier='sun-moon',
        main_region=db_alola,
    )
    db_sumo_version_group = t.VersionGroup(
        identifier='sun-moon',
        generation=db_sumo_generation,
        order=17,
    )
    db_sun = t.Version(
        identifier='sun',
        version_group=db_sumo_version_group,
    )
    db_moon = t.Version(
        identifier='moon',
        version_group=db_sumo_version_group,
    )
    # TODO find names in other languages
    db_sun.name_map[db_en] = 'Sun'
    db_moon.name_map[db_en] = 'Moon'
    session.add_all([
        db_alola, db_sumo_generation,
        db_sumo_version_group, db_sun, db_moon,
    ])
    session.flush()


# Abilities
print()
print("--- ABILITIES ---")
with (out / 'abilities.yaml').open(encoding='utf8') as f:
    abilities = camel.load(f.read())

for (sumo_identifier, sumo_ability), db_ability in itertools.zip_longest(
    abilities.items(),
    session.query(t.Ability)
        .filter_by(is_main_series=True)
        .order_by(t.Ability.id)
        .options(Load(t.Ability).joinedload('names'))
        .all()
):
    print(sumo_identifier)
    if db_ability:
        assert sumo_identifier == db_ability.identifier
        # Update names and insert new ones
        for lang, name in sumo_ability.name.items():
            old_name = db_ability.name_map.get(db_languages[lang])
            if old_name != name:
                if old_name:
                    print("- hmm! changing", old_name, "to", name, "in", lang)
                db_ability.name_map[db_languages[lang]] = name
    else:
        db_ability = t.Ability(
            identifier=sumo_identifier,
            generation_id=7,
            is_main_series=True,
        )
        for lang, name in sumo_ability.name.items():
            db_ability.name_map[db_languages[lang]] = name
        session.add(db_ability)

    # Flavor text is per-version (group) and thus always new
    for lang, flavor_text in sumo_ability.flavor_text.items():
        session.add(t.AbilityFlavorText(
            ability=db_ability,
            version_group=db_sumo_version_group,
            language=db_languages[lang],
            flavor_text=flavor_text,
        ))

session.commit()
print()
print("done")
