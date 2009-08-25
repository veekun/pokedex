import unittest

from pokedex.lookup import open_index
from pokedex.db import connect
from pokedex.db.load import load

def setup():
    # Reload data just in case
    session = connect()
    open_index(session=session, recreate=True)


def teardown():
    pass
