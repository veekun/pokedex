# encoding: utf8
from nose.tools import *
import unittest

from pokedex.lookup import PokedexLookup

lookup = None

def setup():
    # Recreate data
    global lookup
    lookup = PokedexLookup()
    lookup.rebuild_index()

def test_exact_lookup():
    tests = [
        # Simple lookups
        (u'Eevee',          'pokemon',      133),
        (u'Scratch',        'moves',        10),
        (u'Master Ball',    'items',        1),
        (u'normal',         'types',        1),
        (u'Run Away',       'abilities',    50),

        # Funny characters
        (u'Mr. Mime',       'pokemon',      122),
        (u"Farfetch'd",     'pokemon',      83),
        (u'Poké Ball',      'items',        4),

        # Forms
        (u'Rotom',          'pokemon',      479),
        (u'Wash Rotom',     'pokemon',      504),

        # Other languages
        (u'イーブイ',       'pokemon',      133),
        (u'Iibui',          'pokemon',      133),
        (u'Eievui',         'pokemon',      133),
        (u'이브이',         'pokemon',      133),
        (u'伊布',           'pokemon',      133),
        (u'Evoli',          'pokemon',      133),
    ]

    for input, table, id in tests:
        results = lookup.lookup(input)
        assert_equal(len(results), 1,           u"'%s' returns one result" % input)
        assert_equal(results[0].exact, True,    u"'%s' match exactly" % input)

        row = results[0].object
        assert_equal(row.__tablename__, table,  u"'%s' is in the right table" % input)
        assert_equal(row.id, id,                u"'%s' returns the right id" % input)


def test_id_lookup():
    results = lookup.lookup(u'1')
    assert_true(len(results) >= 5,              u'At least five things have id 1')
    assert_true(all(_.object.id == 1 for _ in results),
                                                u'All results have id 1')

def test_multi_lookup():
    results = lookup.lookup(u'Metronome')
    assert_equal(len(results), 2,               u'Two things called "Metronome"')
    assert_true(results[0].exact,               u'Metronome matches are exact')


def test_type_lookup():
    results = lookup.lookup(u'pokemon:1')
    assert_equal(results[0].object.__tablename__, 'pokemon',
                                                u'Type restriction works correctly')
    assert_equal(len(results), 1,               u'Only one id result when type is specified')
    assert_equal(results[0].name, u'Bulbasaur', u'Type + id returns the right result')

    results = lookup.lookup(u'1', valid_types=['pokemon'])
    assert_equal(results[0].name, u'Bulbasaur', u'valid_types works as well as type: prefix')

def test_language_lookup():
    # There are two objects named "charge": the move Charge, and the move
    # Tackle, which is called "Charge" in French.
    results = lookup.lookup(u'charge')
    assert_true(len(results) > 1,               u'There are multiple "charge"s')

    results = lookup.lookup(u'@fr:charge')
    assert_equal(results[0].iso639, u'fr',      u'Language restriction works correctly')
    assert_equal(len(results), 1,               u'Only one "charge" result when language is specified')
    assert_equal(results[0].object.name, u'Tackle',
                                                u'Language + vague name returns the right result')

    results = lookup.lookup(u'charge', valid_types=['@fr'])
    assert_equal(results[0].object.name, u'Tackle',
                                                u'valid_types works as well as @lang: prefix')

    results = lookup.lookup(u'@fr,move:charge')
    assert_equal(results[0].object.name, u'Tackle',
                                                u'Languages and types both work together')

def test_fuzzy_lookup():
    tests = [
        # Regular English names
        (u'chamander',          u'Charmander'),
        (u'pokeball',           u'Poké Ball'),

        # Names with squiggles in them
        (u'farfetchd',          u"Farfetch'd"),
        (u'porygonz',           u'Porygon-Z'),

        # Sufficiently long foreign names
        (u'カクレオ',           u'Kecleon'),
        (u'Yamikrasu',          u'Murkrow'),
    ]

    for misspelling, name in tests:
        results = lookup.lookup(misspelling)
        first_result = results[0]
        assert_equal(first_result.object.name, name,
                                                u'Simple misspellings are corrected')

    results = lookup.lookup(u'Nidoran')
    top_names = [_.object.name for _ in results[0:2]]
    assert_true(u'Nidoran♂' in top_names,       u'Nidoran♂ is a top result for "Nidoran"')
    assert_true(u'Nidoran♀' in top_names,       u'Nidoran♀ is a top result for "Nidoran"')

def test_wildcard_lookup():
    tests = [
        (u'pokemon:*meleon',    u'Charmeleon'),
        (u'item:master*',       u'Master Ball'),
        (u'ee?ee',              u'Eevee'),
    ]

    for wildcard, name in tests:
        results = lookup.lookup(wildcard)
        first_result = results[0]
        assert_equal(first_result.object.name, name,
                                                u'Wildcards work correctly')

def test_random_lookup():
    for _ in xrange(5):
        results = lookup.lookup(u'random')
        assert_equal(len(results), 1,           u'Random returns one result')

    for table_name in [u'pokemon', u'moves', u'items', u'abilities', u'types']:
        results = lookup.lookup(u'random', valid_types=[table_name])
        assert_equal(len(results), 1,           u'Constrained random returns one result')
        assert_equal(results[0].object.__tablename__, table_name,
                                                u'Constrained random returns result from the right table')
