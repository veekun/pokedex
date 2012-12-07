#!/usr/bin/env python2

"""List the ways that pokemon forms differ from one another.

This is not a one-shot script! It is probably unmaintained though.
"""

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
    return list(sorted((item.version_id, item.item, item.rarity) for item in items))

def getmoves(moves):
    return list(sorted((move.version_group_id, move.move_id, move.pokemon_move_method_id, move.level, move.order) for move in moves))

def getform(form):
    return {
        'ability': form.pokemon.all_abilities,
        'items': getitems(form.pokemon.items),
        'moves': getmoves(form.pokemon.pokemon_moves),
        'pokeathlon': getpokeathlon(form.pokeathlon_stats),
        'stats': getstats(form.pokemon.stats),
        'effort': geteffort(form.pokemon.stats),
        'types': form.pokemon.types,
        'exp': form.pokemon.base_experience,
        'weight': form.pokemon.weight,
        'height': form.pokemon.height,
    }

def gcd(a, b):
    keys = set(a.keys()) & set(b.keys())
    result = {}
    for k in keys:
        if a[k] == b[k]:
            result[k] = a[k]
    return result

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
            joinedload('pokemon'),
            joinedload('pokemon.all_abilities'),
            joinedload('pokemon.items'),
            joinedload('pokemon.stats'),
            joinedload('pokemon.types'),
            joinedload('pokeathlon_stats'),
            subqueryload('pokemon.pokemon_moves'),
            lazyload('pokemon.pokemon_moves.pokemon'),
            lazyload('pokemon.pokemon_moves.move'),
        )
        .all()
    )

    keys = set(getform(forms[0]).keys())
    common_keys = set(reduce(gcd, map(getform, forms)).keys())
    unique_keys = keys - common_keys

    print "{}: {}".format(species.name, ", ".join(sorted(unique_keys)))
