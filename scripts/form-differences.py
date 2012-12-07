#!/usr/bin/env python2

"""List the ways that pokemon forms differ from one another.

This is not a one-shot script! It is probably unmaintained though.
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

def groupdict(it, key):
    """Group an iterable by a key and return a dict."""

    return dict((group_key, list(group)) for group_key, group in itertools.groupby(it, key))

def getmoves(form):
    all_moves = sorted((move.method.identifier, move.version_group_id, move.move_id, move.level, move.order) for move in form.pokemon.pokemon_moves)

    return groupdict(all_moves, lambda x: x[0])


def gcd(a, b):
    keys = set(a.keys()) & set(b.keys())
    result = {}
    for k in keys:
        if a[k] == b[k]:
            result[k] = a[k]
    return result

def find_uncommon_keys(dicts):
    keys = set(dicts[0])

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

    uncommon = sorted(find_uncommon_keys(map(getform, forms)))
    uncommon_moves = sorted(find_uncommon_keys(map(getmoves, forms)))

    if uncommon_moves:
        uncommon.append("moves ({})".format(", ".join(sorted(uncommon_moves))))

    print "{}: {}".format(species.name, ", ".join(uncommon))
