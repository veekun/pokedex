# Encoding: utf8

import pytest
parametrize = pytest.mark.parametrize

from pokedex.db import tables, util

def test_get_item_identifier(session):
    item = util.get(session, tables.Item, identifier=u'master-ball')
    assert item.name == 'Master Ball'

def test_get_item_name(session):
    item = util.get(session, tables.Item, name=u'Awakening')
    assert item.name == 'Awakening'

def test_get_english_by_identifier(session):
    language = util.get(session, tables.Language, u'en')
    assert language.name == 'English'

@parametrize('identifier', [u'burmy', u'shaymin', u'unown', u'cresselia'])
def test_get_pokemon_identifier(session, identifier):
    poke = util.get(session, tables.PokemonSpecies, identifier=identifier)
    assert poke.identifier == identifier

@parametrize('name', [u'Burmy', u'Shaymin', u'Unown', u'Cresselia'])
def test_get_pokemon_name(session, name):
    poke = util.get(session, tables.PokemonSpecies, name=name)
    assert poke.name == name

@parametrize('name', [u'Cheniti', u'Shaymin', u'Zarbi', u'Cresselia'])
def test_get_pokemon_name_explicit_language(session, name):
    french = util.get(session, tables.Language, u'fr')
    poke = util.get(session, tables.PokemonSpecies, name=name, language=french)
    assert poke.name_map[french] == name, poke.name_map[french]

def test_types_french_order(session):
    french = util.get(session, tables.Language, u'fr')
    types = session.query(tables.Type).filter(tables.Type.id < 10000)
    types = list(util.order_by_name(types, tables.Type, language=french))
    assert types[0].name_map[french] == 'Acier', types[0].name_map[french]
    # SQLite doesn't know how to sort unicode properly, so accented charaters come last.
    # Postgres doesn't have this problem.
    assert types[-1].name_map[french] in (u'Électrik', u'Vol'), types[-1].name_map[french]

@parametrize('id', range(1, 10))
def test_get_pokemon_id(session, id):
    result = util.get(session, tables.Pokemon, id=id)
    assert result.id == id
    assert result.__tablename__ == 'pokemon'
