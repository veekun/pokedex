# coding: utf-8
import itertools
from operator import itemgetter
from collections import OrderedDict

import pokedex.db
import sqlalchemy
from sqlalchemy import (Column, Integer, ForeignKey, Table, Unicode)
from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint

meta = sqlalchemy.MetaData()
Base = sqlalchemy.ext.declarative.declarative_base(metadata=meta)

class OldPokemonMove(Base):
    u"""Record of a move a Pokémon can learn."""
    __tablename__ = 'pokemon_moves'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, index=True,
        doc=u"ID of the Pokémon")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, index=True,
        doc=u"ID of the version group this applies to")
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False, index=True,
        doc=u"ID of the move")
    pokemon_move_method_id = Column(Integer, ForeignKey('pokemon_move_methods.id'), nullable=False, index=True,
        doc=u"ID of the method this move is learned by")
    level = Column(Integer, nullable=True, index=True, autoincrement=False,
        doc=u"Level the move is learned at, if applicable")
    order = Column(Integer, nullable=True,
        doc=u"The order which moves learned at the same level are learned in")

    __table_args__ = (
        PrimaryKeyConstraint('pokemon_id', 'version_group_id', 'move_id', 'pokemon_move_method_id', 'level'),
    )

# The pokemon move table has much redundancy across versions, but also many small variations.
# The general strategy here is to break movesets into chunks, such that a moveset is the union
# of a number of an arbitrary number of chunks, and those chunks can be shared across versions.

pokemon_moveset_table = Table('pokemon_movesets', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    #Column('hint', Unicode(79), unique=True, index=True),
    Column('pokemon_id', Integer, ForeignKey('pokemon.id')),
    Column('method_id', Integer, ForeignKey('pokemon_move_methods.id'), nullable=False, index=True),
)

pokemon_moveset_moves_table = Table('pokemon_moveset_moves', Base.metadata,
    Column('moveset_id', Integer),
    Column('move_id', Integer, ForeignKey('moves.id'), nullable=False, index=True),
    Column('level', Integer, nullable=True, index=True, autoincrement=False),
    Column('order', Integer, nullable=True, index=False),
    ForeignKeyConstraint(['moveset_id'], ['pokemon_movesets.id']),
    ForeignKeyConstraint(['move_id'], ['moves.id']),
    PrimaryKeyConstraint('moveset_id', 'move_id', 'level'),
)

pokemon_moveset_version_groups_table = Table('pokemon_moveset_version_groups', Base.metadata,
    Column('moveset_id', Integer),
    Column('version_group_id', Integer, ForeignKey('version_groups.id'), nullable=False, index=True),
    ForeignKeyConstraint(['moveset_id'], ['pokemon_movesets.id']),
    PrimaryKeyConstraint('moveset_id', 'version_group_id'),
)

def upgrade():
    engine = sqlalchemy.create_engine('postgresql:///pokedex')
    meta.reflect(bind=engine)

    pokemon_moveset_version_groups_table.drop(engine, checkfirst=True)
    pokemon_moveset_moves_table.drop(engine, checkfirst=True)
    pokemon_moveset_table.drop(engine, checkfirst=True)

    pokemon_moveset_table.create(engine, checkfirst=True)
    pokemon_moveset_moves_table.create(engine, checkfirst=True)
    pokemon_moveset_version_groups_table.create(engine, checkfirst=True)

    old_table = OldPokemonMove.__table__
    pokemon_table = meta.tables['pokemon']
    method_table = meta.tables['pokemon_move_methods']
    version_group_table = meta.tables['version_groups']
    generation_table = meta.tables['generations']
    print "all systems go"
    conn = engine.connect()
    for pokemon_id, in conn.execute(sqlalchemy.select([pokemon_table.c.id])):
        moves = conn.execute(
            sqlalchemy.select([
                old_table.c.pokemon_move_method_id,
                version_group_table.c.generation_id,
                old_table.c.version_group_id,
                old_table.c.move_id,
                old_table.c.level,
                old_table.c.order,
            ])
            .where(old_table.c.version_group_id == version_group_table.c.id)
            .where(old_table.c.pokemon_id == pokemon_id)
            .order_by("pokemon_move_method_id", "generation_id", version_group_table.c.order)
        ).fetchall()
        print pokemon_id

        for method_id, group in itertools.groupby(moves, itemgetter(0)):
            if method_id == 4:
                # TMs stayed more or less same across Gens 3&4 and 5&6
                def grouper(x):
                    return [0, 1, 2, 3, 3, 5, 5][x[1]]
            #elif method_id == 2:
                # Egg moves stick around forever
                #grouper = lambda _: None
            else:
                grouper = itemgetter(1)
            for _, group in itertools.groupby(group, grouper):
                movesets = OrderedDict()
                for version_group_id, group in itertools.groupby(group, itemgetter(2)):
                    movesets[version_group_id] = set(map(itemgetter(3, 4, 5), group))
                common = reduce(set.intersection, movesets.values())
                if common:
                    create_moveset(conn, pokemon_id, method_id, common, movesets.keys())
                deltas = []
                for version_group_id in movesets:
                    moveset = movesets[version_group_id] - common
                    delta_ids = []
                    for moveset_id, delta in reversed(deltas):
                        if delta <= moveset:
                            delta_ids.append(moveset_id)
                            moveset -= delta
                    if delta_ids:
                        add_to_movesets(conn, pokemon_id, method_id, delta_ids, version_group_id)
                    if moveset:
                        moveset_id = create_moveset(conn, pokemon_id, method_id, moveset, [version_group_id])
                        deltas.append((moveset_id, moveset))


def create_moveset(conn, pokemon_id, method_id, moves, versions):
    result = conn.execute(pokemon_moveset_table.insert(), pokemon_id=pokemon_id, method_id=method_id)
    moveset_id, = result.inserted_primary_key
    conn.execute(pokemon_moveset_moves_table.insert()
        .values(moveset_id=moveset_id),
        [dict(move_id=move_id, level=level, order=order) for move_id, level, order in moves])
    conn.execute(pokemon_moveset_version_groups_table.insert()
        .values(moveset_id=moveset_id),
        [dict(version_group_id=version_group_id) for version_group_id in versions])
    return moveset_id

def add_to_movesets(conn, pokemon_id, method_id, moveset_ids, version_group_id):
    conn.execute(pokemon_moveset_version_groups_table.insert()
        .values(version_group_id=version_group_id),
        [dict(moveset_id=moveset_id) for moveset_id in moveset_ids])

if __name__ == '__main__':
    upgrade()
