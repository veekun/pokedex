#!/usr/bin/env python2

"""List the ways that pokemon forms differ from one another.

This is not a one-shot script--it is probably unmaintained though!
"""

import itertools

from pokedex.db import connect
import pokedex.db.tables as t
from sqlalchemy.orm import lazyload, joinedload, subqueryload

session = connect()
#session.bind.echo = True

def getstats(stats):
    return dict((stat.stat_id, stat.base_stat) for stat in stats)

def geteffort(stats):
    return dict((stat.stat_id, stat.effort) for stat in stats)

def getpokeathlon(stats):
    return dict((stat.pokeathlon_stat_id, (stat.minimum_stat, stat.base_stat, stat.maximum_stat)) for stat in stats)

def getitems(items):
    return sorted((item.version_id, item.item_id, item.rarity) for item in items)

def getform(form):
    return {
        'ability': form.pokemon.all_abilities,
        'items': getitems(form.pokemon.items),
        'pokeathlon': getpokeathlon(form.pokeathlon_stats),
        'stats': getstats(form.pokemon.stats),
        'effort': geteffort(form.pokemon.stats),
        'type': form.pokemon.types,
        'exp': form.pokemon.base_experience,
        'weight': form.pokemon.weight,
        'height': form.pokemon.height,
    }

def getmoves(form):
    moves = sorted((move.version_group_id, move.method.identifier, move.move_id, move.level, move.order) for move in form.pokemon.pokemon_moves)

    # {version: {method: moves}}
    version_method_moves = {}
    for version, group in itertools.groupby(moves, lambda x: x[0]):
        version_method_moves[version] = method_moves = {}
        for method, group in itertools.groupby(group, lambda x: x[1]):
            method_moves[method] = list(group)

    return version_method_moves

def dictacc(a, b):
    for k in b:
        if k not in a:
            a[k] = []
        a[k] += [b[k]]
    return a

def union(sets):
    return reduce(set.union, sets, set())

def gcd(a, b):
    """Return a new dict containing only items which have the same value in both a and b."""
    keys = set(a.keys()) & set(b.keys())
    result = {}
    for k in keys:
        if a[k] == b[k]:
            result[k] = a[k]
    return result

def find_uncommon_keys(dicts):
    keys = union(d.keys() for d in dicts)

    common_keys = set(reduce(gcd, dicts).keys())
    unique_keys = keys - common_keys

    return unique_keys

q = session.query(t.PokemonSpecies)
q = q.options(
    lazyload('default_pokemon'),

    joinedload('forms'),
    lazyload('forms.pokemon'),
)

for species in q.all():
    forms = species.forms

    if len(forms) == 1:
        continue

    forms = (session.query(t.PokemonForm)
        .join(t.Pokemon)
        .filter(t.Pokemon.species_id==species.id)
        .options(
            subqueryload('pokeathlon_stats'),

            joinedload('pokemon'),
            joinedload('pokemon.all_abilities'),
            joinedload('pokemon.items'),
            joinedload('pokemon.types'),
            joinedload('pokemon.pokemon_moves.method'),
            #joinedload('pokemon.pokemon_moves.version_group'),
            subqueryload('pokemon.stats'),
            subqueryload('pokemon.pokemon_moves'),

            lazyload('pokemon.default_form'),
            lazyload('pokemon.forms'),
            lazyload('pokemon.items.item'),
            lazyload('pokemon.pokemon_moves.pokemon'),
            lazyload('pokemon.pokemon_moves.move'),
            lazyload('pokemon.species'),
        )
        .all()
    )

    ### Okay, grab some info for each form and and find the differences
    uncommon = sorted(find_uncommon_keys(map(getform, forms)))

    ### Moves are a bit different.
    ### First off, we want to split them up by method so we can narrow down the
    ### difference a little; this works the same as above. Second, if a form
    ### has no moves at all in some version group (because it didn't exist yet)
    ### then we don't want to count that as a difference.

    # Start off by grabbing the movepool for each form
    # This gives us pools = [{version: {method: moves}}]
    pools = [getmoves(form) for form in forms]
    # Next we combine the pools to get {version: [{method: moves}]}
    version_pools = reduce(dictacc, pools, {})
    # Now we can calculate the uncommon methods in each version.
    uncommon_move_methods = union(map(find_uncommon_keys, version_pools.values()))

    if uncommon_move_methods:
        uncommon.append("moves ({})".format(", ".join(sorted(uncommon_move_methods))))

    print "{}: {}".format(species.name, ", ".join(uncommon))
