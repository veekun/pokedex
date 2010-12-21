#!/usr/bin/env python2

import sqlite3

conn = sqlite3.connect("pokedex/data/pokedex.sqlite")

cur = conn.execute(
    """select p.id, p.name, pf.name
    from pokemon p
    join evolution_chains ec on p.evolution_chain_id = ec.id
    left join pokemon_forms pf on p.id = pf.unique_pokemon_id
    order by ec.id, is_baby = 0, coalesce(pf.form_base_pokemon_id, p.id),
             pf."order", pf.name
    ;""")

idmap = []

for i, row in enumerate(cur):
    idmap.append((1 + i, row[0]))

conn.executemany(
    """update pokemon set "order" = ? where id = ?""",
    idmap,
)

conn.commit()

