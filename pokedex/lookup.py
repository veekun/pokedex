# encoding: utf8
from sqlalchemy.sql import func

import pokedex.db.tables as tables

def lookup(session, name):
    """Attempts to find some sort of object, given a database session and name.

    Returns a list of (object, matchiness) tuples.  Matchiness is 1 for exact
    matches.  It is possible to get multiple exact matches; for example,
    'Metronome' will match both the move and the item.  In these cases, the
    results are returned in rough order of "importance", e.g., Pokémon come
    before moves come before types.

    This function does fuzzy matching iff there are no exact matches.

    Formes are not returned; "Shaymin" will return only grass Shaymin.
    
    Currently recognizes:
    - Pokémon names: "Eevee"
    """

    q = session.query(tables.Pokemon) \
               .filter(func.lower(tables.Pokemon.name) == name.lower()) \
               .filter_by(forme_base_pokemon_id=None)

    try:
        result = q.one()
        return [ (result, 1) ]
    except:
        return []
