#! /usr/bin/env python
u"""General handling of translations

The general idea is to get messages from somewhere: the source pokedex CSVs,
or the translation CSVs, etc., then merge them together in some way, and shove
them into the database.

If a message is translated, it has a source string attached to it, with the
original English version. Or at least it has a CRC of the original.
When that doesn't match, it means the English string changed and the
translation has to be updated.
Also this is why we can't dump translations from the database: there's no
original string info.

Some complications:

Flavor text is so repetitive that we take strings from all the version,
separate the unique ones by blank lines, let translators work on that, and then
put it in flavor_summary tables.

Routes names and other repetitive numeric things are replaced by e.g.
"Route {num}" so translators only have to work on each set once.

"""

import binascii
import csv
import heapq
import itertools
import os
import re
import sys
from collections import defaultdict

from pokedex.db import tables
from pokedex.defaults import get_default_csv_dir

default_source_lang = 'en'

# Top-level classes we want translations for: in order, and by name
# These are all mapped_classes that have translatable texts and aren't summarized
toplevel_classes = []
toplevel_class_by_name = {}

# summary_map[pokemon_prose]['flavor_summary'] == PokemonFlavorTexts
summary_map = {}

# translation_class_by_column[class_name, column_name] == translation_class
translation_class_by_column = {}

for cls in tables.mapped_classes:
    try:
        summary_class, col = cls.summary_column
    except AttributeError:
        if cls.translation_classes:
            toplevel_classes.append(cls)
            toplevel_class_by_name[cls.__name__] = cls
            for translation_class in cls.translation_classes:
                for column in translation_class.__table__.c:
                    translation_class_by_column[cls, column.name] = translation_class
    else:
        summary_map.setdefault(summary_class, {})[col] = cls

number_re = re.compile("[0-9]+")

def crc(string):
    """Return a hash to we use in translation CSV files"""
    return "%08x" % (binascii.crc32(string.encode('utf-8')) & 0xffffffff)
    # Two special values are also used in source_crc:
    # UNKNOWN: no source string was available
    # OFFICIAL: an official string from the main database

class Message(object):
    """Holds all info about a translatable or translated string

    cls: Name of the mapped class the message belongs to
    id: The id of the thing the message belongs to
    colname: name of the database column
    strings: A list of strings in the message, usualy of length 1.

    Optional attributes (None if not set):
    colsize: Max length of the database column
    source: The string this was translated from
    number_replacement: True if this is a translation with {num} placeholders
    pot: Name of the pot the message goes to (see pot_for_column)
    source_crc: CRC of the source
    origin: Some indication of where the string came from (CSV, PO, ...)
    fuzzy: True for fuzzy translations
    language_id: ID of the language
    official: True if this is a known-good translation
    """
    __slots__ = 'cls id colname strings colsize source number_replacement pot source_crc origin fuzzy language_id official'.split()
    def __init__(self, cls, id, colname, string,
            colsize=None, source=None, number_replacement=None, pot=None,
            source_crc=None, origin=None, fuzzy=None, language_id=None,
            official=None,
        ):
        self.cls = cls
        self.id = id
        self.colname = colname
        self.strings = [string]
        self.colsize = colsize
        self.source = source
        self.number_replacement = number_replacement
        self.pot = pot
        self.source_crc = source_crc
        if source and not source_crc:
             self.source_crc = crc(source)
        self.origin = origin
        self.fuzzy = fuzzy
        self.language_id = language_id
        self.official = official

    def merge(self, other):
        """Merge two messages, as required for flavor text summarizing
        """
        assert self.merge_key == other.merge_key
        for string in other.strings:
            if string not in self.strings:
                self.strings.append(string)
        self.colsize = self.colsize or other.colsize
        self.pot = self.pot or other.pot
        self.source = None
        self.source_crc = None
        self.number_replacement = None

    @property
    def string(self):
        return '\n\n'.join(self.strings)

    @property
    def merge_key(self):
        return self.cls, self.id, self.colname

    @property
    def sort_key(self):
        return self.merge_key, self.language_id, self.fuzzy

    @property
    def eq_key(self):
        return self.sort_key, self.strings

    def __eq__(self, other): return self.eq_key == other.eq_key
    def __ne__(self, other): return self.eq_key != other.eq_key
    def __gt__(self, other): return self.sort_key > other.sort_key
    def __lt__(self, other): return self.sort_key < other.sort_key
    def __ge__(self, other): return self.sort_key >= other.sort_key
    def __le__(self, other): return self.sort_key <= other.sort_key

    def __unicode__(self):
        string = '"%s"' % self.string
        if len(string) > 20:
            string = string[:15] + u'"...'
        template = u'<Message from {self.origin} for {self.cls}.{self.colname}:{self.id} -- {string}>'
        return template.format(self=self, string=string)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __repr__(self):
        return unicode(self).encode('utf-8')

