# Encoding: UTF-8
"""Fill the version_group_pokemon_move_methods table

This is an unmaintained one-shot script, only included in the repo for reference.


"""


from sqlalchemy.sql import exists, func
from sqlalchemy.orm import lazyload
from sqlalchemy import and_, or_, not_

from pokedex.db import connect, tables, load

session = connect()

session.query(tables.VersionGroupPokemonMoveMethod).delete()

q = session.query(tables.VersionGroup, tables.PokemonMoveMethod)
q = q.filter(exists().where(and_(
        tables.PokemonMove.pokemon_move_method_id == tables.PokemonMoveMethod.id,
        tables.PokemonMove.version_group_id == tables.VersionGroup.id)))
q = q.options(lazyload('*'))
for version_group, pokemon_move_method in q:
    entry = tables.VersionGroupPokemonMoveMethod(
            version_group=version_group,
            pokemon_move_method=pokemon_move_method,
        )
    session.add(entry)


load.dump(session, tables=['version_group_pokemon_move_methods'])
print "Dumped to CSV, rolling back transaction"
session.rollback()
