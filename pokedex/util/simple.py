"""Simple lists of things for simple scripts

If you want to get a pokemon list, and you don't want it to include three
Wormadams and a whole bunch of Rotoms because of how the database is
structured, this module is for you.

The returned queries basically contain what a pokedex would show you.
You should make no other assumptions about them.

If you need to make assumptions, feel free to use these functions as examples
of what to watch out for.
"""

from pokedex.db import tables
from pokedex.db.util import filter_base_forms, order_by_name

def pokemon(session):
    """Get a "sane" list of pokemon

    WARNING: The result of this function is not very well defined.
    If you want something specific, build that specific query yourself.

    Currently, all base forms are returned, in evolution-preserving order
    """
    query = session.query(tables.Pokemon)
    query = query.order_by(tables.Pokemon.order)
    query = filter_base_forms(query)
    return query

def moves(session):
    """Get a "sane" list of moves

    WARNING: The result of this function is not very well defined.
    If you want something specific, build that specific query yourself.

    Currently, moves from mainline games are returned, sored by name
    """
    query = session.query(tables.Move)
    query = order_by_name(query, tables.Move)
    query = query.filter(tables.Move.id < 10000)
    return query

def types(session):
    """Get a "sane" list of types

    WARNING: The result of this function is not very well defined.
    If you want something specific, build that specific query yourself.

    Currently, generation V types are returned, sored by name
    """
    query = session.query(tables.Type)
    query = order_by_name(query, tables.Type)
    query = query.filter(tables.Type.id < 10000)
    return query

def items(session):
    """Get a "sane" list of items

    WARNING: The result of this function is not very well defined.
    If you want something specific, build that specific query yourself.

    Currently, items are sored by name
    """
    query = session.query(tables.Item)
    query = order_by_name(query, tables.Item)
    return query
