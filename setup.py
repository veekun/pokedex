from setuptools import setup, find_packages
setup(
    name = 'Pokedex',
    version = '0.1',
    packages = find_packages(),
    package_data = { '': 'data' },

    entry_points = {
        'console_scripts': [
            'pokedex = pokedex:main',
        ],
    },
)
