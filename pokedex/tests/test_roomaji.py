# encoding: utf8
from nose.tools import *
import unittest

import pokedex.roomaji


def test_roomaji():
    tests = [
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

    for kana, roomaji in tests:
        result = pokedex.roomaji.romanize(kana)
        assert_equal(result, roomaji, u"'%s' romanizes correctly" % roomaji)

def test_roomaji_cs():
    tests = [
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

    for kana, roomaji in tests:
        result = pokedex.roomaji.romanize(kana, 'cs')
        assert_equal(result, roomaji, u"'%s' romanizes correctly for Czech" % roomaji)
