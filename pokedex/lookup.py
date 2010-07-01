# encoding: utf8
import os, os.path
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

from pokedex.util import namedtuple

from pokedex.db import connect
import pokedex.db.tables as tables
from pokedex.roomaji import romanize
from pokedex.defaults import get_default_index_dir

__all__ = ['PokedexLookup']


rx_is_number = re.compile('^\d+$')

LookupResult = namedtuple('LookupResult',
    ['object', 'indexed_name', 'name', 'language', 'iso3166', 'exact'])

class UninitializedIndex(object):
    class UninitializedIndexError(Exception):
        pass

    def __nonzero__(self):
        """Dummy object should identify itself as False."""
        return False

    def __bool__(self):
        """Python 3000 version of the above.  Future-proofing rules!"""
        return False

    def __getattr__(self, *args, **kwargs):
        raise self.UninitializedIndexError(
            "The lookup index does not exist.  Please use `pokedex setup` "
            "or lookup.rebuild_index() to create it."
        )

class LanguageWeighting(whoosh.scoring.Weighting):
    """A scoring class that forces otherwise-equal English results to come
    before foreign results.
    """

    def __init__(self, extra_weights={}, *args, **kwargs):
        """`extra_weights` may be a dictionary of weights which will be
        factored in.

        Intended for use with spelling corrections, which come along with their
        own weightings.
        """
        self.extra_weights = extra_weights
        super(LanguageWeighting, self).__init__(*args, **kwargs)

    def score(self, searcher, fieldnum, text, docnum, weight, QTF=1):
        doc = searcher.stored_fields(docnum)

        # Apply extra weight
        weight = weight * self.extra_weights.get(text, 1.0)

        if doc['language'] == None:
            # English (well, "default"); leave it at 1
            return weight
        elif doc['language'] == u'Roomaji':
            # Give Roomaji a little boost; it's most likely to be searched
            return weight * 0.9
        else:
            # Everything else can drop down the totem pole
            return weight * 0.8


