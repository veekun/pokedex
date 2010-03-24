# encoding: utf8
from collections import namedtuple
import os, os.path
import pkg_resources
import random
import re
import shutil
import unicodedata

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

__all__ = ['PokedexLookup']


rx_is_number = re.compile('^\d+$')

LookupResult = namedtuple('LookupResult',
    ['object', 'indexed_name', 'name', 'language', 'iso3166', 'exact'])

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
            # Give Roomaji a little boost; it's most likely to be searched
            return weight * 0.95
        else:
            # Everything else can drop down the totem pole
            return weight * 0.9


class PokedexLookup(object):
    INTERMEDIATE_LOOKUP_RESULTS = 25
    MAX_LOOKUP_RESULTS = 10

    # Dictionary of table name => table class.
    # Need the table name so we can get the class from the table name after we
    # retrieve something from the index
    indexed_tables = dict(
        (cls.__tablename__, cls)
        for cls in (
            tables.Ability,
            tables.Item,
            tables.Location,
            tables.Move,
            tables.Pokemon,
            tables.Type,
        )
    )


    def __init__(self, directory=None, session=None, recreate=False):
        """Opens the whoosh index stored in the named directory.  If the index
        doesn't already exist, it will be created.

        `directory`
            Directory containing the index.  Defaults to a location within the
            `pokedex` egg directory.

        `session`
            If the index needs to be created, this database session will be
            used.  Defaults to an attempt to connect to the default SQLite
            database installed by `pokedex setup`.

        `recreate`
            If set to True, the whoosh index will be created even if it already
            exists.
        """

        # By the time this returns, self.index, self.speller, and self.session
        # must be set

        # Defaults
        if not directory:
            directory = pkg_resources.resource_filename('pokedex',
                                                        'data/whoosh-index')

        if session:
            self.session = session
        else:
            self.session = connect()

        # Attempt to open or create the index
        directory_exists = os.path.exists(directory)
        if directory_exists and not recreate:
            # Already exists; should be an index!  Bam, done.
            try:
                self.index = whoosh.index.open_dir(directory, indexname='MAIN')
                spell_store = whoosh.filedb.filestore.FileStorage(directory)
                self.speller = whoosh.spelling.SpellChecker(spell_store)
                return
            except whoosh.index.EmptyIndexError as e:
                # Apparently not a real index.  Fall out and create it
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
            iso3166=whoosh.fields.STORED,
            display_name=whoosh.fields.STORED,  # non-lowercased name
        )

        self.index = whoosh.index.create_in(directory, schema=schema,
                                            indexname='MAIN')
        writer = self.index.writer()

        # Index every name in all our tables of interest
        # speller_entries becomes a list of (word, score) tuples; the score is
        # 2 for English names, 1.5 for Roomaji, and 1 for everything else.  I
        # think this biases the results in the direction most people expect,
        # especially when e.g. German names are very similar to English names
        speller_entries = []
        for cls in self.indexed_tables.values():
            q = session.query(cls)

            for row in q.yield_per(5):
                row_key = dict(table=unicode(cls.__tablename__),
                               row_id=unicode(row.id))

                def add(name, language, iso3166, score):
                    normalized_name = self.normalize_name(name)

                    writer.add_document(
                        name=normalized_name, display_name=name,
                        language=language, iso3166=iso3166,
                        **row_key
                    )

                    speller_entries.append((normalized_name, score))


                # Add the basic English name to the index
                if cls == tables.Pokemon:
                    # Pokémon need their form name added
                    # XXX kinda kludgy
                    add(row.full_name, None, u'us', 1)

                    # If this is a default form, ALSO add the unadorned name,
                    # so 'Deoxys' alone will still do the right thing
                    if row.forme_name and not row.forme_base_pokemon_id:
                        add(row.name, None, u'us', 1)
                else:
                    add(row.name, None, u'us', 1)

                # Some things also have other languages' names
                # XXX other language form names..?
                for foreign_name in getattr(row, 'foreign_names', []):
                    moonspeak = foreign_name.name
                    if row.name == moonspeak:
                        # Don't add the English name again as a different
                        # language; no point and it makes spell results
                        # confusing
                        continue

                    add(moonspeak, foreign_name.language.name,
                                   foreign_name.language.iso3166,
                                   3)

                    # Add Roomaji too
                    if foreign_name.language.name == 'Japanese':
                        roomaji = romanize(foreign_name.name)
                        add(roomaji, u'Roomaji', u'jp', 8)

        writer.commit()

        # Construct and populate a spell-checker index.  Quicker to do it all
        # at once, as every call to add_* does a commit(), and those seem to be
        # expensive
        self.speller = whoosh.spelling.SpellChecker(self.index.storage)
        self.speller.add_scored_words(speller_entries)


    def normalize_name(self, name):
        """Strips irrelevant formatting junk from name input.

        Specifically: everything is lowercased, and accents are removed.
        """
        # http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
        # Makes sense to me.  Decompose by Unicode rules, then remove combining
        # characters, then recombine.  I'm explicitly doing it this way instead
        # of testing combining() because Korean characters apparently
        # decompose!  But the results are considered letters, not combining
        # characters, so testing for Mn works well, and combining them again
        # makes them look right.
        nkfd_form = unicodedata.normalize('NFKD', unicode(name))
        name = u"".join(c for c in nkfd_form
                        if unicodedata.category(c) != 'Mn')
        name = unicodedata.normalize('NFC', name)

        name = name.strip()
        name = name.lower()

        return name


    def _parse_table_name(self, name):
        """Takes a singular table name, table name, or table object and returns
        the table name.

        Returns None for a bogus name.
        """
        if hasattr(name, '__tablename__'):
            return getattr(name, '__tablename__')
        elif name in self.indexed_tables:
            return name
        elif name + 's' in self.indexed_tables:
            return name + 's'
        else:
            # Bogus.  Be nice and return dummy
            return None

    def _whoosh_records_to_results(self, records, exact=True):
        """Converts a list of whoosh's indexed records to LookupResult tuples
        containing database objects.
        """
        # XXX this 'exact' thing is getting kinda leaky.  would like a better
        # way to handle it, since only lookup() cares about fuzzy results
        seen = {}
        results = []
        for record in records:
            # Skip dupes
            seen_key = record['table'], record['row_id']
            if seen_key in seen:
                continue
            seen[seen_key] = True

            cls = self.indexed_tables[record['table']]
            obj = self.session.query(cls).get(record['row_id'])

            results.append(LookupResult(object=obj,
                                        indexed_name=record['name'],
                                        name=record['display_name'],
                                        language=record['language'],
                                        iso3166=record['iso3166'],
                                        exact=exact))

        return results


    def lookup(self, input, valid_types=[], exact_only=False):
        """Attempts to find some sort of object, given a name.

        Returns a list of named (object, name, language, iso3166, exact)
        tuples.  `object` is a database object, `name` is the name under which
        the object was found, `language` and `iso3166` are the name and country
        code of the language in which the name was found, and `exact` is True
        iff this was an
        exact match.

        This function currently ONLY does fuzzy matching if there are no exact
        matches.

        Formes are not returned unless requested; "Shaymin" will return only
        grass Shaymin.

        Extraneous whitespace is removed with extreme prejudice.

        Recognizes:
        - Names: "Eevee", "Surf", "Run Away", "Payapa Berry", etc.
        - Foreign names: "Iibui", "Eivui"
        - Fuzzy names in whatever language: "Evee", "Ibui"
        - IDs: "133", "192", "250"
        Also:
        - Type restrictions.  "type:psychic" will only return the type.  This
          is how to make ID lookup useful.  Multiple type specs can be entered
          with commas, as "move,item:1".  If `valid_types` are provided, any
          type prefix will be ignored.
        - Alternate formes can be specified merely like "wash rotom".

        `input`
            Name of the thing to look for.

        `valid_types`
            A list of table objects or names, e.g., `['pokemon', 'moves']`.  If
            this is provided, only results in one of the given tables will be
            returned.

        `exact_only`
            If True, only exact matches are returned.  If set to False (the
            default), and the provided `name` doesn't match anything exactly,
            spelling correction will be attempted.
        """

        name = self.normalize_name(input)
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
            return self.random_lookup(valid_types=valid_types)

        # Do different things depending what the query looks like
        # Note: Term objects do an exact match, so we don't have to worry about
        # a query parser tripping on weird characters in the input
        if '*' in name or '?' in name:
            exact_only = True
            query = whoosh.query.Wildcard(u'name', name)
        elif rx_is_number.match(name):
            # Don't spell-check numbers!
            exact_only = True
            query = whoosh.query.Term(u'row_id', name)
        else:
            # Not an integer
            query = whoosh.query.Term(u'name', name)

        ### Filter by type of object
        type_terms = []
        for valid_type in valid_types:
            table_name = self._parse_table_name(valid_type)
            if table_name:
                # Quietly ignore bogus valid_types; more likely to DTRT
                type_terms.append(whoosh.query.Term(u'table', table_name))

        if type_terms:
            query = query & whoosh.query.Or(type_terms)


        ### Actual searching
        searcher = self.index.searcher()
        # XXX is this kosher?  docs say search() takes a weighting arg, but it
        # certainly does not
        searcher.weighting = LanguageWeighting()
        results = searcher.search(query,
                                  limit=self.INTERMEDIATE_LOOKUP_RESULTS)

        # Look for some fuzzy matches if necessary
        if not exact_only and not results:
            exact = False
            results = []

            for suggestion in self.speller.suggest(
                name, self.INTERMEDIATE_LOOKUP_RESULTS):

                query = whoosh.query.Term('name', suggestion)
                results.extend(searcher.search(query))

        ### Convert results to db objects
        objects = self._whoosh_records_to_results(results, exact=exact)

        # Only return up to 10 matches; beyond that, something is wrong.  We
        # strip out duplicate entries above, so it's remotely possible that we
        # should have more than 10 here and lost a few.  The speller returns 25
        # to give us some padding, and should avoid that problem.  Not a big
        # deal if we lose the 25th-most-likely match anyway.
        return objects[:self.MAX_LOOKUP_RESULTS]


    def random_lookup(self, valid_types=[]):
        """Returns a random lookup result from one of the provided
        `valid_types`.
        """

        tables = []
        for valid_type in valid_types:
            table_name = self._parse_table_name(valid_type)
            if table_name:
                tables.append(self.indexed_tables[table_name])

        if not tables:
            # n.b.: It's possible we got a list of valid_types and none of them
            # were valid, but this function is guaranteed to return
            # *something*, so it politely selects from the entire index isntead
            tables = self.indexed_tables.values()

        # Rather than create an array of many hundred items and pick randomly
        # from it, just pick a number up to the total number of potential
        # items, then pick randomly from that, and partition the whole range
        # into chunks.  This also avoids the slight problem that the index
        # contains more rows (for languages) for some items than others.
        # XXX ought to cache this (in the index?) if possible
        total = 0
        partitions = []
        for table in tables:
            count = self.session.query(table).count()
            total += count
            partitions.append((table, count))

        n = random.randint(1, total)
        while n > partitions[0][1]:
            n -= partitions[0][1]
            partitions.pop(0)

        return self.lookup(unicode(n), valid_types=[ partitions[0][0] ])

    def prefix_lookup(self, prefix):
        """Returns terms starting with the given exact prefix.

        No special magic is currently done with the name; type prefixes are not
        recognized.
        """

        query = whoosh.query.Prefix(u'name', self.normalize_name(prefix))

        searcher = self.index.searcher()
        searcher.weighting = LanguageWeighting()
        results = searcher.search(query)  # XXX , limit=self.MAX_LOOKUP_RESULTS)

        return self._whoosh_records_to_results(results)
