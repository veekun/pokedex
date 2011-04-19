"""Helpers for common ways to work with pokedex queries

These include identifier- and name-based lookup, filtering out base forms
of pokemon, and filtering/ordering by name.
"""

from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.functions import coalesce

from pokedex.db import tables

### Getter

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
    order_columns = []
    if language is None:
        query = query.outerjoin(table.names_local)
        order_columns.append(func.lower(table.names_table.name))
    else:
        extra_languages = (language, ) + extra_languages
    for language in extra_languages:
        names_table = aliased(table.names_table)
        query = query.outerjoin(names_table)
        query = query.filter(names_table.foreign_id == table.id)
        query = query.filter(names_table.local_language_id == language.id)
        order_columns.append(func.lower(names_table.name))
    order_columns.append(table.identifier)
    query = query.order_by(coalesce(*order_columns))
    return query