class PokedexLookup(object):
    INTERMEDIATE_LOOKUP_RESULTS = 25
    MAX_LOOKUP_RESULTS = 10

    # The speller only checks how much the input matches a word; there can be
    # all manner of extra unmatched junk, and it won't affect the weighting.
    # To compensate, greatly boost the weighting of matches at the beginning
    # and end, so nearly-full-word-matches are much better
    SPELLER_OPTIONS = dict(booststart=10.0, boostend=9.0)

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
            tables.Nature,
            tables.Pokemon,
            tables.Type,
        )
    )


    def __init__(self, directory=None, session=None):
        """Opens the whoosh index stored in the named directory.  If the index
        doesn't already exist, it will be created.

        `directory`
            Directory containing the index.  Defaults to a location within the
            `pokedex` egg directory.

        `session`
            Used for creating the index and retrieving objects.  Defaults to an
            attempt to connect to the default SQLite database installed by
            `pokedex setup`.
        """

        # By the time this returns, self.index, self.speller, and self.session
        # must be set

        # If a directory was not given, use the default
        if directory is None:
            directory = get_default_index_dir()

        self.directory = directory

        if session:
            self.session = session
        else:
            self.session = connect()

        # Attempt to open or create the index
        if not os.path.exists(directory) or not os.listdir(directory):
            # Directory doesn't exist OR is empty; caller needs to use
            # rebuild_index before doing anything.  Provide a dummy object that
            # complains when used
            self.index = UninitializedIndex()
            self.speller = UninitializedIndex()
            return

        # Otherwise, already exists; should be an index!  Bam, done.
        # Note that this will explode if the directory exists but doesn't
        # contain an index; that's a feature
        try:
            self.index = whoosh.index.open_dir(directory, indexname='MAIN')
        except whoosh.index.EmptyIndexError:
            raise IOError(
                "The index directory already contains files.  "
                "Please use a dedicated directory for the lookup index."
            )

        # Create speller, and done
        spell_store = whoosh.filedb.filestore.FileStorage(directory)
        self.speller = whoosh.spelling.SpellChecker(spell_store,
            **self.SPELLER_OPTIONS)


    def rebuild_index(self):
        """Creates the index from scratch."""

        schema = whoosh.fields.Schema(
            name=whoosh.fields.ID(stored=True),
            table=whoosh.fields.ID(stored=True),
            row_id=whoosh.fields.ID(stored=True),
            language=whoosh.fields.STORED,
            iso3166=whoosh.fields.STORED,
            display_name=whoosh.fields.STORED,  # non-lowercased name
        )

        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

        self.index = whoosh.index.create_in(self.directory, schema=schema,
                                                            indexname='MAIN')
        writer = self.index.writer()

        # Index every name in all our tables of interest
        speller_entries = set()
        for cls in self.indexed_tables.values():
            q = self.session.query(cls)

            for row in q.yield_per(5):
                row_key = dict(table=unicode(cls.__tablename__),
                               row_id=unicode(row.id))

                def add(name, language, iso3166):
                    normalized_name = self.normalize_name(name)

                    writer.add_document(
                        name=normalized_name, display_name=name,
                        language=language, iso3166=iso3166,
                        **row_key
                    )

                    speller_entries.add(normalized_name)


                # Add the basic English name to the index
                if cls == tables.Pokemon:
                    # Pokémon need their form name added
                    # XXX kinda kludgy
                    add(row.full_name, None, u'us')

                    # If this is a default form, ALSO add the unadorned name,
                    # so 'Deoxys' alone will still do the right thing
                    if row.forme_name and not row.forme_base_pokemon_id:
                        add(row.name, None, u'us')
                else:
                    add(row.name, None, u'us')

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
                                   foreign_name.language.iso3166)

                    # Add Roomaji too
                    if foreign_name.language.name == 'Japanese':
                        roomaji = romanize(foreign_name.name)
                        add(roomaji, u'Roomaji', u'jp')

        writer.commit()

        # Construct and populate a spell-checker index.  Quicker to do it all
        # at once, as every call to add_* does a commit(), and those seem to be
        # expensive
        self.speller = whoosh.spelling.SpellChecker(self.index.storage, mingram=2,
            **self.SPELLER_OPTIONS)
        self.speller.add_words(speller_entries)


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


    def _apply_valid_types(self, name, valid_types):
        """Combines the enforced `valid_types` with any from the search string
        itself and updates the query.

        For example, a name of 'a,b:foo' and valid_types of b,c will search for
        only `b`s named "foo".

        Returns `(name, merged_valid_types, term)`, where `name` has had any type
        prefix stripped, `merged_valid_types` combines the original
        `valid_types` with the type prefix, and `term` is a query term for
        limited to just the allowed types.  If there are no type restrictions
        at all, `term` will be None.
        """

        # Remove any type prefix (pokemon:133) first
        user_valid_types = []
        if ':' in name:
            prefix_chunk, name = name.split(':', 1)
            name = name.strip()

            prefixes = prefix_chunk.split(',')
            user_valid_types = [_.strip() for _ in prefixes]

        # Merge the valid types together.  Only types that appear in BOTH lists
        # may be used.
        # As a special case, if the user asked for types that are explicitly
        # forbidden, completely ignore what the user requested
        combined_valid_types = []
        if user_valid_types and valid_types:
            combined_valid_types = list(
                set(user_valid_types) & set(combined_valid_types)
            )

            if not combined_valid_types:
                # No overlap!  Just use the enforced ones
                combined_valid_types = valid_types
        else:
            # One list or the other was blank, so just use the one that isn't
            combined_valid_types = valid_types + user_valid_types

        if not combined_valid_types:
            # No restrictions
            return name, [], None

        # Construct the term
        type_terms = []
        final_valid_types = []
        for valid_type in combined_valid_types:
            table_name = self._parse_table_name(valid_type)

            # Quietly ignore bogus valid_types; more likely to DTRT
            if table_name:
                final_valid_types.append(valid_type)
                type_terms.append(whoosh.query.Term(u'table', table_name))

        return name, final_valid_types, whoosh.query.Or(type_terms)


    def _parse_table_name(self, name):
        """Takes a singular table name, table name, or table object and returns
        the table name.

        Returns None for a bogus name.
        """
        # Table object
        if hasattr(name, '__tablename__'):
            return getattr(name, '__tablename__')

        # Table name
        for table in self.indexed_tables.values():
            if name in (table.__tablename__, table.__singlename__):
                return table.__tablename__

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

        # Pop off any type prefix and merge with valid_types
        name, merged_valid_types, type_term = \
            self._apply_valid_types(name, valid_types)

        # Random lookup
        if name == 'random':
            return self.random_lookup(valid_types=merged_valid_types)

        # Do different things depending what the query looks like
        # Note: Term objects do an exact match, so we don't have to worry about
        # a query parser tripping on weird characters in the input
        try:
            # Let Python try to convert to a number, so 0xff works
            name_as_number = int(name, base=0)
        except ValueError:
            # Oh well
            name_as_number = None

        if '*' in name or '?' in name:
            exact_only = True
            query = whoosh.query.Wildcard(u'name', name)
        elif name_as_number is not None:
            # Don't spell-check numbers!
            exact_only = True
            query = whoosh.query.Term(u'row_id', unicode(name_as_number))
        else:
            # Not an integer
            query = whoosh.query.Term(u'name', name)

        if type_term:
            query = query & type_term


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

            fuzzy_query_parts = []
            fuzzy_weights = {}
            min_weight = [None]
            for suggestion, _, weight in self.speller.suggestions_and_scores(name):
                # Only allow the top 50% of scores; otherwise there will always
                # be a lot of trailing junk
                if min_weight[0] is None:
                    min_weight[0] = weight * 0.5
                elif weight < min_weight[0]:
                    break

                fuzzy_query_parts.append(whoosh.query.Term('name', suggestion))
                fuzzy_weights[suggestion] = weight

            if not fuzzy_query_parts:
                # Nothing at all; don't try querying
                return []

            fuzzy_query = whoosh.query.Or(fuzzy_query_parts)
            if type_term:
                fuzzy_query = fuzzy_query & type_term

            searcher.weighting = LanguageWeighting(extra_weights=fuzzy_weights)
            results = searcher.search(fuzzy_query)

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

    def prefix_lookup(self, prefix, valid_types=[]):
        """Returns terms starting with the given exact prefix.

        Type prefixes are recognized, but no other name munging is done.
        """

        # Pop off any type prefix and merge with valid_types
        prefix, merged_valid_types, type_term = \
            self._apply_valid_types(prefix, valid_types)

        query = whoosh.query.Prefix(u'name', self.normalize_name(prefix))

        if type_term:
            query = query & type_term

        searcher = self.index.searcher()
        searcher.weighting = LanguageWeighting()
        results = searcher.search(query)  # XXX , limit=self.MAX_LOOKUP_RESULTS)

        return self._whoosh_records_to_results(results)
