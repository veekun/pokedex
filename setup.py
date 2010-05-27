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
        'docutils',
        'SQLAlchemy>=0.6',
        'whoosh>=0.3.0b24',
    ],

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex:main',
        ],
    },
)
