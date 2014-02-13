from struct import Struct
from sys import argv

max_pokemon = 411  # Gen III indices are a Gen-I-esque mess past Celebi

# I got the first fifteen from FR by looking at tutor NPCs' scripts.  I got the
# full list from Emerald by searching for the first fifteen; the list starts at
# 0x61500C.
moves = ['mega-punch', 'swords-dance', 'mega-kick', 'body-slam', 'double-edge',
    'counter', 'seismic-toss', 'mimic', 'metronome', 'softboiled',
    'dream-eater', 'thunder-wave', 'explosion', 'rock-slide', 'substitute',

    # Emerald only
    'dynamicpunch', 'rollout', 'psych-up', 'snore', 'icy-wind', 'endure',
    'mud-slap', 'ice-punch', 'swagger', 'sleep-talk', 'swift', 'defense-curl',
    'thunderpunch', 'fire-punch', 'fury-cutter']

query_template = """
insert into pokemon_moves (pokemon_id, version_group_id, move_id,
  pokemon_move_method_id, level, "order") values (
    (select pokemon_id from pokemon_game_indices where version_id={version}
     and game_index={game_index}),
    {version_group},
    (select id from moves where identifier='{move}'),
    3, 0, null
);
"""

version_constants = {
    'POKEMON FIRE': {
        'version_id': 10,
        'version_group_id': 7,
        'offset': 0x459B80,
        'moves': 15
    },

    'POKEMON LEAF': {
        'version_id': 11,
        'version_group_id': 7,
        'offset': 0x4595A0,
        'moves': 15
    },

    'POKEMON EMER': {
        'version_id': 9,
        'version_group_id': 6,
        'offset': 0x61504C,
        'moves': 30
    }
}

with open(argv[1], 'rb') as rom:
    rom.seek(0xA0)
    version = rom.read(12).decode('ASCII')
    stuff = version_constants[version]

    # Flags go from least significant bit to most significant, and then to the
    # next byte, just like TMs, but there are few enough of them that we can
    # treat the whole field as a little-endian int.
    if stuff['moves'] == 15:
        flag_struct = Struct('<H')
    else:
        flag_struct = Struct('<L')

    rom.seek(stuff['offset'])

    # For LeafGreen, we want to skip straight to Defense Deoxys.
    if version == 'POKEMON LEAF':
        ids = [410]
        rom.seek(2 * 409, 1)
    else:
        ids = range(1, max_pokemon + 1)

    for pokemon in ids:
        # Read the flags
        flags, = flag_struct.unpack(rom.read(flag_struct.size))
        for move in range(stuff['moves']):
            if flags & 1:
                # This Pokémon learns this move!  Dump an SQL insert.
                print(query_template.format(
                    version=stuff['version_id'],
                    game_index=pokemon,
                    version_group=stuff['version_group_id'],
                    move=moves[move],
                ))
            flags >>= 1
