"""Helpers for common ways to work with pokedex queries

These include identifier- and name-based lookup, filtering out base forms
of pokemon, and filtering/ordering by name.
"""

from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.orm.exc import NoResultFound

from pokedex.db import tables

### Getter

def get(session, table, identifier=None, name=None, id=None, language=None):
    """Get one object from the database.

    session: The session to use (from pokedex.db.connect())
    table: The table to select from (such as pokedex.db.tables.Move)

    identifier: Identifier of the object
    name: The name of the object
    id: The ID number of the object

    language: A Language to use for name and form_name

    All conditions must match, so it's not a good idea to specify more than one
    of identifier/name/id at once.

    If zero or more than one objects matching the criteria are found, the
    appropriate SQLAlchemy exception is raised.
    """

    query = session.query(table)

    if identifier is not None:
        query = query.filter_by(identifier=identifier)

    if name is not None:
        query = filter_name(query, table, name, language)

    if id is not None:
        # ASSUMPTION: id is the primary key of the table.
        result = query.get(id)
        if result is None:
            # Keep the API
            raise NoResultFound
        else:
            return result

    return query.one()

### Helpers

def filter_name(query, table, name, language, name_attribute='name'):
    """Filter a query by name, return the resulting query

    query: The query to filter
    table: The table of named objects
    name: The name to look for. May be a tuple of alternatives.
    language: The language for "name", or None for the session default
    name_attribute: the attribute to use; defaults to 'name'
    """
    if language is None:
        query = query.filter(getattr(table, name_attribute) == name)
    else:
        names_table = table.names_table
        name_column = getattr(names_table, name_attribute)
        query = query.join(names_table)
        query = query.filter(names_table.foreign_id == table.id)
        query = query.filter(names_table.local_language_id == language.id)
        if isinstance(name, tuple):
            query = query.filter(name_column in name)
        else:
            query = query.filter(name_column == name)
    return query

def order_by_name(query, table, language=None, *extra_languages, **kwargs):
    """Order a query by name.

    query: The query to order
    table: Table of the named objects
    language: The language to order names by. If None, use the
        connection default.
    extra_languages: Extra languages to order by, should the translations for
        `language` be incomplete (or ambiguous).

    name_attribute (keyword argument): the attribute to use; defaults to 'name'

    Uses the identifier as a fallback ordering.
    """
    name_attribute = kwargs.pop('name', 'name')
    if kwargs:
        raise ValueError('Unexpected keyword arguments: %s' % kwargs.keys())
    order_columns = []
    if language is None:
        query = query.outerjoin(table.names_local)
        order_columns.append(func.lower(getattr(table.names_table, name_attribute)))
    else:
        extra_languages = (language, ) + extra_languages
    for language in extra_languages:
        names_table = aliased(table.names_table)
        query = query.outerjoin(names_table)
        query = query.filter(names_table.foreign_id == table.id)
        query = query.filter(names_table.local_language_id == language.id)
        order_columns.append(func.lower(getattr(names_table, name_attribute)))
    order_columns.append(table.identifier)
    query = query.order_by(coalesce(*order_columns))
    return query
