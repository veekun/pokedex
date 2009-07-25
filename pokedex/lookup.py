# encoding: utf8
import re

from sqlalchemy.sql import func
import whoosh
from whoosh.qparser import QueryParser
import whoosh.spelling

import pokedex.db.tables as tables

# Dictionary of table name => table class.
# Need the table name so we can get the class from the table name after we
# retrieve something from the index
indexed_tables = {}
for cls in [
        tables.Pokemon,
    ]:
    indexed_tables[cls.__tablename__] = cls

index_bits = {}
def get_index(session):
    """Returns (index, speller).

    Creates an index if one does not exist.
    """

    if index_bits:
        return index_bits['index'], index_bits['speller']

    store = whoosh.store.RamStorage()
    schema = whoosh.fields.Schema(
        name=whoosh.fields.ID(stored=True),
        spelling_name=whoosh.fields.ID(stored=True),
        table=whoosh.fields.STORED,
        row_id=whoosh.fields.STORED,
        language_id=whoosh.fields.STORED,
    )

    index = whoosh.index.Index(store, schema=schema, create=True)
    writer = index.writer()

    # Index every name in all our tables of interest
    for cls in indexed_tables.values():
        q = session.query(cls)

        # Only index base Pokémon formes
        if hasattr(cls, 'forme_base_pokemon_id'):
            q = q.filter_by(forme_base_pokemon_id=None)

        for row in q.yield_per(5):
            name = row.name.lower()
            spelling_name = re.sub('[^a-z]', '', name)
            writer.add_document(name=name,
                                spelling_name=spelling_name,
                                table=cls.__tablename__,
                                row_id=row.id)

    writer.commit()

    ### Construct a spell-checker index
    speller = whoosh.spelling.SpellChecker(index.storage)

    # Can't use speller.add_field because it tries to intuit a frequency, and
    # names are in an ID field, which seems to be immune to frequency.
    # Not hard to add everything ourselves, though
    reader = index.doc_reader()
    speller.add_words([ _['spelling_name'] for _ in reader ])
    reader.close()

    index_bits['index'] = index
    index_bits['speller'] = speller
    index_bits['store'] = store
    return index_bits['index'], index_bits['speller']

def lookup(session, name, exact_only=False):
    """Attempts to find some sort of object, given a database session and name.

    Returns (objects, exact) where `objects` is a list of database objects, and
    `exact` is True iff the given name matched the returned objects exactly.

    This function ONLY does fuzzy matching if there are no exact matches.

    Formes are not returned; "Shaymin" will return only grass Shaymin.

    Currently recognizes:
    - Pokémon names: "Eevee"
    """

    exact = True

    # Alas!  We have to make three attempts to find anything with this index.
    # First: Try an exact match for a name in the index.
    # Second: Try an exact match for a stripped-down name in the index.
    # Third: Get spelling suggestions.
    # The spelling module apparently only indexes *words* -- that is, [a-z]+.
    # So we have a separate field that contains the same name, stripped down to
    # just [a-z]+.
    # Unfortunately, exact matches aren't returned as spelling suggestions, so
    # we also have to do a regular index match against this separate field.
    # Otherwise, 'nidoran' will never match anything
    index, speller = get_index(session)

    # Look for exact name
    parser = QueryParser('name', schema=index.schema)
    results = index.find(name.lower(), parser=parser)

    if not exact_only:
        # Look for a match with a reduced a-z name
        if not results:
            parser = QueryParser('spelling_name', schema=index.schema)
            results = index.find(name.lower(), parser=parser)

        # Look for some fuzzy matches
        if not results:
            results = []
            exact = False

            for suggestion in speller.suggest(name, 3):
                results.extend( index.find(suggestion, parser=parser) )

    # Convert results to db objects
    objects = []
    seen = {}
    for result in results:
        # Skip dupe results
        seen_key = result['table'], result['row_id']
        if seen_key in seen:
            continue
        seen[seen_key] = True

        cls = indexed_tables[result['table']]
        obj = session.query(cls).get(result['row_id'])
        objects.append(obj)

    return objects, exact
