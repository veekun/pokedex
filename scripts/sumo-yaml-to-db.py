import itertools
from pathlib import Path

from camel import Camel
from sqlalchemy import inspect
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

db_types = {row.identifier: row for row in session.query(t.Type)}
db_targets = {row.identifier: row for row in session.query(t.MoveTarget)}
db_damage_classes = {row.identifier: row for row in session.query(t.MoveDamageClass)}
db_move_categories = {row.identifier: row for row in session.query(t.MoveMetaCategory)}
db_move_ailments = {row.identifier: row for row in session.query(t.MoveMetaAilment)}
db_move_flags = {row.identifier: row for row in session.query(t.MoveFlag)}

# These are by id since move effects don't have identifiers atm
db_move_effects = {row.id: row for row in session.query(t.MoveEffect)}

# Insert some requisite new stuff if it doesn't already exist
db_sumo_generation = session.query(t.Generation).get(7)
if db_sumo_generation:
    db_sumo_version_group = session.query(t.VersionGroup).filter_by(identifier='sun-moon').one()
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


def cheap_upsert(db_obj, db_class, new_only, **data):
    if db_obj:
        if 'identifier' in new_only and new_only['identifier'] != db_obj.identifier:
            print(f"- identifier mismatch, yaml {new_only['identifier']!r} vs db {db_obj.identifier!r}")
        for key, new_value in data.items():
            old_value = getattr(db_obj, key)
            if old_value != new_value:
                print(f"- changing {key} from {old_value!r} to {new_value!r}")
                setattr(db_obj, key, new_value)
    else:
        db_obj = db_class(
            **new_only,
            **data,
        )
        session.add(db_obj)
    return db_obj


def update_names(sumo_obj, db_obj):
    """Update the database's names as necessary, and add any missing ones"""
    for lang, name in sumo_obj.name.items():
        old_name = db_obj.name_map.get(db_languages[lang])
        if old_name != name:
            if old_name:
                print(f"- NOTE: changing {old_name!r} to {name!r} in {lang}")
            db_obj.name_map[db_languages[lang]] = name


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
):
    print(sumo_identifier)
    if db_ability:
        assert sumo_identifier == db_ability.identifier
        update_names(sumo_ability, db_ability)
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
    # FIXME uhh no it isn't, not if i've alreayd run this script once lol
    """
    for lang, flavor_text in sumo_ability.flavor_text.items():
        session.add(t.AbilityFlavorText(
            ability=db_ability,
            version_group=db_sumo_version_group,
            language=db_languages[lang],
            flavor_text=flavor_text,
        ))
    """
session.flush()


print()
print("--- MOVES ---")
with (out / 'moves.yaml').open(encoding='utf8') as f:
    moves = camel.load(f.read())

for (sumo_identifier, sumo_move), db_move in itertools.zip_longest(
    moves.items(),
    session.query(t.Move)
        .filter(t.Move.id < 10000)
        .order_by(t.Move.id)
        .options(
            Load(t.Move).joinedload('names'),
            Load(t.Move).joinedload('meta'),
            Load(t.Move).subqueryload('flags'),
        )
):
    print(sumo_identifier)

    # Insert the move effect first, if necessary
    effect_id = sumo_move.effect + 1
    if effect_id not in db_move_effects:
        effect = t.MoveEffect(id=effect_id)
        effect.short_effect_map[db_languages['en']] = f"XXX new effect for {sumo_identifier}"
        effect.effect_map[db_languages['en']] = f"XXX new effect for {sumo_identifier}"
        session.add(effect)
        db_move_effects[effect_id] = effect

    db_move = cheap_upsert(
        db_move,
        t.Move,
        dict(identifier=sumo_identifier, generation_id=7),
        type=db_types[sumo_move.type.rpartition('.')[2]],
        power=None if sumo_move.power in (0, 1) else sumo_move.power,
        pp=sumo_move.pp,
        accuracy=None if sumo_move.accuracy == 101 else sumo_move.accuracy,
        priority=sumo_move.priority,
        target=db_targets[sumo_move.range.rpartition('.')[2]],
        damage_class=db_damage_classes[sumo_move.damage_class.rpartition('.')[2]],
        effect_id=effect_id,
        effect_chance=sumo_move.effect_chance,
    )
    # Check for any changed fields that can go in a changelog
    # TODO unfortunately, target is not in the changelog
    state = inspect(db_move)
    if state.persistent:
        loggable_changes = {}
        for field in ('type_id', 'type', 'power', 'pp', 'accuracy', 'effect_id', 'effect_chance'):
            history = getattr(state.attrs, field).history
            if history.has_changes():
                old, = history.deleted
                if old is not None:
                    loggable_changes[field] = old
        if loggable_changes:
            session.add(t.MoveChangelog(
                move_id=db_move.id,
                changed_in_version_group_id=db_sumo_version_group.id,
                **loggable_changes))

    # Names
    update_names(sumo_move, db_move)

    # Move flags
    old_flag_set = frozenset(db_move.flags)
    new_flag_set = frozenset(db_move_flags[flag.rpartition('.')[2]] for flag in sumo_move.flags)
    for added_flag in new_flag_set - old_flag_set:
        print(f"- NOTE: adding flag {added_flag.identifier}")
        db_move.flags.append(added_flag)
    for removed_flag in old_flag_set - new_flag_set:
        # These aren't real flags (in the sense of being a rippable part of the
        # move struct) and I'm not entirely sure why they're in this table
        if removed_flag.identifier in ('powder', 'bite', 'pulse', 'ballistics', 'mental'):
            continue
        print(f"- NOTE: removing flag {removed_flag.identifier}")
        db_move.flags.remove(removed_flag)

    # Move metadata
    cheap_upsert(
        db_move.meta,
        t.MoveMeta,
        # FIXME populate stat_chance?  but...  it's bogus.
        dict(move=db_move, stat_chance=0),
        category=db_move_categories[sumo_move.category.rpartition('.')[2]],
        ailment=db_move_ailments[sumo_move.ailment.rpartition('.')[2]],

        # TODO these should probably be null (or omitted) in the yaml instead of zero
        min_hits=sumo_move.min_hits or None,
        max_hits=sumo_move.max_hits or None,
        min_turns=sumo_move.min_turns or None,
        max_turns=sumo_move.max_turns or None,

        drain=sumo_move.drain,
        healing=sumo_move.healing,
        crit_rate=sumo_move.crit_rate,
        ailment_chance=sumo_move.ailment_chance,
        flinch_chance=sumo_move.flinch_chance,
    )

    # Flavor text is per-version (group) and thus always new
    # FIXME uhh no it isn't, not if i've already run this script once lol
    """
    for lang, flavor_text in sumo_move.flavor_text.items():
        session.add(t.MoveFlavorText(
            move=db_move,
            version_group=db_sumo_version_group,
            language=db_languages[lang],
            flavor_text=flavor_text,
        ))
    """
session.flush()


session.commit()
print()
print("done")
