# encoding: utf8

import pytest
parametrize = pytest.mark.parametrize

import pokedex.roomaji

@parametrize(
    ('kana', 'roomaji'),
    [
        (u'ヤミカラス',         'yamikarasu'),

        # Elongated vowel
        (u'イーブイ',           'iibui'),
        (u'ホーホー',           'hoohoo'),
        (u'ピカチュウ',         u'pikachuu'),

        # Combined characters
        (u'ニャース',           'nyaasu'),
        (u'ジャ',               'ja'),
        (u'ぎゃくてん',         'gyakuten'),
        (u'ウェザーボール',     'wezaabooru'),

        # Special katakana combinations
        (u'ラティアス',         'ratiasu'),
        (u'ウィー',             'wii'),
        (u'セレビィ',           'sereby'),
    ]
)
def test_roomaji(kana, roomaji):
    result = pokedex.roomaji.romanize(kana)
    assert result == roomaji


@parametrize(
    ('kana', 'roomaji'),
    [
        (u'ヤミカラス',         u'jamikarasu'),

        # Elongated vowel
        (u'イーブイ',           u'íbui'),
        (u'ホーホー',           u'hóhó'),
        (u'ピカチュウ',         u'pikačú'),

        # Combined characters
        (u'ニャース',           u'ňjásu'),
        (u'ジャ',              u'dža'),
        (u'ぎゃくてん',         u'gjakuten'),
        (u'ウェザーボール',     u'wezábóru'),

        # Special katakana combinations
        (u'ラティアス',         u'ratiasu'),
        (u'ウィー',             u'wí'),
        (u'セレビィ',           u'serebí'),
    ]
)
def test_roomaji_cs(kana, roomaji):
    result = pokedex.roomaji.romanize(kana, 'cs')
    assert result == roomaji
