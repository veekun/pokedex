from setuptools import setup, find_packages

import sys

setup(
    name = 'Pokedex',
    version = '0.1',
    zip_safe = False,
    packages = find_packages(),
    package_data = {
        'pokedex': ['data/csv/*.csv']
    },
    install_requires = [
        'SQLAlchemy>=0.9.7',
        'whoosh>=2.5,<2.7',
        'markdown',
        'construct',
        'six>=1.9.0',
    ],
    entry_points = {
        'console_scripts': [
            'pokedex = pokedex.main:setuptools_entry',
        ],
    },
    classifiers = [
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
)
