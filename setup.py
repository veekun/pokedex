from setuptools import setup, find_packages
setup(
    name = 'Pokedex',
    version = '0.1',
    zip_safe = False,
    packages = find_packages(),
    package_data = { '': ['pokedex/data'] },
    install_requires=['SQLAlchemy>=0.5.1', 'whoosh>=0.3.0b24'],

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex:main',
        ],
    },
)