class Translations(object):
    """Data and opertaions specific to a location on disk (and a source language)
    """
    def __init__(self, source_lang=default_source_lang, csv_directory=None, translation_directory=None):
        if csv_directory is None:
            csv_directory = get_default_csv_dir()

        if translation_directory is None:
            translation_directory = os.path.join(csv_directory, 'translations')

        self.source_lang = default_source_lang
        self.csv_directory = csv_directory
        self.translation_directory = translation_directory

        self.language_ids = {}
        self.language_identifiers = {}
        self.official_langs = []
        for row in self.reader_for_class(tables.Language, reader_class=csv.DictReader):
            self.language_ids[row['identifier']] = int(row['id'])
            self.language_identifiers[int(row['id'])] = row['identifier']
            if row['official'] and int(row['official']):
                self.official_langs.append(row['identifier'])

        self.source_lang_id = self.language_ids[self.source_lang]

    @classmethod
    def from_parsed_options(cls, options):
        return cls(options.source_lang, options.directory)

    @property
    def source(self):
        """All source (i.e. English) messages
        """
        return self.official_messages(self.source_lang)

    def official_messages(self, lang):
        """All official messages (i.e. from main database) for the given lang
        """
        # Cached as tuples, since they're used pretty often
        lang_id = self.language_ids[lang]
        try:
            return self._sources[lang_id]
        except AttributeError:
            self._sources = {}
            for message in self.yield_source_messages():
                self._sources.setdefault(message.language_id, []).append(message)
            self._sources = dict((k, tuple(merge_adjacent(v))) for k, v in self._sources.items())
            return self.official_messages(lang)
        except KeyError:
            # Looks like there are no messages in the DB for this language
            # This should only happen for non-official languages
            assert lang not in self.official_langs
            return ()

    def write_translations(self, lang, *streams):
        """Write a translation CSV containing messages from streams.

        Streams should be ordered by priority, from highest to lowest.

        Any official translations (from the main database) are added automatically.
        """
        writer = self.writer_for_lang(lang)

        writer.writerow('language_id table id column source_crc string'.split())

        messages = merge_translations(self.source, self.official_messages(lang), *streams)

        warnings = {}
        for source, sourcehash, string, exact in messages:
            if string and sourcehash != 'OFFICIAL':
                utf8len = len(string.encode('utf-8'))
                if source.colsize and utf8len > source.colsize:
                    key = source.cls, source.colname
                    warnings[key] = max(warnings.get(key, (0,)), (utf8len, source, string))
                else:
                    writer.writerow((
                            self.language_ids[lang],
                            source.cls,
                            source.id,
                            source.colname,
                            sourcehash,
                            string.encode('utf-8'),
                        ))
        for utf8len, source, string in warnings.values():
            template = u'Error: {size}B value for {colsize}B column! {key[0]}.{key[2]}:{key[1]}: {string}'
            warning = template.format(
                    key=source.merge_key,
                    string=string,
                    size=utf8len,
                    colsize=source.colsize,
                )
            if len(warning) > 79:
                warning = warning[:76] + u'...'
            print warning.encode('utf-8')

    def reader_for_class(self, cls, reader_class=csv.reader):
        tablename = cls.__table__.name
        csvpath = os.path.join(self.csv_directory, tablename + '.csv')
        return reader_class(open(csvpath, 'rb'), lineterminator='\n')

    def writer_for_lang(self, lang):
        csvpath = os.path.join(self.translation_directory, '%s.csv' % lang)
        return csv.writer(open(csvpath, 'wb'), lineterminator='\n')

    def yield_source_messages(self, language_id=None):
        """Yield all messages from source CSV files

        Messages from all languages are returned. The messages are not ordered
        properly, but splitting the stream by language (and filtering results
        by merge_adjacent) will produce proper streams.
        """
        if language_id is None:
            language_id = self.source_lang_id

        for cls in sorted(toplevel_classes, key=lambda c: c.__name__):
            streams = []
            for translation_class in cls.translation_classes:
                streams.append(yield_source_csv_messages(
                        translation_class,
                        cls,
                        self.reader_for_class(translation_class),
                    ))
                try:
                    colmap = summary_map[translation_class]
                except KeyError:
                    pass
                else:
                    for colname, summary_class in colmap.items():
                        column = translation_class.__table__.c[colname]
                        streams.append(yield_source_csv_messages(
                                summary_class,
                                cls,
                                self.reader_for_class(summary_class),
                                force_column=column,
                            ))
            for message in Merge(*streams):
                yield message

    def yield_target_messages(self, lang):
        """Yield messages from the data/csv/translations/<lang>.csv file
        """
        path = os.path.join(self.csv_directory, 'translations', '%s.csv' % lang)
        try:
            file = open(path, 'rb')
        except IOError:
            return ()
        return yield_translation_csv_messages(file)

    def yield_all_translations(self):
        stream = Merge()
        for lang in self.language_identifiers.values():
            stream.add_iterator(self.yield_target_messages(lang))
        return (message for message in stream if not message.official)

    def get_load_data(self, langs=None):
        """Yield (translation_class, data for INSERT) pairs for loading into the DB

        langs is either a list of language identifiers or None
        """
        if langs is None:
            langs = self.language_identifiers.values()
        stream = Merge()
        for lang in self.language_identifiers.values():
            stream.add_iterator(self.yield_target_messages(lang))
        stream = (message for message in stream if not message.official)
        count = 0
        class GroupDict(dict):
            """Dict to automatically set the foreign_id and local_language_id for new items
            """
            def __missing__(self, key):
                # depends on `cls` from outside scope
                id, language_id = key
                data = self[key] = defaultdict(lambda: None)
                column_names = (c.name for c in translation_class.__table__.columns)
                data.update(dict.fromkeys(column_names))
                data.update({
                        '%s_id' % cls.__singlename__: id,
                        'local_language_id': language_id,
                    })
                return data
        # Nested dict:
        # translation_class -> (lang, id) -> column -> value
        everything = defaultdict(GroupDict)
        # Group by object so we always have all of the messages for one DB row
        for (cls_name, id), group in group_by_object(stream):
            cls = toplevel_class_by_name[cls_name]
            for message in group:
                translation_class = translation_class_by_column[cls, message.colname]
                key = id, message.language_id
                colname = str(message.colname)
                everything[translation_class][key][colname] = message.string
                count += 1
            if count > 1000:
                for translation_class, key_data in everything.items():
                    yield translation_class, key_data.values()
                count = 0
                everything.clear()
        for translation_class, data_dict in everything.items():
            yield translation_class, data_dict.values()

