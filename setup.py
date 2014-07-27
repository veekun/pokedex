from setuptools import setup, find_packages
setup(
    name = 'Pokedex',
    version = '0.1',
    zip_safe = False,
    packages = find_packages(),
    package_data = {
        'pokedex': ['data/csv/*.csv']
    },
    install_requires=[
        'SQLAlchemy>=0.9.7',
        'whoosh>=2.5',
        'markdown',
        'construct',
    ],

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex.main:setuptools_entry',
        ],
    },
)
