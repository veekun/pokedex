# encoding: utf8
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

# Dictionary of extra keys to file types of objects under, e.g. Pokémon can
# also be looked up purely by number
extra_keys = {
    tables.Move: [
        lambda row: u"move %d" % row.id,
    ],
    tables.Pokemon: [
        lambda row: unicode(row.id),
    ],
}

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
            index = whoosh.index.open_dir(directory, indexname='pokedex')
            speller = whoosh.index.open_dir(directory, indexname='spelling')
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
        row_id=whoosh.fields.STORED,
        language=whoosh.fields.STORED,

        # Whoosh 0.2 explodes when using a file-stored schema with no TEXT
        # columns.  Appease it
        dummy=whoosh.fields.TEXT,
    )

    index = whoosh.index.create_in(directory, schema=schema,
                                              indexname='pokedex')
    writer = index.writer()

    # Index every name in all our tables of interest
    speller_entries = []
    for cls in indexed_tables.values():
        q = session.query(cls)

        # Only index base Pokémon formes
        if hasattr(cls, 'forme_base_pokemon_id'):
            q = q.filter_by(forme_base_pokemon_id=None)

        for row in q.yield_per(5):
            row_key = dict(table=cls.__tablename__, row_id=row.id)

            # Spelling index only indexes strings of letters, alas, so we
            # reduce every name to this to make the index work.  However, exact
            # matches are not returned, so e.g. 'nidoran' would neither match
            # exactly nor fuzzy-match.  Solution: add the spelling-munged name
            # as a regular index row too.
            name = row.name.lower()
            writer.add_document(name=name, **row_key)

            speller_entries.append(name)

            for extra_key_func in extra_keys.get(cls, []):
                extra_key = extra_key_func(row)
                writer.add_document(name=extra_key, **row_key)

    writer.commit()

    # XXX GIHWEGREHKG
    old__schema = whoosh.spelling.SpellChecker._schema
    def new__schema(self):
        schema = old__schema(self)
        schema.add('dummy', whoosh.fields.TEXT)
        return schema
    whoosh.spelling.SpellChecker._schema = new__schema

    # Construct and populate a spell-checker index.  Quicker to do it all
    # at once, as every call to add_* does a commit(), and those seem to be
    # expensive
    speller = whoosh.spelling.SpellChecker(index.storage, indexname='spelling')
    # WARNING: HERE BE DRAGONS
    # whoosh.spelling refuses to index things that don't look like words.
    # Unfortunately, this doesn't work so well for Pokémon (Mr. Mime,
    # Porygon-Z, etc.), and attempts to work around it lead to further
    # complications.
    # The below is copied from SpellChecker.add_scored_words without the check
    # for isalpha().  XXX get whoosh patched to make this unnecessary!
    writer = speller.index(create=True).writer()
    for word in speller_entries:
        fields = {"word": word, "score": 1}
        for size in xrange(speller.mingram, speller.maxgram + 1):
            nga = whoosh.analysis.NgramAnalyzer(size)
            gramlist = [t.text for t in nga(word)]
            if len(gramlist) > 0:
                fields["start%s" % size] = gramlist[0]
                fields["end%s" % size] = gramlist[-1]
                fields["gram%s" % size] = " ".join(gramlist)
        writer.add_document(**fields)
    writer.commit()
    # end copy-pasta

    return index, speller


def lookup(name, session=None, exact_only=False):
    """Attempts to find some sort of object, given a database session and name.

    Returns (objects, exact) where `objects` is a list of database objects, and
    `exact` is True iff the given name matched the returned objects exactly.

    This function ONLY does fuzzy matching if there are no exact matches.

    Formes are not returned; "Shaymin" will return only grass Shaymin.

    Currently recognizes:
    - Pokémon names: "Eevee"

    `name`
        Name of the thing to look for.

    `session`
        A database session to use for retrieving objects.  As with get_index,
        if this is not provided, a connection to the default database will be
        attempted.

    `exact_only`
        If True, only exact matches are returned.  If set to False (the
        default), and the provided `name` doesn't match anything exactly,
        spelling correction will be attempted.
    """

    if not session:
        session = connect()

    index, speller = open_index()

    exact = True

    # Look for exact name.  A Term object does an exact match, so we don't have
    # to worry about a query parser tripping on weird characters in the input
    searcher = index.searcher()
    query = whoosh.query.Term('name', name.lower())
    results = searcher.search(query)

    if not exact_only:
        # Look for some fuzzy matches
        if not results:
            exact = False
            results = []

            for suggestion in speller.suggest(name, 3):
                query = whoosh.query.Term('name', suggestion)
                results.extend(searcher.search(query))

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