def group_by_object(stream):
    """Group stream by object

    Yields ((class name, object ID), (list of messages)) pairs.
    """
    stream = iter(stream)
    current = stream.next()
    current_key = current.cls, current.id
    group = [current]
    for message in stream:
        if (message.cls, message.id) != current_key:
            yield current_key, group
            group = []
        group.append(message)
        current = message
        current_key = current.cls, current.id
    yield current_key, group

class Merge(object):
    """Merge several sorted iterators together

    Additional iterators may be added at any time with add_iterator.
    Accepts None for the initial iterators
    If the same value appears in more iterators, there will be duplicates in
    the output.
    """
    def __init__(self, *iterators):
        self.next_values = []
        for iterator in iterators:
            if iterator is not None:
                self.add_iterator(iterator)

    def add_iterator(self, iterator):
        iterator = iter(iterator)
        try:
            value = iterator.next()
        except StopIteration:
            return
        else:
            heapq.heappush(self.next_values, (value, iterator))

    def __iter__(self):
        return self

    def next(self):
        if self.next_values:
            value, iterator = heapq.heappop(self.next_values)
            self.add_iterator(iterator)
            return value
        else:
            raise StopIteration

def merge_adjacent(gen):
    """Merge adjacent messages that compare equal"""
    gen = iter(gen)
    last = gen.next()
    for this in gen:
        if this.merge_key == last.merge_key:
            last.merge(this)
        elif last < this:
            yield last
            last = this
        else:
            raise AssertionError('Bad order, %s > %s' % (last, this))
    yield last

