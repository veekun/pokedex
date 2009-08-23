# encoding: utf8
from collections import namedtuple
import os, os.path
import pkg_resources
import re

from sqlalchemy.sql import func
import whoosh
import whoosh.filedb.filestore
import whoosh.filedb.fileindex
import whoosh.index
from whoosh.qparser import QueryParser
import whoosh.spelling

from pokedex.db import connect
import pokedex.db.tables as tables
from pokedex.roomaji import romanize

# Dictionary of table name => table class.
# Need the table name so we can get the class from the table name after we
# retrieve something from the index
indexed_tables = {}
for cls in [
        tables.Ability,
        tables.Item,
        tables.Move,
        tables.Pokemon,
        tables.Type,
    ]:
    indexed_tables[cls.__tablename__] = cls

def open_index(directory=None, session=None, recreate=False):
    """Opens the whoosh index stored in the named directory and returns (index,
    speller).  If the index doesn't already exist, it will be created.

    `directory`
        Directory containing the index.  Defaults to a location within the
        `pokedex` egg directory.

    `session`
        If the index needs to be created, this database session will be used.
        Defaults to an attempt to connect to the default SQLite database
        installed by `pokedex setup`.

    `recreate`
        If set to True, the whoosh index will be created even if it already
        exists.
    """

    # Defaults
    if not directory:
        directory = pkg_resources.resource_filename('pokedex',
                                                    'data/whoosh_index')

    if not session:
        session = connect()

    # Attempt to open or create the index
    directory_exists = os.path.exists(directory)
    if directory_exists and not recreate:
        # Already exists; should be an index!
        try:
            index = whoosh.index.open_dir(directory, indexname='MAIN')
            spell_store = whoosh.filedb.filestore.FileStorage(directory)
            speller = whoosh.spelling.SpellChecker(spell_store)
            return index, speller
        except whoosh.index.EmptyIndexError as e:
            # Apparently not a real index.  Fall out of the if and create it
            pass

    if not directory_exists:
        os.mkdir(directory)


    # Create index
    schema = whoosh.fields.Schema(
        name=whoosh.fields.ID(stored=True),
        table=whoosh.fields.STORED,
        row_id=whoosh.fields.ID(stored=True),
        language=whoosh.fields.STORED,
    )

    index = whoosh.index.create_in(directory, schema=schema, indexname='MAIN')
    writer = index.writer()

    # Index every name in all our tables of interest
    # speller_entries becomes a list of (word, score) tuples; the score is 2
    # for English names, 1.5 for Roomaji, and 1 for everything else.  I think
    # this biases the results in the direction most people expect, especially
    # when e.g. German names are very similar to English names
    speller_entries = []
    for cls in indexed_tables.values():
        q = session.query(cls)

        # Only index base Pokémon formes
        if hasattr(cls, 'forme_base_pokemon_id'):
            q = q.filter_by(forme_base_pokemon_id=None)

        for row in q.yield_per(5):
            row_key = dict(table=cls.__tablename__, row_id=unicode(row.id))

            name = row.name.lower()
            writer.add_document(name=name, **row_key)
            speller_entries.append((name, 1))

            # Pokemon also get other languages
            for foreign_name in getattr(row, 'foreign_names', []):
                moonspeak = foreign_name.name.lower()
                if name == moonspeak:
                    # Don't add the English name again as a different language;
                    # no point and it makes spell results confusing
                    continue

                writer.add_document(name=moonspeak,
                                    language=foreign_name.language.name,
                                    **row_key)
                speller_entries.append((moonspeak, 3))

                # Add Roomaji too
                if foreign_name.language.name == 'Japanese':
                    roomaji = romanize(foreign_name.name).lower()
                    writer.add_document(name=roomaji, language='Roomaji',
                                        **row_key)
                    speller_entries.append((roomaji, 8))


    writer.commit()

    # Construct and populate a spell-checker index.  Quicker to do it all
    # at once, as every call to add_* does a commit(), and those seem to be
    # expensive
    speller = whoosh.spelling.SpellChecker(index.storage)
    speller.add_scored_words(speller_entries)

    return index, speller


rx_is_number = re.compile('^\d+$')

LookupResult = namedtuple('LookupResult',
                          ['object', 'name', 'language', 'exact'])
def lookup(input, session=None, indices=None, exact_only=False):
    """Attempts to find some sort of object, given a database session and name.

    Returns a list of named (object, name, language, exact) tuples.  `object`
    is a database object, `name` is the name under which the object was found,
    `language` is the name of the language in which the name was found, and
    `exact` is True iff this was an exact match.

    This function currently ONLY does fuzzy matching if there are no exact
    matches.

    Formes are not returned; "Shaymin" will return only grass Shaymin.

    Recognizes:
    - Names: "Eevee", "Surf", "Run Away", "Payapa Berry", etc.
    - Foreign names: "Iibui", "Eivui"
    - Fuzzy names in whatever language: "Evee", "Ibui"
    - IDs: "pokemon 133", "move 192", "item 250"
    - Dex numbers: "sinnoh 55", "133", "johto 180"

    `input`
        Name of the thing to look for.

    `session`
        A database session to use for retrieving objects.  As with get_index,
        if this is not provided, a connection to the default database will be
        attempted.

    `indices`
        Tuple of index, speller as returned from `open_index()`.  Defaults to
        a call to `open_index()`.

    `exact_only`
        If True, only exact matches are returned.  If set to False (the
        default), and the provided `name` doesn't match anything exactly,
        spelling correction will be attempted.
    """

    if not session:
        session = connect()

    if indices:
        index, speller = indices
    else:
        index, speller = open_index()

    name = unicode(input).lower()
    exact = True

    # If the input provided is a number, match it as an id.  Otherwise, name
    if rx_is_number.match(input):
        query_column = 'row_id'
        exact_only = True  # don't spell-check numbers!
    else:
        # Not an integer
        query_column = 'name'

    # Look for exact name.  A Term object does an exact match, so we don't have
    # to worry about a query parser tripping on weird characters in the input
    searcher = index.searcher()
    query = whoosh.query.Term(query_column, name)
    print query
    results = searcher.search(query)

    # Look for some fuzzy matches if necessary
    if not exact_only and not results:
        exact = False
        results = []

        for suggestion in speller.suggest(name, 25):
            query = whoosh.query.Term('name', suggestion)
            results.extend(searcher.search(query))

    ### Convert results to db objects
    objects = []
    seen = {}
    for result in results:
        # Skip dupe results
        # Note!  The speller prefers English names, but the query does not.  So
        # "latias" comes over "ratiasu".  "latias" matches only the English
        # row, comes out first, and all is well.
        # However!  The speller could then return "foo" which happens to be the
        # name for two different things in different languages, and the
        # non-English one could appear preferred.  This is not very likely.
        seen_key = result['table'], result['row_id']
        if seen_key in seen:
            continue
        seen[seen_key] = True

        cls = indexed_tables[result['table']]
        obj = session.query(cls).get(result['row_id'])
        objects.append(LookupResult(object=obj,
                                    name=result['name'],
                                    language=result['language'],
                                    exact=exact))

    # Only return up to 10 matches; beyond that, something is wrong.
    # We strip out duplicate entries above, so it's remotely possible that we
    # should have more than 10 here and lost a few.  The speller returns 25 to
    # give us some padding, and should avoid that problem.  Not a big deal if
    # we lose the 25th-most-likely match anyway.
    return objects[:10]
