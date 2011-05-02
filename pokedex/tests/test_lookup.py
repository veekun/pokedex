# Encoding: UTF-8

from pokedex.tests import *

from pokedex.lookup import PokedexLookup

lookup = PokedexLookup()

@positional_params(
        # Simple lookups
        (u'Eevee',          'pokemon_species',133),
        (u'Scratch',        'moves',        10),
        (u'Master Ball',    'items',        1),
        (u'normal',         'types',        1),
        (u'Run Away',       'abilities',    50),

        # Funny characters
        (u'Mr. Mime',       'pokemon_species', 122),
        (u"Farfetch'd",     'pokemon_species', 83),
        (u'Poké Ball',      'items',           4),

        # Forms
        (u'Rotom',          'pokemon_species', 479),
        (u'Wash Rotom',     'pokemon_forms',   708),
        (u'East Shellos',   'pokemon_forms',   688),

        # Other languages
        (u'イーブイ',       'pokemon_species', 133),
        (u'Iibui',          'pokemon_species', 133),
        (u'Eievui',         'pokemon_species', 133),
        (u'이브이',         'pokemon_species', 133),
        (u'伊布',           'pokemon_species', 133),
        (u'Evoli',          'pokemon_species', 133),
    )
def test_exact_lookup(input, table, id):
    results = lookup.lookup(input)
    assert len(results) == 1
    assert results[0].exact == True

    row = results[0].object
    assert row.__tablename__ == table
    assert row.id == id


def test_id_lookup():
    results = lookup.lookup(u'1')
    assert len(results) >= 5
    assert all(result.object.id == 1 for result in results)


def test_multi_lookup():
    results = lookup.lookup(u'Metronome')
    assert len(results) == 2
    assert results[0].exact


def test_type_lookup():
    results = lookup.lookup(u'pokemon:1')
    assert results[0].object.__tablename__ == 'pokemon_species'
    assert len(results) == 1
    assert results[0].object.name == u'Bulbasaur'

    results = lookup.lookup(u'1', valid_types=['pokemon_species'])
    assert results[0].object.name == u'Bulbasaur'


def test_language_lookup():
    # There are two objects named "charge": the move Charge, and the move
    # Tackle, which is called "Charge" in French.
    results = lookup.lookup(u'charge')
    assert len(results) > 1

    results = lookup.lookup(u'@fr:charge')
    assert results[0].iso639 == u'fr'
    assert len(results) == 1
    assert results[0].object.name == u'Tackle'

    results = lookup.lookup(u'charge', valid_types=['@fr'])
    assert results[0].object.name == u'Tackle'

    results = lookup.lookup(u'@fr,move:charge')
    assert results[0].object.name == u'Tackle'

    results = lookup.lookup(u'@fr:charge', valid_types=['move'])
    assert results[0].object.name, u'Tackle'


@positional_params(
        # Regular English names
        (u'chamander',          u'Charmander'),
        (u'pokeball',           u'Poké Ball'),

        # Names with squiggles in them
        (u'farfetchd',          u"Farfetch'd"),
        (u'porygonz',           u'Porygon-Z'),

        # Sufficiently long foreign names
        (u'カクレオ',           u'Kecleon'),
        (u'Yamikrasu',          u'Murkrow'),
    )
def test_fuzzy_lookup(misspelling, name):
    results = lookup.lookup(misspelling)
    first_result = results[0]
    assert first_result.object.name == name


def test_nidoran():
    results = lookup.lookup(u'Nidoran')
    top_names = [result.object.name for result in results[0:2]]
    assert u'Nidoran♂' in top_names
    assert u'Nidoran♀' in top_names


@positional_params(
        (u'pokemon:*meleon',    u'Charmeleon'),
        (u'item:master*',       u'Master Ball'),
        (u'ee?ee',              u'Eevee'),
    )
def test_wildcard_lookup(wildcard, name):
    results = lookup.lookup(wildcard)
    first_result = results[0]
    assert first_result.object.name == name


def test_bare_random():
    for i in range(5):
        results = lookup.lookup(u'random')
        assert len(results) == 1


@positional_params(
        [u'pokemon_species'],
        [u'moves'],
        [u'items'],
        [u'abilities'],
        [u'types'],
    )
def test_qualified_random(table_name):
    results = lookup.lookup(u'random', valid_types=[table_name])
    assert len(results) == 1
    assert results[0].object.__tablename__ == table_name


def test_crash_empty_prefix():
    """Searching for ':foo' used to crash, augh!"""
    results = lookup.lookup(u':Eevee')
    assert results[0].object.name == u'Eevee'
