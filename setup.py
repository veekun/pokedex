from setuptools import setup, find_packages
setup(
    name = 'Pokedex',
    version = '0.1',
    packages = find_packages(),
    package_data = { '': ['data'] },
    install_requires=['SQLAlchemy>=0.5.1', 'whoosh==0.3.0b5'],

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex:main',
        ],
    },
)
