# encoding: utf8
from nose.tools import *
import unittest

from pokedex.db import connect, tables
from pokedex.util import get

session = connect()

def test_get_item_identifier():
    item = get.get(session, tables.Item, identifier='master-ball')
    assert item.name == 'Master Ball'

def test_get_item_name():
    item = get.get(session, tables.Item, name='Awakening')
    assert item.name == 'Awakening'

def test_get_english_by_identifier():
    language = get.get(session, tables.Language, 'en')
    assert language.name == 'English'

def test_get_pokemon_baseform_identifier():
    for identifier in 'burmy shaymin unown cresselia'.split():
        poke = get.get(session, tables.Pokemon, identifier=identifier)
        assert poke.identifier == identifier
        assert poke.is_base_form

def test_get_pokemon_baseform_name():
    for name in 'Burmy Shaymin Unown Cresselia'.split():
        poke = get.get(session, tables.Pokemon, name=name)
        assert poke.name == name
        assert poke.is_base_form

def test_get_pokemon_baseform_name_explicit_language():
    french = get.get(session, tables.Language, 'fr')
    for name in 'Cheniti Shaymin Zarbi Cresselia'.split():
        poke = get.get(session, tables.Pokemon, name=name, language=french)
        assert poke.name_map[french] == name, poke.name_map[french]
        assert poke.is_base_form

def test_get_pokemon_other_form_identifier():
    for ii in 'wormadam/trash shaymin/sky shaymin/land'.split():
        pokemon_identifier, form_identifier = ii.split('/')
        poke = get.get(session, tables.Pokemon, identifier=pokemon_identifier, form_identifier=form_identifier)
        assert poke.identifier == pokemon_identifier
        if poke.form.unique_pokemon_id:
            assert poke.form.identifier == form_identifier

def test_pokemon():
    pokemon = get.pokemon(session)
    assert pokemon[0].identifier == 'bulbasaur'
    assert pokemon[-1].identifier == 'genesect'

def test_pokemon_by_name():
    pokemon = get.pokemon(session, order=tables.Pokemon.name)
    assert pokemon[0].identifier == 'abomasnow'
    assert pokemon[-1].identifier == 'zweilous'

def test_types_french_order():
    french = get.get(session, tables.Language, 'fr')
    types = get.types(session, order=None)
    types = list(get.order_by_name(types, tables.Type, language=french))
    assert types[0].name_map[french] == 'Acier', types[0].name_map[french]
    assert types[-1].name_map[french] == 'Vol', types[-1].name_map[french]

def test_moves():
    moves = get.moves(session)
    assert moves[0].identifier == 'absorb'
    assert moves[-1].identifier == 'zen-headbutt'

def test_items():
    items = get.items(session)
    assert items[0].identifier == 'ability-urge'
    assert items[-1].identifier == 'zoom-lens'

