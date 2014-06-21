# Encoding: utf8

import base64

import pytest

from pokedex import struct
from pokedex.db import connect, tables, util

from pokedex.tests import positional_params

session = connect()

def check_with_roundtrip(gen, pkmn, expected):
    blob = pkmn.blob
    del pkmn.blob
    assert blob == pkmn.blob

    assert pkmn.export_dict() == expected
    from_dict = struct.save_file_pokemon_classes[5](session=session,
        dict_=expected)
    assert from_dict.blob == blob
    assert from_dict.export_dict() == expected

    from_blob = struct.save_file_pokemon_classes[5](session=session,
        blob=pkmn.blob)
    assert from_blob.blob == blob
    assert from_blob.export_dict() == expected


voltorb_species = util.get(session, tables.PokemonSpecies, 'voltorb')
def voltorb_and_dict():
    pkmn = struct.save_file_pokemon_classes[5](session=session)
    voltorb_species = util.get(session, tables.PokemonSpecies, 'voltorb')
    pkmn.species = voltorb_species
    expected = {
            'gender': 'male',
            'species': dict(id=100, name=u'Voltorb'),
            'level': 1,
            'nickname': u'\0' * 11,
            'nicknamed': False,
            'nickname trash': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==',
            'moves': [],
        }
    return pkmn, expected


def test_species():
    pkmn, expected = voltorb_and_dict()
    assert pkmn.species == voltorb_species
    assert pkmn.pokemon == voltorb_species.default_pokemon
    assert pkmn.form == voltorb_species.default_form
    assert pkmn.export_dict() == expected

@positional_params([True], [False])
def test_moves(use_update):
    pkmn, expected = voltorb_and_dict()
    new_moves = (util.get(session, tables.Move, 'sonicboom'), )
    expected['moves'] = [dict(id=49, name=u'SonicBoom', pp=0)]
    if use_update:
        pkmn.update(moves=expected['moves'])
    else:
        pkmn.moves = new_moves
    assert pkmn.moves == new_moves
    check_with_roundtrip(5, pkmn, expected)

    new_moves += (util.get(session, tables.Move, 'explosion'),)
    expected['moves'].append(dict(id=153, name=u'Explosion', pp=0))
    if use_update:
        pkmn.update(moves=expected['moves'])
    else:
        pkmn.moves = new_moves
    assert pkmn.moves == new_moves
    check_with_roundtrip(5, pkmn, expected)

    new_pp = (20,)
    expected['moves'][0]['pp'] = 20
    if use_update:
        pkmn.update(moves=expected['moves'])
    else:
        pkmn.move_pp = new_pp
    assert pkmn.move_pp == (20, 0, 0, 0)
    check_with_roundtrip(5, pkmn, expected)

@positional_params([True], [False])
def test_personality(use_update):
    pkmn, expected = voltorb_and_dict()
    assert pkmn.is_shiny == True
    if use_update:
        pkmn.update(personality=12345)
    else:
        pkmn.personality = 12345
    assert pkmn.is_shiny == False
    expected['personality'] = 12345
    check_with_roundtrip(5, pkmn, expected)

@positional_params([True], [False])
def test_pokeball(use_update):
    pkmn, expected = voltorb_and_dict()
    masterball = util.get(session, tables.Item, 'master-ball')
    expected['pokeball'] = dict(id_dppt=1, name='Master Ball')
    if use_update:
        pkmn.update(pokeball=expected['pokeball'])
    else:
        pkmn.pokeball = masterball
    assert pkmn.pokeball == masterball
    check_with_roundtrip(5, pkmn, expected)

@positional_params([True], [False])
def test_nickname(use_update):
    pkmn, expected = voltorb_and_dict()
    if use_update:
        pkmn.update(nickname=unicode(pkmn.nickname))
    else:
        pkmn.nickname = pkmn.nickname
    expected['nicknamed'] = True
    check_with_roundtrip(5, pkmn, expected)

    if use_update:
        pkmn.update(nicknamed=False)
    else:
        pkmn.is_nicknamed = False
    expected['nicknamed'] = False
    check_with_roundtrip(5, pkmn, expected)

    if use_update:
        pkmn.update(nicknamed=True)
    else:
        pkmn.is_nicknamed = True
    expected['nicknamed'] = True
    check_with_roundtrip(5, pkmn, expected)

