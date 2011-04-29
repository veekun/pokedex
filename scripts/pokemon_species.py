# Encoding: UTF-8
"""Reorganize Pokemon, PokemonForm, etc. to Species, Pokemon, etc.

This is an unmaintained one-shot script, only included in the repo for
reference.

"""

import csv
import os

from pokedex import defaults

number_of_species = 649
high_id_start = 10000

csv_dir = defaults.get_default_csv_dir()

def to_dict(filename):
    fullname = os.path.join(csv_dir, filename)
    reader = csv.reader(open(fullname))
    column_names = reader.next()
    entries = dict()
    for row in reader:
        row_dict = dict(zip(column_names, row))
        entries[row_dict.get('id', row_dict.get('pokemon_id'))] = row_dict
    return entries, column_names

pokemon, pokemon_columns = to_dict('pokemon.csv')
forms, form_columns = to_dict('pokemon_forms.csv')
form_groups, form_group_columns = to_dict('pokemon_form_groups.csv')
evolution_chains, evolution_chain_columns = to_dict('evolution_chains.csv')

result_columns = dict(
    species='''id identifier generation_id evolves_from_species_id
        evolution_chain_id color_id shape_id habitat_id
        growth_rate_id gender_rate capture_rate base_happiness is_baby
        hatch_counter has_gender_differences forms_switchable'''.split(),
    pokemon='''id species_id height weight base_experience order'''.split(),
    form='''id form_identifier pokemon_id introduced_in_version_group_id
        is_default is_battle_only order'''.split(),
    chain='''id baby_trigger_item_id'''.split(),
    )

def normalize_id(id):
    id = int(id)
    if id > number_of_species:
        id = id - high_id_start + number_of_species
    return id

def put(dct, entry):
    """Put entry in dct. If already there, check it's the same.
    """
    id = int(entry['id'])
    if id in dct:
        if entry == dct[id]:
            pass
        else:
            print entry
            print dct[id]
            assert False
    else:
        dct[id] = entry

forms_switchable = dict(
        castform=True,
        unown=False,
        darmanitan=True,
        basculin=False,
        rotom=True,
        shaymin=True,
        deerling=True,
        sawsbuck=True,
        arceus=True,
        pichu=False,
        giratina=True,
        burmy=True,
        wormadam=False,
        deoxys=True,
        genesect=True,
        meloetta=True,
        gastrodon=False,
        cherrim=True,
        shellos=False,
    )

result_species = dict()
result_pokemon = dict()
result_forms = dict()
result_chains = dict()

for form_id, source_form in forms.items():
    pokemon_id = source_form['unique_pokemon_id'] or source_form['form_base_pokemon_id']
    species_id = source_form['form_base_pokemon_id']
    source_pokemon = pokemon[pokemon_id]
    source_evolution_chain = evolution_chains[source_pokemon['evolution_chain_id']]
    try:
        source_group = form_groups[species_id]
    except KeyError:
        source_group = dict(is_battle_only=0)
    all_fields = dict(source_form)
    all_fields.update(source_group)
    all_fields.update(source_pokemon)
    all_fields.update(source_evolution_chain)
    del all_fields['id']
    new_species = dict()
    for column_name in result_columns['species']:
        if column_name == 'id':
            new_species[column_name] = normalize_id(species_id)
        elif column_name == 'evolves_from_species_id':
            new_species[column_name] = pokemon[species_id]['evolves_from_pokemon_id']
        elif column_name == 'shape_id':
            new_species[column_name] = all_fields['pokemon_shape_id']
        elif column_name == 'forms_switchable':
            if species_id in form_groups:
                new_species[column_name] = forms_switchable[source_pokemon['identifier']]
            else:
                new_species[column_name] = 0
        else:
            new_species[column_name] = all_fields[column_name]
    put(result_species, new_species)
    new_pokemon = dict()
    for column_name in result_columns['pokemon']:
        if column_name == 'id':
            new_pokemon[column_name] = normalize_id(pokemon_id)
        elif column_name == 'species_id':
            new_pokemon[column_name] = species_id
        else:
            new_pokemon[column_name] = all_fields[column_name]
    put(result_pokemon, new_pokemon)
    new_form = dict()
    for column_name in result_columns['form']:
        if column_name == 'id':
            new_form[column_name] = normalize_id(form_id)
        elif column_name == 'pokemon_id':
            new_form[column_name] = normalize_id(pokemon_id)
        elif column_name == 'form_identifier':
            new_form[column_name] = source_form['identifier']
        elif column_name == 'is_battle_only':
            if source_form['unique_pokemon_id'] == source_form['form_base_pokemon_id']:
                # Default form, herefore not battle-only
                new_form[column_name] = '0'
            else:
                # Keep
                new_form[column_name] = all_fields[column_name]
        else:
            new_form[column_name] = all_fields[column_name]
    put(result_forms, new_form)
    new_chain = dict(source_evolution_chain)
    del new_chain['growth_rate_id']
    put(result_chains, new_chain)

def write_csv(dct, fieldnames, filename):
    fullname = os.path.join(csv_dir, filename)
    reader = csv.DictWriter(open(fullname, 'w'), fieldnames)
    reader.writerow(dict((n,n) for n in fieldnames))
    for id, row in sorted(dct.items()):
        reader.writerow(row)

write_csv(result_species, result_columns['species'], 'pokemon_species.csv')
write_csv(result_pokemon, result_columns['pokemon'], 'pokemon.csv')
write_csv(result_forms, result_columns['form'], 'pokemon_forms.csv')
write_csv(result_chains, result_columns['chain'], 'evolution_chains.csv')

