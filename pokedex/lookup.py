# encoding: utf8
from collections import namedtuple
import os, os.path
import pkg_resources
import random
import re
import shutil

from sqlalchemy.sql import func
import whoosh
import whoosh.filedb.filestore
import whoosh.filedb.fileindex
import whoosh.index
from whoosh.qparser import QueryParser
import whoosh.scoring
import whoosh.spelling

from pokedex.db import connect
import pokedex.db.tables as tables
from pokedex.roomaji import romanize

__all__ = ['open_index', 'lookup', 'random_lookup']

INTERMEDIATE_LOOKUP_RESULTS = 25
MAX_LOOKUP_RESULTS = 10

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
                                                    'data/whoosh-index')

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

    # Delete and start over if we're going to bail anyway.
    if directory_exists and recreate:
        # Be safe and only delete if it looks like a whoosh index, i.e.,
        # everything starts with _
        if all(f[0] == '_' for f in os.listdir(directory)):
            shutil.rmtree(directory)
            directory_exists = False

    if not directory_exists:
        os.mkdir(directory)


    ### Create index
    schema = whoosh.fields.Schema(
        name=whoosh.fields.ID(stored=True),
        table=whoosh.fields.ID(stored=True),
        row_id=whoosh.fields.ID(stored=True),
        language=whoosh.fields.STORED,
        display_name=whoosh.fields.STORED,  # non-lowercased name
        forme_name=whoosh.fields.ID,
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

        for row in q.yield_per(5):
            # XXX need to give forme_name a dummy value because I can't search
            # for explicitly empty fields.  boo.
            row_key = dict(table=unicode(cls.__tablename__),
                           row_id=unicode(row.id),
                           forme_name=u'XXX')

            def add(name, language, score):
                writer.add_document(name=name.lower(), display_name=name,
                                    language=language,
                                    **row_key)
                speller_entries.append((name.lower(), score))

            # If this is a form, mark it as such
            if getattr(row, 'forme_base_pokemon_id', None):
                row_key['forme_name'] = row.forme_name

            name = row.name
            add(name, None, 1)

            # Pokemon also get other languages
            for foreign_name in getattr(row, 'foreign_names', []):
                moonspeak = foreign_name.name
                if name == moonspeak:
                    # Don't add the English name again as a different language;
                    # no point and it makes spell results confusing
                    continue

                add(moonspeak, foreign_name.language.name, 3)

                # Add Roomaji too
                if foreign_name.language.name == 'Japanese':
                    roomaji = romanize(foreign_name.name)
                    add(roomaji, u'Roomaji', 8)

    writer.commit()

    # Construct and populate a spell-checker index.  Quicker to do it all
    # at once, as every call to add_* does a commit(), and those seem to be
    # expensive
    speller = whoosh.spelling.SpellChecker(index.storage)
    speller.add_scored_words(speller_entries)

    return index, speller


class LanguageWeighting(whoosh.scoring.Weighting):
    """A scoring class that forces otherwise-equal English results to come
    before foreign results.
    """

    def score(self, searcher, fieldnum, text, docnum, weight, QTF=1):
        doc = searcher.stored_fields(docnum)
        if doc['language'] == None:
            # English (well, "default"); leave it at 1
            return weight
        elif doc['language'] == u'Roomaji':
            # Give Roomaji a bit of a boost, as it's most likely to be searched
            return weight * 0.95
        else:
            # Everything else can drop down the totem pole
            return weight * 0.9

rx_is_number = re.compile('^\d+$')

LookupResult = namedtuple('LookupResult',
                          ['object', 'name', 'language', 'exact'])

def _parse_table_name(name):
    """Takes a singular table name, table name, or table object and returns the
    table name.

    Returns None for a bogus name.
    """
    if hasattr(name, '__tablename__'):
        return getattr(name, '__tablename__')
    elif name in indexed_tables:
        return name
    elif name + 's' in indexed_tables:
        return name + 's'
    else:
        # Bogus.  Be nice and return dummy
        return None

def _whoosh_records_to_results(records, session, exact=True):
    """Converts a list of whoosh's indexed records to LookupResult tuples
    containing database objects.
    """
    # XXX this 'exact' thing is getting kinda leaky.  would like a better way
    # to handle it, since only lookup() cares about fuzzy results
    seen = {}
    results = []
    for record in records:
        # Skip dupes
        seen_key = record['table'], record['row_id']
        if seen_key in seen:
            continue
        seen[seen_key] = True

        cls = indexed_tables[record['table']]
        obj = session.query(cls).get(record['row_id'])

        results.append(LookupResult(object=obj,
                                    name=record['display_name'],
                                    language=record['language'],
                                    exact=exact))

    return results


def lookup(input, valid_types=[], session=None, indices=None, exact_only=False):
    """Attempts to find some sort of object, given a database session and name.

    Returns a list of named (object, name, language, exact) tuples.  `object`
    is a database object, `name` is the name under which the object was found,
    `language` is the name of the language in which the name was found, and
    `exact` is True iff this was an exact match.

    This function currently ONLY does fuzzy matching if there are no exact
    matches.

    Formes are not returned unless requested; "Shaymin" will return only grass
    Shaymin.

    Extraneous whitespace is removed with extreme prejudice.

    Recognizes:
    - Names: "Eevee", "Surf", "Run Away", "Payapa Berry", etc.
    - Foreign names: "Iibui", "Eivui"
    - Fuzzy names in whatever language: "Evee", "Ibui"
    - IDs: "133", "192", "250"
    Also:
    - Type restrictions.  "type:psychic" will only return the type.  This is
      how to make ID lookup useful.  Multiple type specs can be entered with
      commas, as "move,item:1".  If `valid_types` are provided, any type prefix
      will be ignored.
    - Alternate formes can be specified merely like "wash rotom".

    `input`
        Name of the thing to look for.

    `valid_types`
        A list of table objects or names, e.g., `['pokemon', 'moves']`.  If
        this is provided, only results in one of the given tables will be
        returned.

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

    name = unicode(input).strip().lower()
    exact = True
    form = None

    # Remove any type prefix (pokemon:133) before constructing a query
    if ':' in name:
        prefix_chunk, name = name.split(':', 1)
        name = name.strip()

        if not valid_types:
            # Only use types from the query string if none were explicitly
            # provided
            prefixes = prefix_chunk.split(',')
            valid_types = [_.strip() for _ in prefixes]

    # Random lookup
    if name == 'random':
        return random_lookup(indices=(index, speller),
                             session=session,
                             valid_types=valid_types)

    # Do different things depending what the query looks like
    # Note: Term objects do an exact match, so we don't have to worry about a
    # query parser tripping on weird characters in the input
    if '*' in name or '?' in name:
        exact_only = True
        query = whoosh.query.Wildcard(u'name', name)
    elif rx_is_number.match(name):
        # Don't spell-check numbers!
        exact_only = True
        query = whoosh.query.Term(u'row_id', name)
    else:
        # Not an integer
        query = whoosh.query.Term(u'name', name) \
              & whoosh.query.Term(u'forme_name', u'XXX')

        # If there's a space in the input, this might be a form
        if ' ' in name:
            form, formless_name = name.split(' ', 1)
            form_query = whoosh.query.Term(u'name', formless_name) \
                       & whoosh.query.Term(u'forme_name', form)
            query = query | form_query

    ### Filter by type of object
    type_terms = []
    for valid_type in valid_types:
        table_name = _parse_table_name(valid_type)
        type_terms.append(whoosh.query.Term(u'table', table_name))

    if type_terms:
        query = query & whoosh.query.Or(type_terms)


    ### Actual searching
    searcher = index.searcher()
    searcher.weighting = LanguageWeighting()  # XXX kosher?  docs say search()
                                              # takes a weighting kw but it
                                              # certainly does not
    results = searcher.search(query, limit=INTERMEDIATE_LOOKUP_RESULTS)

    # Look for some fuzzy matches if necessary
    if not exact_only and not results:
        exact = False
        results = []

        for suggestion in speller.suggest(name, INTERMEDIATE_LOOKUP_RESULTS):
            query = whoosh.query.Term('name', suggestion)
            results.extend(searcher.search(query))

    ### Convert results to db objects
    objects = _whoosh_records_to_results(results, session, exact=exact)

    # Only return up to 10 matches; beyond that, something is wrong.
    # We strip out duplicate entries above, so it's remotely possible that we
    # should have more than 10 here and lost a few.  The speller returns 25 to
    # give us some padding, and should avoid that problem.  Not a big deal if
    # we lose the 25th-most-likely match anyway.
    return objects[:MAX_LOOKUP_RESULTS]


def random_lookup(valid_types=[], session=None, indices=None):
    """Takes similar arguments as `lookup()`, but returns a random lookup
    result from one of the provided `valid_types`.
    """

    tables = []
    for valid_type in valid_types:
        table_name = _parse_table_name(valid_type)
        if table_name:
            tables.append(indexed_tables[table_name])

    if not tables:
        tables = indexed_tables.values()

    # Rather than create an array of many hundred items and pick randomly from
    # it, just pick a number up to the total number of potential items, then
    # pick randomly from that, and partition the whole range into chunks
    total = 0
    partitions = []
    for table in tables:
        count = session.query(table).count()
        total += count
        partitions.append((table, count))

    n = random.randint(1, total)
    while n > partitions[0][1]:
        n -= partitions[0][1]
        partitions.pop(0)

    return lookup(unicode(n), valid_types=[ partitions[0][0] ],
                  indices=indices, session=session)

def prefix_lookup(prefix, session=None, indices=None):
    """Returns terms starting with the given exact prefix.

    No special magic is currently done with the name; type prefixes are not
    recognized.

    `session` and `indices` are treated as with `lookup()`.
    """

    if not session:
        session = connect()

    if indices:
        index, speller = indices
    else:
        index, speller = open_index()

    query = whoosh.query.Prefix(u'name', prefix.lower())

    searcher = index.searcher()
    searcher.weighting = LanguageWeighting()
    results = searcher.search(query)  # XXX , limit=MAX_LOOKUP_RESULTS)

    return _whoosh_records_to_results(results, session)