def leftjoin(left_stream, right_stream, key=lambda x: x, unused=None):
    """A "left join" operation on sorted iterators

    Yields (left, right) pairs, where left comes from left_stream and right
    is the corresponding item from right, or None

    Note that if there are duplicates in right_stream, you won't get duplicate
    rows for them.

    If given, unused should be a one-arg function that will get called on all
    unused items in right_stream.
    """
    left_stream = iter(left_stream)
    right_stream = iter(right_stream)
    try:
        right = right_stream.next()
        for left in left_stream:
            while right and key(left) > key(right):
                if unused is not None:
                    unused(right)
                right = right_stream.next()
            if key(left) == key(right):
                yield left, right
                del left
                right = right_stream.next()
            else:
                yield left, None
    except StopIteration:
        try:
            yield left, None
        except NameError:
            pass
        for left in left_stream:
            yield left, None
    else:
        if unused is not None:
            try:
                unused(right)
            except NameError:
                pass
            for right in right_stream:
                unused(right)

def synchronize(reference, stream, key=lambda x: x, unused=None):
    """Just the right side part of leftjoin(), Nones included"""
    for left, right in leftjoin(reference, stream, key, unused):
        yield right

def yield_source_csv_messages(cls, foreign_cls, csvreader, force_column=None):
    """Yield all messages from one source CSV file.
    """
    columns = list(cls.__table__.c)
    column_names = csvreader.next()
    # Assumptions: rows are in lexicographic order
    #  (taking numeric values as numbers of course)
    # Assumptions about the order of columns:
    # 1. It's the same in the table and in CSV
    # 2. Primary key is at the beginning
    # 3. First thing in the PK is the object id
    # 4. Last thing in the PK is the language
    # 5. Everything that follows is some translatable text
    assert [cls.__table__.c[name] for name in column_names] == columns, ','.join(c.name for c in columns)
    pk = columns[:len(cls.__table__.primary_key.columns)]
    first_string_index = len(pk)
    return _yield_csv_messages(foreign_cls, columns, first_string_index, csvreader, force_column=force_column)

def _yield_csv_messages(foreign_cls, columns, first_string_index, csvreader, origin='source CSV', crc_value='OFFICIAL', force_column=None):
    language_index = first_string_index - 1
    assert 'language' in columns[language_index].name, columns[language_index].name
    string_columns = columns[first_string_index:]
    if force_column is not None:
        assert len(string_columns) == 1
        string_columns = [force_column]
    for values in csvreader:
        id = int(values[0])
        messages = []
        for string, column in zip(values[first_string_index:], string_columns):
            message = Message(
                    foreign_cls.__name__,
                    id,
                    column.name,
                    string.decode('utf-8'),
                    column.type.length,
                    pot=pot_for_column(cls, column, force_column is not None),
                    origin=origin,
                    official=True,
                    source_crc=crc_value,
                    language_id=int(values[language_index]),
                )
            messages.append(message)
        messages.sort()
        for message in messages:
            yield message

