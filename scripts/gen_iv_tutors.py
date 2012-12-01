from struct import Struct

max_pokemon = 507

# As usual, I'm just going to dump SQL
print('begin;')

# Delete the previous tutor data, except for the special tutors that aren't
# stored as flags
print("""delete from pokemon_moves where version_group_id in (9, 10)
    and pokemon_move_method_id=3
    and move_id not in (select id from moves where identifier in
        ('blast-burn', 'hydro-cannon', 'frenzy-plant', 'draco-meteor'));
""")

# A template for inserting a pokemon_moves record.  No internal Pokémon indices
# change between Pt and HG/SS, so we'll just use Pt's.
insert_template = """insert into pokemon_moves (pokemon_id, version_group_id,
    move_id, pokemon_move_method_id, level, "order")
values (
    (select pokemon_id from pokemon_game_indices where game_index={pokemon}
        and version_id=14),
    {version_group}, {move}, 3, 0, null
);
"""

# PLATINUM
move_struct = Struct('<H10x')  # We don't care about shard costs or anything
move_count = 38
moves = []

with open('/tmp/pt/overlay9/overlay_00000005.bin', 'rb') as overlay:
    overlay.seek(0x2FF64)

    for move in range(move_count):
        move = overlay.read(move_struct.size)
        move, = move_struct.unpack(move)
        moves.append(move)

    # The Eggs don't get dummy flags; it goes straight to Attack Deoxys
    for pokemon in range(1, max_pokemon + 1 - 2):
        if pokemon > 493:
            pokemon += 2

        for n, move in enumerate(moves):
            if n % 8 == 0:
                flag_byte, = overlay.read(1)

            if flag_byte & 1:
                print(insert_template.format(
                    pokemon=pokemon,
                    version_group=9,
                    move=move
                ))

            flag_byte >>= 1


# HEARTGOLD
move_struct = Struct('<H2x')  # Costs are just BP so there's less to skip
move_count = 52
moves = []

# The move list for HG is in a compressed overlay, which I decompressed
# beforehand with magical's lzss3.py -- https://github.com/magical/nlzss
with open('/tmp/overlays/overlay_00000001.bin', 'rb') as overlay:
    overlay.seek(0x23AE0)

    for move in range(move_count):
        move = overlay.read(move_struct.size)
        move, = move_struct.unpack(move)
        moves.append(move)

# And the flags are in their own file, padded to an easy length this time.
# This seemed nice at first but it made it harder to find the move list...
flag_struct = Struct('<Q')
with open('/tmp/hg/fsroot/fielddata/wazaoshie/waza_oshie.bin', 'rb') as flagbin:
    for pokemon in range(1, max_pokemon + 1 - 2):
        if pokemon > 493:
            pokemon += 2

        flags, = flag_struct.unpack(flagbin.read(8))

        for n, move in enumerate(moves):
            if flags & 1:
                print(insert_template.format(
                    pokemon=pokemon,
                    version_group=10,
                    move=move
                ))

            flags >>= 1

# Duplicate moves for the Castforms
print("""
insert into pokemon_moves (pokemon_id, version_group_id, move_id,
    pokemon_move_method_id, level, "order")
select p.id, pm.version_group_id, pm.move_id, 3, 0, null
from pokemon_moves pm
join pokemon p on pm.pokemon_id=p.species_id and p.is_default=False
where p.species_id=351 and pm.pokemon_move_method_id=3 and pm.version_group_id in
    (9, 10);
""")

print('commit;')
