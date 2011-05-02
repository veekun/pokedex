
# Configuration for the tests.
# Use `py.test` to run the tests.

# (This file needs to be in or above the directory where py.test is called)

import pytest
import os

def pytest_addoption(parser):
    parser.addoption("--media-root", action="store",
        default=None,
        help="Root for the media files (if not specified and pokedex/data/media doesn't exist, tests are skipped)")
    parser.addoption("--all", action="store_true", default=False,
        help="Run all tests, even those that take a lot of time")

def pytest_generate_tests(metafunc):
    for funcargs in getattr(metafunc.function, 'funcarglist', ()):
        metafunc.addcall(funcargs=funcargs)
    for posargs in getattr(metafunc.function, 'posarglist', ()):
        metafunc.addcall(funcargs=dict(zip(metafunc.funcargnames, posargs)))
