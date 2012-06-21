#!/usr/bin/env python2

"""Dump /arc/ppark.narc.

This is an unmaintained one-shot script, only included in the repo for
reference.

"""


import sys
from struct import pack, unpack
import binascii

import pokedex.db
from pokedex.db.tables import PalPark

types = [
    '',
    'grass',
    'fire',
    'water',
    'bug',
    'normal',
    'poison',
    'electric',
    'ground',
    'fighting',
    'psychic',
    'rock',
    'ghost',
    'ice',
    'steel',
    'dragon',
    'dark',
    'flying',
]

areas = {
    1: 'forest',
    2: 'mountain',
    3: 'field',
    0x200: 'pond',
    0x400: 'sea',
}

session = pokedex.db.connect()()

with open(sys.argv[1], "rb") as f:
    f.seek(0x3C)
    for i in range(0xb8e // 6):
        data = f.read(6)
        area, score, rate, t1, t2 = unpack("<HBBBB", data)

        print(i+1, binascii.hexlify(data).decode(),
                   areas[area], score, rate, types[t1], types[t2])

        obj = PalPark()
        obj.species_id = i+1
        obj.area = areas[area]
        obj.base_score = score
        obj.rate = rate

        session.add(obj)


session.commit()
