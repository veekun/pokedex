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

        # Combined characters
        (u'ニャース',           'nyaasu'),
        (u'ジャ',               'ja'),
        (u'ぎゃくてん',         'gyakuten'),

        # Special katakana combinations
        (u'ラティアス',         'ratiasu'),
        (u'ウィー',             'wii'),
    ]

    for kana, roomaji in tests:
        result = pokedex.roomaji.romanize(kana)
        assert_equal(result, roomaji, u"'%s' romanizes correctly" % roomaji)
