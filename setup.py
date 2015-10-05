from setuptools import setup, find_packages

import sys

deps = [
    'SQLAlchemy>=0.9.7',
    'whoosh>=2.5,<2.7',
    'markdown',
    'construct',
    'six>=1.9.0',
]
if sys.version_info < (2, 7):
    # We don't actually use this, but markdown does
    deps.append('importlib')

setup(
    name = 'Pokedex',
    version = '0.1',
    zip_safe = False,
    packages = find_packages(),
    package_data = {
        'pokedex': ['data/csv/*.csv']
    },
    install_requires=deps,

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex.main:setuptools_entry',
        ],
    },
)
