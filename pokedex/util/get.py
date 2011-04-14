"""Provides simple functions for common queries

These include identifier- and name-based lookup, filtering out base forms
of pokemon, ordering by name, and getting canonical "pokedex" lists (i.e.
ordered and without cruft like alternate pokemon forms or Shadow moves)
"""

from sqlalchemy.orm import aliased

from pokedex.db import tables

### Getters

def get(session, table, identifier=None, name=None, id=None,
        form_identifier=None, form_name=None, language=None, is_pokemon=None):
    """Get one object from the database.

    session: The session to use (from pokedex.db.connect())
    table: The table to select from (such as pokedex.db.tables.Move)

    identifier: Identifier of the object
    name: The name of the object
    id: The ID number of the object
    form_identifier: For pokemon, identifier of the form
    form_name: For pokemon, name of the form

    language: A Language to use for name and form_name
    is_pokemon: If true, specifies that the table should be treated as a
        pokemon table (handling forms specially). If None and table is the
        (unaliased) Pokemon, it is set to True. Otherwise, the pokemon forms
        aren't handled.

    All conditions must match, so it's not a good idea to specify more than one
    of identifier/name/id at once.

    If zero or more than one objects matching the criteria are found, the
    appropriate SQLAlchemy exception is raised.
    Exception: for pokemon, selects the form base unless form_* is given.
    """

    if is_pokemon is None:
        is_pokemon = (table is tables.Pokemon)

    query = session.query(table)

    if identifier is not None:
        query = query.filter_by(identifier=identifier)

    if name is not None:
        query = filter_name(query, table, name, language)

    if id is not None:
        query = query.filter_by(id=id)

    if form_identifier is not None or form_name is not None:
        if is_pokemon:
            query = query.join(table.unique_form)
            if form_identifier is not None:
                query = query.filter(tables.PokemonForm.identifier ==
                        form_identifier)
            if form_name is not None:
                query = filter_name(query, table, form_name, language)
        else:
            raise ValueError(
                "form_identifier and form_name only make sense for pokemon")
    elif is_pokemon:
        query = filter_base_forms(query)

    return query.one()

### Helpers

def filter_name(query, table, name, language):
    """Filter a query by name, return the resulting query

    query: The query to filter
    table: The table of named objects
    name: The name to look for. May be a tuple of alternatives.
    language: The language for "name", or None for the session default
    """
    if language is None:
        query = query.filter(table.name == name)
    else:
        names_table = table.names_table
        query = query.join(names_table)
        query = query.filter(names_table.foreign_id == table.id)
        query = query.filter(names_table.local_language_id == language.id)
        if isinstance(name, tuple):
            query = query.filter(names_table.name in name)
        else:
            query = query.filter(names_table.name == name)
    return query

def filter_base_forms(query):
    """Filter only base forms of pokemon, and return the resulting query
    """
    query = query.filter(tables.Pokemon.forms.any())
    return query

def order_by_name(query, table, language=None, *extra_languages):
    """Order a query by name.

    query: The query to order
    table: Table of the named objects
    language: The language to order names by. If None, use the
        connection default.
    extra_languages: Extra languages to order by, should the translations for
        `language` be incomplete (or ambiguous).

    Uses the identifier as a fallback ordering.
    """
    if language is None:
        query = query.outerjoin(table.names_local)
        query = query.order_by(table.names_table.name)
    else:
        extra_languages = (language, ) + extra_languages
    for language in extra_languages:
        names_table = aliased(table.names_table)
        query = query.outerjoin(names_table)
        query = query.filter(names_table.foreign_id == table.id)
        query = query.filter(names_table.local_language_id == language.id)
        query = query.order_by(names_table.name)
    query = query.order_by(table.identifier)
    return query

_name = object()
def get_all(session, table, order=_name):
    """Shortcut to get an ordered query from table.

    session: The session to use
    table: The table to select from
    order: A clause to order by, or None for no ordering.
        The default is to order by name; this can also be specified explicitly
        with the table's name property (e.g. tables.Pokemon.name). Be aware
        that the query's order_by will not order by name this way.
    """
    query = session.query(table)
    if order is table.name or order is _name:
        query = order_by_name(query, table)
    elif order is not None:
        query = query.order_by(order)
    return query

### Shortcuts

def pokemon(session, order=tables.Pokemon.id):
    """Return a query for all base form pokemon, ordered by id by default

    See get_all for the session and order arguments (but note the default for
    pokemon is to order by id).
    """
    query = get_all(session, tables.Pokemon, order=order)
    query = query.filter(tables.Pokemon.forms.any())
    return query

def moves(session, order=_name):
    """Return a query for moves in the mainline games (i.e. no Shadow moves)

    See get_all for the session and order arguments.
    """
    return get_all(session, tables.Move, order=order).filter(tables.Move.id < 10000)

def types(session, order=_name):
    """Return a query for sane types (i.e. not ???, Shadow)

    See get_all for the session and order arguments.
    """
    return get_all(session, tables.Type, order=order).filter(tables.Type.id < 10000)

def items(session, order=_name):
    """Return a query for items

    See get_all for the session and order arguments.
    """
    return get_all(session, tables.Item, order=order)
