# Encoding: UTF-8
"""Add XD tutors to the database

This is an unmaintained one-shot script, only included in the repo for reference.

"""

from pokedex.db import connect, tables, util

session = connect()

emerald = util.get(session, tables.Version, 'emerald')
fire_red = util.get(session, tables.Version, 'firered')
emerald_version_group = emerald.version_group
xd_version_group = util.get(session, tables.Version, 'xd').version_group
colo_version_group = util.get(session, tables.Version, 'colosseum').version_group

tutor = util.get(session, tables.PokemonMoveMethod, 'tutor')
level_up = util.get(session, tables.PokemonMoveMethod, 'level-up')

# According to every source I could find, the following can be taught to
# exactly the same set of Pokémon which learn it from the FR/LG/E tutor: --ete
for move_identifier in '''
        body-slam
        double-edge
        dream-eater
        icy-wind
        mimic
        seismic-toss
        substitute
        swagger
        thunder-wave
        '''.split():
    move = util.get(session, tables.Move, move_identifier)
    print move
    query = session.query(tables.PokemonMove.pokemon_id)
    query = query.filter_by(method=tutor)
    query = query.filter_by(move=move)
    em = set(p for (p, ) in query.filter_by(version_group=emerald.version_group).all())
    fr = set(p for (p, ) in query.filter_by(version_group=fire_red.version_group).all())
    assert not fr or not em.symmetric_difference(fr)
    for pokemon_id in em:
        pokemon_move = tables.PokemonMove()
        pokemon_move.pokemon_id = pokemon_id
        pokemon_move.move = move
        pokemon_move.method = tutor
        pokemon_move.level = 0
        pokemon_move.version_group = xd_version_group
        session.add(pokemon_move)

# These are only found in XD:
xd_tutor_data = {
    'nightmare': 'butterfree clefairy clefable jigglypuff wigglytuff meowth '
        'persian abra kadabra alakazam slowpoke slowbro gastly haunter gengar '
        'drowzee hypno exeggcute exeggutor lickitung starmie mr-mime jynx '
        'lapras porygon mewtwo mew hoothoot noctowl cleffa igglybuff natu xatu '
        'aipom espeon umbreon murkrow slowking misdreavus girafarig dunsparce '
        'sneasel houndour houndoom porygon2 stantler smoochum tyranitar lugia '
        'ho-oh celebi ralts kirlia gardevoir masquerain shedinja sableye '
        'roselia gulpin swalot spinda shuppet banette duskull dusclops '
        'chimecho absol jirachi deoxys '.split(),
    'selfdestruct': 'geodude graveler golem grimer muk shellder cloyster '
        'gastly haunter gengar onix voltorb electrode exeggcute exeggutor '
        'koffing weezing snorlax mewtwo mew sudowoodo pineco forretress '
        'steelix qwilfish slugma magcargo corsola seedot nuzleaf shiftry '
        'nosepass gulpin swalot wailmer wailord camerupt torkoal lunatone '
        'solrock baltoy claydol glalie metang metagross regirock regice '
        'registeel'.split(),
    'sky-attack': 'pidgey pidgeotto pidgeot spearow fearow doduo dodrio '
        'aerodactyl articuno zapdos moltres mew hoothoot noctowl togetic '
        'natu xatu murkrow delibird skarmory ho-oh taillow swellow wingull '
        'pelipper swablu altaria'.split(),
    'faint-attack': ['mew'],
    'fake-out': ['mew'],
    'hypnosis': ['mew'],
    'night-shade': ['mew'],
    'role-play': ['mew'],
    'zap-cannon': ['mew'],
    }

for move_identifier, pokemon_identifiers in xd_tutor_data.items():
    move = util.get(session, tables.Move, move_identifier)
    for pokemon_identifier in pokemon_identifiers:
        species = util.get(session, tables.PokemonSpecies, pokemon_identifier)
        try:
            pokemon, = species.pokemon
        except ValueError:
            assert pokemon_identifier == 'deoxys'
            pokemon = species.default_pokemon
        print move, pokemon

        pokemon_move = tables.PokemonMove()
        pokemon_move.pokemon = pokemon
        pokemon_move.move = move
        pokemon_move.method = tutor
        pokemon_move.level = 0
        pokemon_move.version_group = xd_version_group
        session.add(pokemon_move)

# And unfortunately, we have to copy level-up moves. To both XD and Colosseum.
for pokemon_id, move_id, level, order in set(
        session.query(
                tables.PokemonMove.pokemon_id,
                tables.PokemonMove.move_id,
                tables.PokemonMove.level,
                tables.PokemonMove.order,
            )
        .filter_by(method=level_up)
        .filter_by(version_group=emerald_version_group)
    ):
    for version_group in xd_version_group, colo_version_group:
        print pokemon_id, move_id
        pokemon_move = tables.PokemonMove()
        pokemon_move.pokemon_id = pokemon_id
        pokemon_move.move_id = move_id
        pokemon_move.method = level_up
        pokemon_move.level = level
        pokemon_move.order = order
        pokemon_move.version_group = version_group
        session.add(pokemon_move)


session.commit()
