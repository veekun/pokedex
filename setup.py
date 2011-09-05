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
        'SQLAlchemy>=0.7',
        'whoosh>=1.1.0',
        'markdown',
        'construct',
    ],

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex.main:main',
        ],
    },
)
