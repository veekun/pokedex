from collections import OrderedDict
import itertools
from pathlib import Path

from camel import Camel
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy.orm import Load

import pokedex.db
import pokedex.db.tables as t
import pokedex.main as main
import pokedex.schema as schema

# FIXME machine to move mapping isn't listed anywhere, oops.  where does that go?

# TODO still obviously missing:
# - pokedex order
# TODO needs manual fixing:
# - item categories
# - fling effects?
# - item effects
# - ability effects
# - has_gender_differences
# - forms_switchable
# - is_battle_only
# - form explanations
# - pokemon and form order
# - evolutions requiring particular locations
# TODO needs fixing codewise:
# - decide if i'm using these new pixel version icons or what
# - remove extraneous "Pokémon" after genus
# - 

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
db_move_methods = {row.identifier: row for row in session.query(t.PokemonMoveMethod)}

# These are by id since move effects don't have identifiers atm
db_move_effects = {row.id: row for row in session.query(t.MoveEffect)}

db_colors = {row.identifier: row for row in session.query(t.PokemonColor)}
db_shapes = {row.identifier: row for row in session.query(t.PokemonShape)}
db_growth_rates = {row.identifier: row for row in session.query(t.GrowthRate)}
db_genders = {row.identifier: row for row in session.query(t.Gender)}
db_evo_triggers = {row.identifier: row for row in session.query(t.EvolutionTrigger)}
db_egg_groups = {row.identifier: row for row in session.query(t.EggGroup)}
db_stats = OrderedDict((row.identifier, row) for row in session.query(t.Stat).order_by(t.Stat.id.asc()))

# Insert some requisite new stuff if it doesn't already exist
db_sumo_generation = session.query(t.Generation).get(7)
if db_sumo_generation:
    db_sumo_version_group = session.query(t.VersionGroup).filter_by(identifier='sun-moon').one()
    db_moon = session.query(t.Version).filter_by(identifier='moon').one()
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


def update_names(sumo_name_map, db_name_map):
    """Update the database's names as necessary, and add any missing ones"""
    for lang, name in sumo_name_map.items():
        old_name = db_name_map.get(db_languages[lang])
        if old_name != name:
            if old_name:
                print(f"- NOTE: changing {old_name!r} to {name!r} in {lang}")
            db_name_map[db_languages[lang]] = name


# Items
print()
print("--- ITEMS ---")
with (out / 'items.yaml').open(encoding='utf8') as f:
    sumo_items = camel.load(f.read())

db_items = {
    row.identifier: row for row in session.query(t.Item)
        .options(Load(t.Item).joinedload('names'))
}

for sumo_identifier, sumo_item in sumo_items.items():
    if sumo_identifier == 'none':
        # FIXME just don't dump these yo
        continue
    print(sumo_identifier)
    db_item = db_items.get(sumo_identifier)
    if not db_item:
        print("- new")
    db_item = cheap_upsert(
        db_item,
        t.Item,
        dict(
            identifier=sumo_identifier,
            # This needs to be done manually, since the categories are 100%
            # fanon invention.  Default to the "x/y unknown" dummy category.
            # NOTE: the categories are linked to pockets but the pockets are
            # different in nearly every game, so, uh
            category_id=10001,
            # FIXME veekun has an "effect" called "berry effect" that just means
            # "do whatever the berry does", and that's terrible, and also doesn't
            # match the games, SIGH
            fling_effect=None,
        ),
        cost=sumo_item.price,
        fling_power=sumo_item.fling_power or None,
    )

    # Names
    update_names(sumo_item.name, db_item.name_map)

    # Populate with dummy effects
    if db_item in session.new:
        db_items[sumo_identifier] = db_item
        db_item.short_effect_map[db_languages['en']] = f"XXX new effect for {sumo_identifier}"
        db_item.effect_map[db_languages['en']] = f"XXX new effect for {sumo_identifier}"

    # Flavor text is per-version (group) and thus always new
    # FIXME not idempotent
    """
    for lang, flavor_text in sumo_item.flavor_text.items():
        session.add(t.ItemFlavorText(
            item=db_item,
            version_group=db_sumo_version_group,
            language=db_languages[lang],
            flavor_text=flavor_text,
        ))
    """

    # Game index
    # FIXME not idempotent
    """
    session.add(t.ItemGameIndex(
        item=db_item,
        generation=db_sumo_generation,
        game_index=sumo_item.game_index,
    ))
    """

    # FIXME can flags be done automatically?  some of them, at least?  they are:
    # - countable
    # - consumable
    # - usable-overworld
    # - usable-in-battle
    # - holdable
    # - holdable-passive
    # - holdable-active
    # - underground

    # TODO aside from natural gift bits, i have no idea where berry data is,
    # and i suspect our existing natural gift effects are way off  :S



