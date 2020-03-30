import re

from sqlalchemy import func
from sqlalchemy.orm import joinedload

import pokedex.db.tables as t


def _parse_range(value):
    v = int(value)
    return lambda x: x == v


CRITERION_RX = re.compile(r"""
    \s*
    (?: (?P<field>[-_a-zA-Z0-9]+): )?
    (?P<pattern>
        (?:
            [^\s"]+?
        )+
    )
""", re.VERBOSE)
def parse_search_string(string):
    """Parses a search string!"""
    criteria = {}
    for match in CRITERION_RX.finditer(string):
        # TODO what if there are several of the same match!
        # TODO the cli needs to do append too
        field = match.group('field') or '*'
        criteria[field] = match.group('pattern')
    return criteria


def search(session, **criteria):
    query = (
        session.query(t.Pokemon)
        .options(
            joinedload(t.Pokemon.species)
        )
    )

    stat_query = (
        session.query(t.PokemonStat.pokemon_id)
        .join(t.PokemonStat.stat)
    )
    do_stat = False

    if criteria.get('name') is not None:
        query = query.join(t.Pokemon.species)
        query = query.join(t.PokemonSpecies.names_local)
        query = query.filter(func.lower(t.PokemonSpecies.names_table.name) == criteria['name'].lower())

    for stat_ident in (u'attack', u'defense', u'special-attack', u'special-defense', u'speed', u'hp'):
        criterion = criteria.get(stat_ident)
        if criterion is None:
            continue

        do_stat = True
        stat_query = stat_query.filter(
            (t.Stat.identifier == stat_ident)
            & _parse_range(criterion)(t.PokemonStat.base_stat)
        )

    if do_stat:
        query = query.filter(t.Pokemon.id.in_(stat_query.subquery()))

    return query.all()
