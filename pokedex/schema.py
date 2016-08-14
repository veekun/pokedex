# TODO eventually this file should be split up a bit, perhaps with the camel
# stuff and locus stuff in its own file
from collections import defaultdict
from collections import OrderedDict
from pprint import pprint
import types

import camel


class _Attribute:
    name = None
    _creation_order = 0

    def __init__(self):
        self._creation_order = _Attribute._creation_order
        _Attribute._creation_order += 1

    def __get__(self, inst, owner):
        # TODO this is intended for the glom object, not a slice
        return self.Glommed(self, inst)

    def __set_name__(self, cls, name):
        self.name = name

    class Glommed:
        def __init__(self, prop, obj):
            self.prop = prop
            self.obj = obj

        def __repr__(self):
            return "<{} of {!r}.{}: {!r}>".format(
                type(self).__qualname__,
                self.obj,
                self.prop.name,
                {game: getattr(slice, self.prop.name) for game, slice in self.obj._slices.items()},
            )


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


class Slice:
    is_slice = True

    def __init__(self):
        pass


class LocusMeta(type):
    # This is purely a backport of Python 3.6 functionality, and is taken from
    # PEP 487.  Once the minimum version supported is 3.6, this metaclass can
    # go away entirely.
    if not hasattr(object, '__init_subclass__'):
        def __new__(cls, *args, **kwargs):
            if len(args) != 3:
                return super().__new__(cls, *args)
            name, bases, ns = args
            init = ns.get('__init_subclass__')
            if isinstance(init, types.FunctionType):
                ns['__init_subclass__'] = classmethod(init)
            else:
                init = None
            self = super().__new__(cls, name, bases, ns)
            for k, v in self.__dict__.items():
                func = getattr(v, '__set_name__', None)
                if func is not None:
                    func(self, k)
            sup = super(self, self)
            if hasattr(sup, '__init_subclass__'):
                sup.__init_subclass__(**kwargs)
            return self


class Locus(metaclass=LocusMeta):
    _attributes = {}

    def __init_subclass__(cls, **kwargs):
        # super().__init_subclass__(**kwargs)
        cls._attributes = cls._attributes.copy()
        for key, value in cls.__dict__.items():
            if isinstance(value, _Attribute):
                cls._attributes[key] = value

    def __init__(self, **kwargs):
        cls = type(self)

        for key, value in kwargs.items():
            if not isinstance(getattr(cls, key, None), _Attribute):
                raise TypeError("Unexpected argument: {!r}".format(key))

            setattr(self, key, value)

    def __repr__(self):
        return "<{}: {}>".format(
            type(self).__qualname__,
            self.identifier,
        )


class VersionedLocus(Locus):
    def __init_subclass__(cls, **kwargs):
        super(VersionedLocus, cls).__init_subclass__(**kwargs)

        if not issubclass(cls, Slice):
            class Sliced(cls, Slice):
                base_class = cls

            # TODO this is a circular reference; do i care?
            cls.Sliced = Sliced

            cls._slices = {}

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


class Pokémon(VersionedLocus):
    # TODO version, language.  but those are kind of meta-fields; do they need
    # treating specially?
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

Pokemon = Pokémon


class Repository:
    def __init__(self):
        # type -> identifier -> object
        self.objects = defaultdict(lambda: {})
        # type -> property -> value -> list of objects
        self.index = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    def add(self, obj):
        # TODO this should be declared by the type itself, obviously
        cls = type(obj)
        # TODO both branches here should check for duplicates
        if isinstance(obj, Slice):
            cls = cls.base_class
            if obj.identifier not in self.objects[cls]:
                glom = cls()
                glom.identifier = obj.identifier
                self.objects[cls][obj.identifier] = glom
            else:
                glom = self.objects[cls][obj.identifier]
            # TODO this...  feels special-cased, but i guess, it is?
            glom._slices[obj.game] = obj
        else:
            self.objects[cls][obj.identifier] = obj
        # TODO this is more complex now that names are multi-language
        #self.index[cls][cls.name][obj.name].add(obj)

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
    cls = Pokemon.Sliced
    # TODO wrap with a writer thing?
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
    PATH = 'pokedex/data/ww-red/pokemon.yaml'
    with open(PATH) as f:
        all_pokemon = cam.load(f.read())
        for identifier, pokemon in all_pokemon.items():
            # TODO i don't reeeally like this, but configuring a camel to do it
            # is a little unwieldy
            pokemon.game = 'ww-red'
            # TODO this in particular seems extremely clumsy, but identifiers ARE fundamentally keys...
            pokemon.identifier = identifier

            repository.add(pokemon)
    PATH = 'pokedex/data/ww-blue/pokemon.yaml'
    with open(PATH) as f:
        all_pokemon = cam.load(f.read())
        for identifier, pokemon in all_pokemon.items():
            # TODO i don't reeeally like this, but configuring a camel to do it
            # is a little unwieldy
            pokemon.game = 'ww-blue'
            # TODO this in particular seems extremely clumsy, but identifiers ARE fundamentally keys...
            pokemon.identifier = identifier

            repository.add(pokemon)

    # TODO NEXT TODO
    # - how does the composite object work, exactly?  eevee.name.single?  eevee.name.latest?  no, name needs a language...
    # - but what about the vast majority of properties that are the same in every language and only vary by version?
    # - what about later games, where only some properties vary by language?  in the extreme case, xy/oras are single games!

    # TODO should this prepend the prefix automatically...  eh
    eevee = repository.fetch(Pokemon, 'pokemon.eevee')
    pprint(eevee)
    # TODO i feel like this should work: eevee = repository.Pokemon['eevee']
    print(eevee.name)
    print(eevee.types)


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
