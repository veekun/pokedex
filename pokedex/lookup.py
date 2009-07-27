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
        table=whoosh.fields.STORED,
        row_id=whoosh.fields.STORED,
        language_id=whoosh.fields.STORED,
    )

    # Construct a straight lookup index
    index = whoosh.index.Index(store, schema=schema, create=True)
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

    # Construct and populate a spell-checker index.  Quicker to do it all
    # at once, as every call to add_* does a commit(), and those seem to be
    # expensive
    speller = whoosh.spelling.SpellChecker(index.storage)
    # WARNING: HERE BE DRAGONS
    # whoosh.spelling refuses to index things that don't look like words.
    # Unfortunately, this doesn't work so well for Pokémon (Mr. Mime,
    # Porygon-Z, etc.), and attempts to work around it lead to further
    # complications.
    # The below is copied from SpellChecker.add_scored_words without the check
    # for isalpha().  XXX get whoosh patched to make this unnecessary!
    writer = whoosh.writing.IndexWriter(speller.index())
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

    index, speller = get_index(session)

    # Look for exact name.  A Term object does an exact match, so we don't have
    # to worry about a query parser tripping on weird characters in the input
    searcher = index.searcher()
    query = whoosh.query.Term('name', name)
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
