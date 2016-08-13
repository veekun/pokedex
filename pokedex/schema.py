# TODO eventually this file should be split up a bit, perhaps with the camel
# stuff and locus stuff in its own file
from collections import defaultdict
from collections import OrderedDict
from pprint import pprint

import camel



class _Attribute:
    name = None
    _creation_order = 0
    def __init__(self):
        self._creation_order = _Attribute._creation_order
        _Attribute._creation_order += 1

    def __set_name__(self, cls, name):
        self.name = name

    # TODO classtools, key sort by _creation_order


class _Value(_Attribute):
    def __init__(self, type, min=None, max=None):
        super().__init__()
        self.type = type
        # TODO only make sense for comparable types
        self.min = min
        self.max = max


class _List(_Attribute):
    def __init__(self, type, min=None, max=None):
        super().__init__()
        self.type = type
        self.min = min
        self.max = max


class _Map(_Attribute):
    def __init__(self, key_type, value_type):
        super().__init__()
        self.key_type = key_type
        self.value_type = value_type


class _Localized(_Attribute):
    def __init__(self, value_type):
        super().__init__()
        self.value_type = value_type


class _ForwardDeclaration:
    pass


class LocusMeta(type):
    def __init__(cls, name, bases, attrs):
        for key, attr in attrs.items():
            if hasattr(attr, '__set_name__'):
                attr.__set_name__(cls, key)

        super().__init__(name, bases, attrs)
        # TODO uhh yeah figure this out.  possibly related to attrs
        cls.index = {}

        # TODO need default values


class Locus(metaclass=LocusMeta):
    def __init__(self, **kwargs):
        cls = type(self)

        for key, value in kwargs.items():
            if not isinstance(getattr(cls, key, None), _Attribute):
                raise TypeError("Unexpected argument: {!r}".format(key))

            setattr(self, key, value)


# TODO seems to me that each of these, regardless of whether they have any
# additional data attached or not, are restricted to a fixed extra-game-ular
# list of identifiers
Type = _ForwardDeclaration()
Stat = _ForwardDeclaration()
GrowthRate = _ForwardDeclaration()
Evolution = _ForwardDeclaration()
EncounterMap = _ForwardDeclaration()
MoveSet = _ForwardDeclaration()
Pokedex = _ForwardDeclaration()




class Pokemon(Locus):
    # TODO version, language.  but those are kind of meta-fields; do they need treating specially?
    # TODO in old games, names are unique per game; in later games, they differ
    # per language.  what do i do about that?
    name = _Value(str)

    types = _List(Type, min=1, max=2)
    base_stats = _Map(Stat, int)
    growth_rate = _Value(GrowthRate)
    base_experience = _Value(int, min=0, max=255)

    pokedex_numbers = _Map(Pokedex, int)

    # TODO family?
    evolutions = _List(Evolution)

    species = _Value(str)
    flavor_text = _Value(str)
    # TODO maybe want little wrapper types that can display as either imperial
    # or metric
    # TODO maybe also dump as metric rather than plain numbers
    height = _Value(int)
    weight = _Value(int)

    # TODO this belongs to a place, not to a pokemon
    #encounters = _Value(EncounterMap)

    moves = _Value(MoveSet)

    # TODO should this be written in hex, maybe?
    game_index = _Value(int)


class Repository:
    def __init__(self):
        # type -> identifier -> list of objects
        self.objects = defaultdict(lambda: defaultdict(set))
        # type -> property -> value -> list of objects
        self.index = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    def add(self, obj):
        # TODO this should be declared by the type itself, obviously
        cls = type(obj)
        self.objects[cls][obj.identifier].add(obj)
        self.index[cls][cls.name][obj.name].add(obj)

    def fetch(self, cls, identifier):
        # TODO wrap in a...  multi-thing
        return self.objects[cls][identifier]


# TODO clean this garbage up -- better way of iterating the type, actually work for something other than pokemon...
POKEDEX_TYPES = camel.CamelRegistry(tag_prefix='tag:veekun.com,2005:pokedex/', tag_shorthand='!dex!')

@POKEDEX_TYPES.dumper(Locus, 'pokemon', version=None, inherit=True)
def _dump_locus(locus):
    data = OrderedDict()
    attrs = [(key, attr) for (key, attr) in type(locus).__dict__.items() if isinstance(attr, _Attribute)]
    attrs.sort(key=lambda kv: kv[1]._creation_order)

    for key, attr in attrs:
        if key in locus.__dict__:
            data[key.replace('_', '-')] = locus.__dict__[key]

    return data

@POKEDEX_TYPES.loader('pokemon', version=None)
def _load_locus(data, version):
    cls = Pokemon
    obj = cls()
    for key, value in data.items():
        key = key.replace('-', '_')
        assert hasattr(cls, key)
        setattr(obj, key, value)

    return obj


def _temp_main():
    repository = Repository()

    # just testing for now
    cam = camel.Camel([POKEDEX_TYPES])
    PATH = 'pokedex/data/gen1/red/en/pokemon.yaml'
    with open(PATH) as f:
        all_pokemon = cam.load(f.read())
        for identifier, pokemon in all_pokemon.items():
            # TODO i don't reeeally like this, but configuring a camel to do it
            # is a little unwieldy
            pokemon.version = 'red'
            pokemon.language = 'en'
            # TODO this in particular seems extremely clumsy, but identifiers ARE fundamentally keys...
            pokemon.identifier = identifier

            repository.add(pokemon)
    PATH = 'pokedex/data/gen1/red/fr/pokemon.yaml'
    with open(PATH) as f:
        all_pokemon = cam.load(f.read())
        for identifier, pokemon in all_pokemon.items():
            # TODO i don't reeeally like this, but configuring a camel to do it
            # is a little unwieldy
            pokemon.version = 'red'
            pokemon.language = 'fr'
            # TODO this in particular seems extremely clumsy, but identifiers ARE fundamentally keys...
            pokemon.identifier = identifier

            repository.add(pokemon)

    # TODO NEXT TODO
    # - how does the composite object work, exactly?  eevee.name.single?  eevee.name.latest?  no, name needs a language...
    # - but what about the vast majority of properties that are the same in every language and only vary by version?
    # - what about later games, where only some properties vary by language?  in the extreme case, xy/oras are single games!

    eevee = repository.fetch(Pokemon, 'eevee')
    pprint(eevee)
    return
    eevee = Pokemon['eevee']
    print(eevee.name)


    # TODO alright so we need to figure out the "index" part, and how you
    # access the index, and how a Pokemon object knows what game it belongs to,
    # and what the kinda wrapper overlay objects look like.  which i guess
    # requires having moves and stuff too, and then ripping other gen 1 games
    # as well.  phew!
    # TODO also some descriptor nonsense would be kind of nice up in here, i
    # guess, to enforce that the yaml is sensible.  but also we don't want to
    # slow down loading any more than we absolutely have to, ahem.  maybe do it
    # as a test?
    # TODO maybe worth considering that whole string de-duping idea.
    # TODO lol whoops records don't actually know their own identifiers!!  i
    # think what we have here is a more low-level "raw" representation anyway;
    # "eevee" would be the concept of eevee, you know.  i guess.
    print(all_pokemon['eevee'])
    pprint(all_pokemon['eevee'].__dict__)

if __name__ == '__main__':
    _temp_main()