def yield_guessed_csv_messages(file):
    """Yield messages from a CSV file, using the header to figure out what the data means.
    """
    csvreader = csv.reader(file, lineterminator='\n')
    column_names = csvreader.next()
    if column_names == 'language_id,table,id,column,source_crc,string'.split(','):
        # A translation CSV
        return yield_translation_csv_messages(file, True)
    # Not a translation CSV, figure out what the columns mean
    assert column_names[0].endswith('_id')
    assert column_names[1] == 'local_language_id'
    first_string_index = 2
    foreign_singlename = column_names[0][:-len('_id')]
    columns = [None] * len(column_names)
    column_indexes = dict((name, i) for i, name in enumerate(column_names))
    for foreign_cls in toplevel_classes:
        if foreign_cls.__singlename__ == foreign_singlename:
            break
    else:
        raise ValueError("Foreign key column name %s in %s doesn't correspond to a table" % (column_names[0], file))
    for translation_class in foreign_cls.translation_classes:
        for column in translation_class.__table__.c:
            column_index = column_indexes.get(column.name)
            if column_index is not None:
                columns[column_index] = column
    assert all([c is not None for c in columns[first_string_index:]])
    return _yield_csv_messages(foreign_cls, columns, first_string_index, csvreader, origin=file.name, crc_value='UNKNOWN')

def yield_translation_csv_messages(file, no_header=False):
    """Yield messages from a translation CSV file
    """
    csvreader = csv.reader(file, lineterminator='\n')
    if not no_header:
        columns = csvreader.next()
        assert columns == 'language_id,table,id,column,source_crc,string'.split(',')
    for language_id, table, id, column, source_crc, string in csvreader:
        yield Message(
                table,
                int(id),
                column,
                string.decode('utf-8'),
                origin='target CSV',
                source_crc=source_crc,
                language_id=int(language_id),
            )

def pot_for_column(cls, column, summary=False):
    """Translatable texts get categorized into different POT files to help
       translators prioritize. The pots are:

    - flavor: Flavor texts: here, strings from multiple versions are summarized
    - ripped: Strings ripped from the games; translators for "official"
      languages don't need to bother with these
    - effects: Fanon descriptions of things; they usually use technical
      language
    - misc: Everything else; usually small texts

    Set source to true if this is a flavor summary column. Others are
    determined by the column itself.
    """
    if summary:
        return 'flavor'
    elif column.info.get('ripped'):
        return 'ripped'
    elif column.name.endswith('effect'):
        return 'effects'
    else:
        return 'misc'

def number_replace(source, string):
    numbers_iter = iter(number_re.findall(source))
    next_number = lambda match: numbers_iter.next()
    return re.sub(r'\{num\}', next_number, string)

def match_to_source(source, *translations):
    """Matches translated string(s) to source

    The first translation whose source matches the source message, or whose CRC
    matches, or which is official, and which is not fuzzy, it is used.
    If thre's no such translation, the first translation is used.

    Returns (source, source string CRC, string for CSV file, exact match?)
    If there are no translations, returns (source, None, None, None)

    Handles translations where numbers have been replaced by {num}, if they
    have source information.
    """
    first = True
    best_crc = None
    for translation in translations:
        if translation is None:
            continue
        if translation.number_replacement:
            current_string = number_replace(source.string, translation.string)
            current_source = number_replace(source.string, translation.source)
            current_crc = crc(current_source)
        elif '{num}' in translation.string:
            print (u'Warning: {num} appears in %s, but not marked for number replacement. Discarding!' % translation).encode('utf-8')
            continue
        else:
            current_string = translation.string
            current_source = translation.source
            current_crc = translation.source_crc
        if translation.fuzzy:
            match = False
        elif translation.official:
            match = True
        elif current_source:
            match = source.string == current_source
        else:
            match = current_crc == crc(source.string)
        if first or match:
            best_string = current_string
            best_crc = current_crc
            best_message = translation
        if match:
            break
        first = False
    if best_crc:
        return source, best_crc, best_string, match
    else:
        return source, None, None, None

def merge_translations(source_stream, *translation_streams, **kwargs):
    """For each source message, get its best translation from translations.

    Translations should be ordered by priority, highest to lowest.

    Messages that don't appear in translations at all aren't included.
    """
    source = tuple(source_stream)
    streams = [
            synchronize(source, t, key=lambda m: m.merge_key, unused=kwargs.get('unused'))
            for t in translation_streams
        ]
    for messages in itertools.izip(source, *streams):
        yield match_to_source(*messages)
