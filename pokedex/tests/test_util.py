# Encoding: utf8

import pytest

from pokedex.tests import single_params
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

@single_params(*'burmy shaymin unown cresselia'.split())
def test_get_pokemon_identifier(identifier):
    poke = util.get(session, tables.PokemonSpecies, identifier=identifier)
    assert poke.identifier == identifier

@single_params(*'Burmy Shaymin Unown Cresselia'.split())
def test_get_pokemon_name(name):
    poke = util.get(session, tables.PokemonSpecies, name=name)
    assert poke.name == name

@single_params(*'Cheniti Shaymin Zarbi Cresselia'.split())
def test_get_pokemon_name_explicit_language(name):
    french = util.get(session, tables.Language, 'fr')
    poke = util.get(session, tables.PokemonSpecies, name=name, language=french)
    assert poke.name_map[french] == name, poke.name_map[french]

def test_types_french_order():
    french = util.get(session, tables.Language, 'fr')
    types = session.query(tables.Type).filter(tables.Type.id < 10000)
    types = list(util.order_by_name(types, tables.Type, language=french))
    assert types[0].name_map[french] == 'Acier', types[0].name_map[french]
    assert types[-1].name_map[french] == 'Vol', types[-1].name_map[french]

@single_params(*range(1, 10) * 2)
def test_get_pokemon_id(id):
    result = util.get(session, tables.Pokemon, id=id)
    assert result.id == id
    assert result.__tablename__ == 'pokemon'