@positional_params([True], [False])
def test_experience(use_update):
    pkmn, expected = voltorb_and_dict()
    for exp in 2197, 2200:
        if use_update:
            pkmn.update(exp=exp)
        else:
            pkmn.exp = exp
        assert pkmn.exp == exp
        assert pkmn.experience_rung.experience <= pkmn.exp
        assert pkmn.next_experience_rung.experience > pkmn.exp
        assert pkmn.experience_rung.level + 1 == pkmn.next_experience_rung.level
        assert (pkmn.experience_rung.growth_rate ==
            pkmn.next_experience_rung.growth_rate ==
            pkmn.species.growth_rate)
        assert pkmn.level == pkmn.experience_rung.level
        assert pkmn.exp_to_next == pkmn.next_experience_rung.experience - pkmn.exp
        rung_difference = (pkmn.next_experience_rung.experience -
            pkmn.experience_rung.experience)
        assert pkmn.progress_to_next == (
            pkmn.exp - pkmn.experience_rung.experience) / float(rung_difference)
        if exp == 2197:
            expected['level'] = 13
        else:
            expected['exp'] = exp
            expected['level'] = 13
        check_with_roundtrip(5, pkmn, expected)

def test_update_inconsistent_exp_level():
    pkmn, expected = voltorb_and_dict()
    with pytest.raises(ValueError):
        pkmn.update(exp=0, level=100)

@positional_params([True], [False])
def test_level(use_update):
    pkmn, expected = voltorb_and_dict()
    level = 10
    if use_update:
        pkmn.update(level=level)
    else:
        pkmn.level = level
    assert pkmn.level == level
    assert pkmn.experience_rung.level == level
    assert pkmn.experience_rung.experience == pkmn.exp
    expected['level'] = level
    check_with_roundtrip(5, pkmn, expected)

@positional_params([True], [False])
def test_ability(use_update):
    pkmn, expected = voltorb_and_dict()
    ability = util.get(session, tables.Ability, 'drizzle')
    pkmn.ability = ability
    assert pkmn.ability == ability
    expected['ability'] = dict(id=2, name='Drizzle')
    check_with_roundtrip(5, pkmn, expected)

def test_squirtle_blob():
    # Japanese Dream World Squirtle from http://projectpokemon.org/events
    blob = base64.b64decode('J2ZqBgAAICQHAAAAkOaKyTACAABGLAABAAAAAAAAAAAAAAAAA'
        'AAAACEAJwCRAG4AIx4eKAAAAAD171MHAAAAAAAAAQAAAAAAvDDLMKww4TD//wAAAAAAAA'
        'AAAAD//wAVAAAAAAAAAAAw/zD/T/9S/0f///8AAAAAAAAACgoOAABLAAAZCgAAAA==')
    expected = {
        'ability': {'id': 44, 'name': u'Rain Dish'},
        'date met': '2010-10-14',
        'gender': 'male',
        'genes': {u'attack': 31,
                u'defense': 27,
                u'hp': 21,
                u'special attack': 21,
                u'special defense': 3,
                u'speed': 7},
        'happiness': 70,
        'level': 10,
        'met at level': 10,
        'met location': {'id_dp': 75, 'name': u'Spring Path'},
        'moves': [{'id': 33, 'name': u'Tackle', 'pp': 35},
                {'id': 39, 'name': u'Tail Whip', 'pp': 30},
                {'id': 145, 'name': u'Bubble', 'pp': 30},
                {'id': 110, 'name': u'Withdraw', 'pp': 40}],
        'nickname': u'ゼニガメ',
        'nickname trash': 'vDDLMKww4TD//wAAAAAAAAAAAAD//w==',
        'nicknamed': False,
        'oiginal trainer': {'gender': 'male',
                            'id': 59024,
                            'name': u'ＰＰｏｒｇ',
                            'secret': 51594},
        'original country': 'jp',
        'original version': 21,
        'personality': 107636263,
        'pokeball': {'id_dppt': 25, 'name': u'Hyper Potion'},
        'species': {'id': 7, 'name': u'Squirtle'}}
    pkmn = struct.save_file_pokemon_classes[5](session=session, blob=blob)
    check_with_roundtrip(5, pkmn, expected)
