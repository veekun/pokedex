# Configuration for the tests.
# Use `py.test` to run the tests.

# (This file needs to be in or above the directory where py.test is called)

import pytest
import os

def pytest_addoption(parser):
    group = parser.getgroup("pokedex")
    group.addoption("--engine", action="store", default=None,
        help="Pokedex database URI")
    group.addoption("--index", action="store", default=None,
        help="Path to index directory")
    group.addoption("--media-root", action="store", default=None,
        help="Root for the media files (if not specified and pokedex/data/media doesn't exist, tests are skipped)")
    group.addoption("--all", action="store_true", default=False,
        help="Run all tests, even those that take a lot of time")

def pytest_runtest_setup(item):
    if 'slow' in item.keywords and not item.config.getvalue('all'):
        pytest.skip("skipping slow tests")

@pytest.fixture(scope="module")
def session(request):
    import pokedex.db
    engine_uri = request.config.getvalue("engine")
    return pokedex.db.connect(engine_uri)

@pytest.fixture(scope="module")
def lookup(request, session):
    import pokedex.lookup
    index_dir = request.config.getvalue("index")
    return pokedex.lookup.PokedexLookup(index_dir, session)

@pytest.fixture(scope="session")
def media_root(request):
    media_root = request.config.getvalue("media_root")
    if not media_root:
        media_root = os.path.join(os.path.dirname(__file__), '..', 'data', 'media')
        if not os.path.isdir(media_root):
            raise pytest.skip("Media unavailable")
    return media_root