# Abilities
print()
print("--- ABILITIES ---")
with (out / 'abilities.yaml').open(encoding='utf8') as f:
    abilities = camel.load(f.read())

db_abilities = {
    row.identifier: row
    for row in session.query(t.Ability)
        .filter_by(is_main_series=True)
        .options(Load(t.Ability).joinedload('names'))
}

for sumo_identifier, sumo_ability in abilities.items():
    print(sumo_identifier)
    db_ability = db_abilities.get(sumo_identifier)
    if db_ability:
        assert sumo_identifier == db_ability.identifier
    else:
        db_abilities[sumo_identifier] = db_ability = t.Ability(
            identifier=sumo_identifier,
            generation_id=7,
            is_main_series=True,
            names=[],
        )
        session.add(db_ability)

    update_names(sumo_ability.name, db_ability.name_map)

    # Flavor text is per-version (group) and thus always new
    # TODO not idempotent
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

db_moves = {}
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

    db_move = db_moves[sumo_identifier] = cheap_upsert(
        db_move,
        t.Move,
        dict(generation_id=7, names=[]),
        identifier=sumo_identifier,
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
    update_names(sumo_move.name, db_move.name_map)

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
    # FIXME not idempotent
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


# Pokémon!  Auugh!
print()
print("--- POKéMON ---")
db_pokemons = {}
db_pokemon_forms = {}
db_pokemon_specieses = {}
for species in (
        session.query(t.PokemonSpecies)
        .options(
            Load(t.PokemonSpecies).joinedload('evolution_chain'),
            Load(t.PokemonSpecies).joinedload('pokemon').joinedload('forms'),
            Load(t.PokemonSpecies).joinedload('pokemon').subqueryload('stats'),
            Load(t.PokemonSpecies).joinedload('pokemon').subqueryload('types'),
            Load(t.PokemonSpecies).joinedload('pokemon').subqueryload('pokemon_abilities'),
            Load(t.PokemonSpecies).subqueryload('forms'),
            Load(t.PokemonSpecies).subqueryload('evolutions'),
            Load(t.PokemonSpecies).subqueryload('egg_groups'),
            Load(t.PokemonSpecies).subqueryload('names'),
            Load(t.PokemonSpecies).joinedload('pokemon').joinedload('forms').subqueryload('names'),
        )
        .all()
    ):
    for form in species.forms:
        db_pokemon_forms[form.identifier] = form
        db_pokemon_forms[species.identifier, form.form_identifier] = form
    for pokemon in species.pokemon:
        db_pokemons[pokemon.identifier] = pokemon
    db_pokemon_specieses[species.identifier] = species

max_pokemon_id = session.query(func.max(t.Pokemon.id)).scalar()
max_pokemon_form_id = session.query(func.max(t.PokemonForm.id)).scalar()

with (out / 'pokemon.yaml').open(encoding='utf8') as f:
    pokemon = camel.load(f.read())

sumo_pokemon_by_species = OrderedDict()
# This maps (Pokémon!) identifiers to { base_pokemon, members }, where
# Pokémon in the same family will (in theory) share the same value
sumo_families = dict()
sumo_evolves_from = dict()  # species!
for sumo_identifier, sumo_pokemon in pokemon.items():
    if sumo_identifier == 'egg':
        continue

    sumo_pokemon.identifier = sumo_identifier
    sumo_species_identifier = sumo_pokemon.form_base_species
    sumo_pokemon_by_species.setdefault(sumo_species_identifier, []).append(sumo_pokemon)

    # Construct the family.  Basic idea is to pretend we're a new family, then
    # look through the evolutions for any existing families and merge them
    family = dict(
        base_pokemon=sumo_identifier,
        members={sumo_identifier},
        db_chain=None,
    )
    try:
        family['db_chain'] = db_pokemon_specieses[sumo_species_identifier].evolution_chain
    except KeyError:
        pass
    for evolution in sumo_pokemon.evolutions:
        into = evolution['into']
        sumo_evolves_from[pokemon[into].form_base_species] = sumo_species_identifier
        if into in sumo_families:
            # If this happens, then the current Pokémon evolves into a Pokémon
            # that's already been seen, therefore this is an earlier evolution
            family['members'].update(sumo_families[into]['members'])
            if not family['db_chain']:
                family['db_chain'] = sumo_families[into]['db_chain']
        else:
            family['members'].add(into)
    # Once we're done, ensure every member is using this same newly-updated dict
    for member in family['members']:
        sumo_families[member] = family

for species_identifier, sumo_pokemons in sumo_pokemon_by_species.items():
    db_species = db_pokemon_specieses.get(species_identifier)
    sumo_form_identifiers = sumo_pokemons[0].form_appearances
    is_concrete = not sumo_form_identifiers

    if is_concrete:
        sumo_form_identifiers = [sumo_pokemon.form_identifier for sumo_pokemon in sumo_pokemons]
    if species_identifier in {'cherrim', 'shellos', 'gastrodon', 'floette', 'furfrou'}:
        # These changed to be concrete at some point, but changing form kind is
        # a pain in the ass and I don't want to do it, so let's not
        is_concrete = False

    # Let's check some stuff first I guess
    print(f"{species_identifier:24s}")
    if db_species:
        if is_concrete:
            # Concrete means every form is a Pokemon, and every Pokemon has one PokemonForm
            if len(db_species.pokemon) != len(db_species.forms):
                print(f"- WARNING: expected the same number of Pokémon and forms but got {len(db_species.pokemon)} vs {len(db_species.forms)}")

            for form in db_species.forms:
                if not form.is_default:
                    print(f"- WARNING: expected every form to be a default but {form.form_identifier} is not")

            sumo_pokemon_identifiers = {pokemon.identifier for pokemon in sumo_pokemons}
            db_pokemon_identifiers = {pokemon.identifier for pokemon in db_species.pokemon}
            added_pokemon = sumo_pokemon_identifiers - db_pokemon_identifiers
            removed_pokemon = db_pokemon_identifiers - sumo_pokemon_identifiers
            if added_pokemon:
                print(f"- NOTE: new forms {added_pokemon}")
            if removed_pokemon:
                print(f"- NOTE: removed forms?? {removed_pokemon}")
        else:
            # Flavor means there's only one Pokemon, and it has one PokemonForm per form
            if len(db_species.pokemon) > 1:
                print(f"- WARNING: expected only one Pokémon but got {db_species.pokemon}")

            default_count = 0
            form_identifiers = set()
            for form in db_species.forms:
                form_identifiers.add(form.form_identifier)
                if form.is_default:
                    default_count += 1
            if default_count != 1:
                print(f"- WARNING: expected exactly one default but found {default_count}")

            for sumo_form_identifier in sumo_form_identifiers:
                if sumo_form_identifier in form_identifiers:
                    form_identifiers.discard(sumo_form_identifier)
                else:
                    print(f"- NOTE: new form {sumo_form_identifier}")

            if form_identifiers:
                print(f"- NOTE: SUMO is missing forms {', '.join(sorted(ident or 'None' for ident in form_identifiers))} ({sumo_form_identifiers})")

    else:
        print(f"- NOTE: new {'concrete' if is_concrete else 'flavor'} form")
        print("   ", is_concrete, "|", sumo_pokemons[0].form_appearances)
        print("   ", [sp.identifier for sp in sumo_pokemons])

    # NOTE: this is a terrible way to store it in the yaml, and also it's
    # inaccurate for gen 7 i think?  and why do i use -1 for genderless instead
    # of null lol
    if sumo_pokemons[0].gender_rate == 255:
        gender_rate = -1
    else:
        # 31 -> 1, etc, up to 254 -> 8
        gender_rate = (sumo_pokemons[0].gender_rate + 2) // 32

    # A Pokémon is a baby if it's the earliest evolution, it cannot breed, and
    # it evolves into something that can breed
    is_baby = False
    sumo_identifier = sumo_pokemons[0].identifier
    sumo_family = sumo_families[sumo_identifier]
    is_baby = (
        sumo_family['base_pokemon'] == sumo_identifier and
        sumo_pokemons[0].egg_groups == ['eg.no-eggs'] and
        any(pokemon[identifier].egg_groups != ['eg.no-eggs']
            for identifier in sumo_family['members'])
    )

    # If there's no evolution chain yet, make one
    # NOTE: i don't have the baby trigger items, because they don't seem to be
    # data; they're in code and i've yet to find them
    db_chain = sumo_family['db_chain']
    if not db_chain:
        db_chain = t.EvolutionChain()
        session.add(db_chain)
        sumo_family['db_chain'] = db_chain

    db_species = db_pokemon_specieses[species_identifier] = cheap_upsert(
        db_species,
        t.PokemonSpecies,
        dict(
            generation_id=7,
            # Avoids database fetches on new rows
            evolutions=[],
            egg_groups=[],
            names=[],
            # Doesn't apply to Pokémon not in FRLG
            habitat_id=None,
            # Doesn't apply to Pokémon not in Conquest
            conquest_order=None,
            # Needs to be populated manually
            # FIXME should i get this by checking for different sprites...?  i
            # don't think that would quite catch everything
            has_gender_differences=False,
            # Needs to be populated manually
            forms_switchable=False,
            # Easier to populate with a separate script after the fact
            order=0,
        ),
        id=sumo_pokemons[0].game_index,
        identifier=species_identifier,
        parent_species=db_pokemon_specieses[sumo_evolves_from[species_identifier]] if species_identifier in sumo_evolves_from else None,
        evolution_chain=db_chain,
        # NOTE: color is actually per-concrete
        color=db_colors[sumo_pokemons[0].color.rpartition('.')[2]],
        # NOTE: shape is actually per-flavor
        shape=db_shapes[sumo_pokemons[0].shape.rpartition('.')[2]],
        gender_rate=gender_rate,
        # NOTE: capture rate is actually per-concrete
        capture_rate=sumo_pokemons[0].capture_rate,
        base_happiness=sumo_pokemons[0].base_happiness,
        is_baby=is_baby,
        # NOTE: this is nonsense for pokémon that can't be in eggs (which is
        # not a thing i'm sure i have tracked atm, since i don't directly dump
        # the egg data)
        hatch_counter=sumo_pokemons[0].hatch_counter,
        # NOTE: actually per concrete even though that doesn't entirely make sense haha
        growth_rate=db_growth_rates[sumo_pokemons[0].growth_rate.rpartition('.')[2]],
    )

    # NOTE names are given per concrete form but are really truly a species thing
    # FIXME i am not sure doing both of these at the same time actually works
    update_names(sumo_pokemons[0].name, db_species.name_map)
    update_names(sumo_pokemons[0].genus, db_species.genus_map)

    # Flavor text is per-version (group) and thus always new
    # FIXME this is wrong; flavor text is per form!
    # FIXME not idempotent
    # FIXME get for sun as well
    """
    for lang, flavor_text in sumo_pokemons[0].flavor_text.items():
        if flavor_text:
            session.add(t.PokemonSpeciesFlavorText(
                species_id=db_species.id,
                version=db_moon,
                language=db_languages[lang],
                flavor_text=flavor_text,
            ))
    """

    # FIXME i fucked something up!  new pokemon's forms ended up in the
    # stratosphere and also not marked as defaults.  had to do:
    # update pokemon_forms set id = pokemon_id, is_default = true where form_order = 1 and id > 10000 and pokemon_id between 720 and 9999;
    sumo_db_pokemon_pairs = []
    sumo_db_pokemon_form_pairs = []
    if species_identifier == 'floette':
        # This is a fucking mess; there are two concrete Pokémon, and one of
        # them has multiple flavor forms, so, goddamn.  Let's just assume
        # Sun/Moon didn't change anything, I guess.
        # TODO fix this?  requires making a tree of concrete -> flavor and
        # consolidating the below branches
        for sumo_pokemon in sumo_pokemons:
            if sumo_pokemon.identifier == 'floette-red':
                sumo_db_pokemon_pairs.append((sumo_pokemon, db_pokemons['floette']))
            elif sumo_pokemon.identifier == 'floette-eternal':
                sumo_db_pokemon_pairs.append((sumo_pokemon, db_pokemons['floette-eternal']))
    elif is_concrete:
        # Concrete: multiple yaml records, each is a Pokemon row with one PokemonForm
        for form_order, (sumo_pokemon, sumo_form_identifier) in enumerate(zip(sumo_pokemons, sumo_form_identifiers), start=1):
            if sumo_pokemon.identifier in db_pokemons:
                id = db_pokemons[sumo_pokemon.identifier].id
            else:
                max_pokemon_id += 1
                id = max_pokemon_id
            db_pokemon = cheap_upsert(
                db_pokemons.get(sumo_pokemon.identifier),
                t.Pokemon,
                dict(
                    # Avoids database fetches on new rows
                    types=[],
                    pokemon_abilities=[],
                    items=[],
                    names=[],
                    stats=[],
                    # Easier to populate manually
                    order=0,
                ),
                id=id,
                identifier=sumo_pokemon.identifier,
                species=db_species,
                # TODO the units in the yaml don't match my goofy plan from rby
                # (which i'm not 100% on anyway)
                height=sumo_pokemon.height // 10,
                weight=sumo_pokemon.weight,
                base_experience=sumo_pokemon.base_experience,
                # NOTE: this is less about a real sense of default-ness and
                # more about "what form should veekun default to when looking
                # at this species" (which doesn't belong in the data tbh)
                is_default=form_order == 1,
            )

            db_pokemons[sumo_pokemon.identifier] = db_pokemon
            sumo_db_pokemon_pairs.append((sumo_pokemon, db_pokemon))

            db_form = next(iter(db_pokemons[sumo_pokemon.identifier].forms), None)
            if db_form:
                id = db_form.id
            else:
                max_pokemon_form_id += 1
                id = max_pokemon_form_id
            db_form = cheap_upsert(
                db_form,
                t.PokemonForm,
                dict(
                    version_group=db_sumo_version_group,
                    # Easier to do separately
                    order=0,
                    # Needs doing manually
                    is_battle_only=False,
                ),
                id=id,
                identifier=sumo_pokemon.identifier,
                form_identifier=sumo_form_identifier,
                pokemon=db_pokemons[sumo_pokemon.identifier],
                is_default=True,
                is_mega=bool(sumo_form_identifier and sumo_form_identifier.startswith('mega')),
                form_order=form_order,
            )

            # NOTE the db also has a "pokemon_name" field, e.g. "Sky Shaymin",
            # but i don't think that's official?  ok well it's marked as
            # official but show me where the games say that
            update_names(sumo_pokemon.form_name, db_form.form_name_map)
    else:
        # Flavor: one yaml record, one Pokemon, multiple PokemonForms
        # TODO i think there are names for flavor form but the yaml has nowhere to store them at the moment
        sumo_pokemon = sumo_pokemons[0]
        db_pokemon = cheap_upsert(
            next(iter(db_species.pokemon), None),
            t.Pokemon,
            dict(
                types=[],
                pokemon_abilities=[],
                items=[],
                names=[],
                stats=[],
                order=0,
            ),
            id=sumo_pokemons[0].game_index,
            identifier=species_identifier,
            species=db_species,
            # TODO the units in the yaml don't match my goofy plan from rby
            # (which i'm not 100% on anyway)
            height=sumo_pokemon.height // 10,
            weight=sumo_pokemon.weight,
            base_experience=sumo_pokemon.base_experience,
            is_default=True,
        )
        sumo_db_pokemon_pairs.append((sumo_pokemon, db_pokemon))

        for form_order, form_identifier in enumerate(sumo_form_identifiers, start=1):
            full_form_identifier = species_identifier + ('-' + form_identifier if form_identifier else '')
            if full_form_identifier in db_pokemon_forms:
                id = db_pokemon_forms[full_form_identifier].id
            else:
                max_pokemon_form_id += 1
                id = max_pokemon_form_id
            cheap_upsert(
                db_pokemon_forms.get(full_form_identifier),
                t.PokemonForm,
                dict(
                    version_group=db_sumo_version_group,
                    order=0,
                    # Needs doing manually
                    is_battle_only=False,
                ),
                id=id,
                identifier=full_form_identifier,
                form_identifier=form_identifier,
                pokemon=db_pokemon,
                is_default=id < 10000,
                is_mega=bool(form_identifier and form_identifier.startswith('mega')),
                # FIXME this is wrong if there are existing forms that disappeared in sumo
                form_order=form_order,
            )

    # FIXME: lack of 'unknown' kinda throws things off for arceus

    session.flush()

    # Egg groups
    old_egg_groups = frozenset(db_species.egg_groups)
    new_egg_groups = frozenset(db_egg_groups[ident.rpartition('.')[2]] for ident in sumo_pokemons[0].egg_groups)
    for new_egg_group in new_egg_groups - old_egg_groups:
        print(f"- adding egg group {new_egg_group}")
        db_species.egg_groups.append(new_egg_group)
    for old_egg_group in old_egg_groups - new_egg_groups:
        print(f"- removing egg group {old_egg_group}")
        db_species.egg_groups.remove(old_egg_group)

    # Do stuff that's per concrete Pokémon in the db
    for sumo_pokemon, db_pokemon in sumo_db_pokemon_pairs:
        # Types
        for i, (type_ident, db_type) in enumerate(itertools.zip_longest(sumo_pokemon.types, db_pokemon.types)):
            slot = i + 1
            _, _, veekun_ident = type_ident.rpartition('.')
            if not db_type:
                db_type = db_types[veekun_ident]
                print(f"- adding type {db_type}")
                session.add(t.PokemonType(
                    pokemon_id=db_pokemon.id,
                    type_id=db_type.id,
                    slot=i + 1,
                ))
            elif not type_ident:
                print(f"- WARNING: seem to have LOST type {db_type}, this is not supported")
            elif db_type.identifier == veekun_ident:
                pass
            else:
                print(f"- WARNING: type {db_type} has CHANGED TO {type_ident}, this is not supported")

        # Stats
        seen_stats = set()
        for existing_stat in db_pokemon.stats:
            stat_identifier = existing_stat.stat.identifier
            seen_stats.add(stat_identifier)
            cheap_upsert(
                existing_stat,
                t.Stat,
                dict(),
                base_stat=sumo_pokemon.base_stats[stat_identifier],
                effort=sumo_pokemon.effort[stat_identifier],
            )
        for stat_identifier, stat in db_stats.items():
            if stat.is_battle_only:
                continue
            if stat_identifier in seen_stats:
                continue
            db_pokemon.stats.append(t.PokemonStat(
                stat=stat,
                base_stat=sumo_pokemon.base_stats[stat_identifier],
                effort=sumo_pokemon.effort[stat_identifier],
            ))

        # Abilities
        old_ability_slots = {row.slot: row for row in db_pokemon.pokemon_abilities}
        new_ability_slots = {i + 1: ability_ident for (i, ability_ident) in enumerate(sumo_pokemon.abilities)}
        if new_ability_slots.get(2) == new_ability_slots[1]:
            del new_ability_slots[2]
        if new_ability_slots.get(3) == new_ability_slots[1]:
            del new_ability_slots[3]
        for slot in old_ability_slots.keys() | new_ability_slots.keys():
            old_ability_row = old_ability_slots.get(slot)
            new_ability_ident = new_ability_slots.get(slot)
            if not old_ability_row:
                _, _, veekun_ident = new_ability_ident.rpartition('.')
                db_ability = db_abilities[veekun_ident]
                print(f"- adding ability {db_ability}")
                session.add(t.PokemonAbility(
                    pokemon_id=db_pokemon.id,
                    ability_id=db_ability.id,
                    slot=slot,
                    is_hidden=(slot == 3),
                ))
            elif not new_ability_ident:
                print(f"- WARNING: seem to have LOST ability {old_ability_row.ability}, this is not supported")
            elif old_ability_row.ability.identifier == new_ability_ident.rpartition('.')[2]:
                pass
            else:
                _, _, veekun_ident = new_ability_ident.rpartition('.')
                db_ability = db_abilities[veekun_ident]
                print(f"- changing ability in slot {slot} from {old_ability_row.ability} to {db_ability}")
                old_ability_row.ability = db_ability

        """
        # Items
        # FIXME need items from the other game argh, they're per-version
        # TODO not idempotent
        for item_identifier, rarity in sumo_pokemon.held_items.items():
            session.add(t.PokemonItem(
                pokemon=db_pokemon,
                version=db_moon,
                item=db_items[item_identifier.rpartition('.')[2]],
                rarity=rarity,
            ))

        # Moves
        # TODO not idempotent
        for method_identifier, moves in sumo_pokemon.moves.items():
            last_row = None
            order = None
            seen = set()
            for move_identifier in moves:
                if method_identifier == 'level-up':
                    # FIXME THIS SUX
                    ((level, move_identifier),) = move_identifier.items()
                else:
                    level = 0
                if level and last_row and level == last_row.level:
                    if order is None:
                        last_row.order = 1
                        order = 2
                    else:
                        order += 1
                else:
                    order = None

                # TODO this is stupid but braviary learns superpower at level
                # 1, twice, and I'm not really sure what to do about that; is
                # it correct to remove from the data?
                key = (move_identifier, level)
                if key in seen:
                    continue
                seen.add(key)

                last_row = t.PokemonMove(
                    pokemon=db_pokemon,
                    version_group=db_sumo_version_group,
                    move=db_moves[move_identifier.rpartition('.')[2]],
                    method=db_move_methods[method_identifier],
                    level=level,
                    order=order,
                )
                session.add(last_row)
        """


# Do evolution after adding all the Pokémon, since Pokémon tend to evolve into
# later Pokémon that wouldn't have been inserted yet.  It's also tricky, since
# there might be an existing matching record among several
for species_identifier, sumo_pokemons in sumo_pokemon_by_species.items():
    for sumo_evolution in sumo_pokemons[0].evolutions:
        # Evolutions are on the evolver in the yaml, but evolvee in the db
        db_species = db_pokemon_specieses[pokemon[sumo_evolution['into']].form_base_species]

        # NOTE: this does not seem to be in the data itself so i have to
        # hardcode it here, argh
        if 'traded-with' in sumo_evolution:
            if species_identifier == 'karrablast':
                traded_with = db_pokemon_specieses['shelmet']
            elif species_identifier == 'shelmet':
                traded_with = db_pokemon_specieses['karrablast']
            else:
                raise ValueError(f"Don't know who trade-evolves with {sumo_species_identifier}")
        else:
            traded_with = None

        expected = dict(
            evolved_species=db_species,
            trigger=db_evo_triggers[sumo_evolution['trigger'].rpartition('.')[2]],
            trigger_item=db_items[sumo_evolution['trigger-item'].rpartition('.')[2]] if 'trigger-item' in sumo_evolution else None,
            minimum_level=sumo_evolution.get('minimum-level'),
            gender=db_genders[sumo_evolution['gender']] if 'gender' in sumo_evolution else None,
            # NOTE: this needs populating manually; it's not in the yaml either
            location=None,
            held_item=db_items[sumo_evolution['held-item'].rpartition('.')[2]] if 'held-item' in sumo_evolution else None,
            time_of_day=sumo_evolution.get('time-of-day'),
            known_move=db_moves[sumo_evolution['known-move'].rpartition('.')[2]] if 'known-move' in sumo_evolution else None,
            known_move_type=db_types[sumo_evolution['known-move-type'].rpartition('.')[2]] if 'known-move-type' in sumo_evolution else None,
            minimum_happiness=sumo_evolution.get('minimum-friendship'),
            minimum_beauty=sumo_evolution.get('minimum-beauty'),
            minimum_affection=sumo_evolution.get('minimum-affection'),
            relative_physical_stats={'attack': -1, 'defense': 1, 'equal': 0, None: None}[sumo_evolution.get('higher-physical-stat')],
            party_species=db_pokemon_specieses[sumo_evolution['party-member'].rpartition('.')[2]] if 'party-member' in sumo_evolution else None,
            party_type=db_types[sumo_evolution['party-member-type'].rpartition('.')[2]] if 'party-member-type' in sumo_evolution else None,
            trade_species=traded_with,
            needs_overworld_rain=sumo_evolution.get('overworld-weather') == 'rain',
            turn_upside_down=sumo_evolution.get('upside-down', False),
        )

        # FIXME need to finish...  filling this out
        for db_evolution in db_species.evolutions:
            if all(v == getattr(db_evolution, k) for (k, v) in expected.items()):
                break
        else:
            print(f"- adding new evolution for {species_identifier} -> {sumo_evolution['into']}")
            session.add(t.PokemonEvolution(**expected))

session.flush()



#print("ROLLING BACK")
#session.rollback()
session.commit()
print()
print("done")
