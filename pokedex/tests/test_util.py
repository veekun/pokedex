# encoding: utf8
from nose.tools import *
import unittest

from pokedex.db import connect, tables, util

session = connect()

def test_get_item_identifier():
    item = util.get(session, tables.Item, identifier='master-ball')
    assert item.name == 'Master Ball'

def test_get_item_name():
    item = util.get(session, tables.Item, name='Awakening')
    assert item.name == 'Awakening'

def test_get_english_by_identifier():
    language = util.get(session, tables.Language, 'en')
    assert language.name == 'English'

def test_get_pokemon_identifier():
    for identifier in 'burmy shaymin unown cresselia'.split():
        poke = util.get(session, tables.PokemonSpecies, identifier=identifier)
        assert poke.identifier == identifier

def test_get_pokemon_name():
    for name in 'Burmy Shaymin Unown Cresselia'.split():
        poke = util.get(session, tables.PokemonSpecies, name=name)
        assert poke.name == name

def test_get_pokemon_name_explicit_language():
    french = util.get(session, tables.Language, 'fr')
    for name in 'Cheniti Shaymin Zarbi Cresselia'.split():
        poke = util.get(session, tables.PokemonSpecies, name=name, language=french)
        assert poke.name_map[french] == name, poke.name_map[french]

def test_types_french_order():
    french = util.get(session, tables.Language, 'fr')
    types = session.query(tables.Type).filter(tables.Type.id < 10000)
    types = list(util.order_by_name(types, tables.Type, language=french))
    assert types[0].name_map[french] == 'Acier', types[0].name_map[french]
    assert types[-1].name_map[french] == 'Vol', types[-1].name_map[french]
