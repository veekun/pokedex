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

        def __init__(cls, *args, **kwargs):
            super().__init__(*args)


class Locus(metaclass=LocusMeta):
    _attributes = {}

    def __init_subclass__(cls, *, sliced_by=(), **kwargs):
        # super().__init_subclass__(**kwargs)
        # TODO how...  do i...  make an attribute on the class that's not inherited by instances
        cls.sliced_by = sliced_by
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
            '???',  # TODO where is self.identifier assigned when writing?
        )


class VersionedLocus(Locus, sliced_by=['game']):
    def __init_subclass__(cls, **kwargs):
        super(VersionedLocus, cls).__init_subclass__(**kwargs)

        if not issubclass(cls, Slice):
            class Sliced(cls, Slice):
                base_class = cls

            # TODO this is a circular reference; do i care?
            cls.Sliced = Sliced

            cls._slices = {}


# ------------------------------------------------------------------------------
# Loci definitions

# TODO seems to me that each of these, regardless of whether they have any
# additional data attached or not, are restricted to a fixed extra-game-ular
# list of identifiers
Type = _ForwardDeclaration()
Stat = _ForwardDeclaration()
EggGroup = _ForwardDeclaration()
GrowthRate = _ForwardDeclaration()
Evolution = _ForwardDeclaration()
EncounterMap = _ForwardDeclaration()
MoveSet = _ForwardDeclaration()
Pokedex = _ForwardDeclaration()
PokédexColor = _ForwardDeclaration()
PokédexShape = _ForwardDeclaration()


class Ability(VersionedLocus):
    name = _Localized(str)
    flavor_text = _Localized(str)


class Item(VersionedLocus):
    name = _Localized(str)
    flavor_text = _Localized(str)
    price = _Value(int, min=0)
    # fling effect
    fling_power = _Value(int, min=0)
    # for berries only, but berries are a subset of items...
    # natural gift power
    # natural gift effect
    # natural gift type

    # category (fan classification)

    # short_effect
    # effect

    # TODO pocket?  they're different per game pair and i'm not sure where to find them

    # TODO berries have a bunch of stuff that regular items don't

    game_index = _Value(int)


class Pokémon(VersionedLocus):
    name = _Localized(str)

    # FIXME hackery to get forms working well enough to import back into veekun
    # later; this will need some cleaning up later, somehow
    form_base_species = _Value(str)
    form_identifier = _Value(str)
    form_number = _Value(int)
    form_appearances = _List(str)  # flavor only!
    form_name = _Localized(str)

    types = _List(Type, min=1, max=2)
    # FIXME how do i distinguish hidden ability?
    abilities = _List(Ability, min=1, max=3)
    base_stats = _Map(Stat, int)
    growth_rate = _Value(GrowthRate)
    base_experience = _Value(int, min=0, max=255)
    effort = _Map(Stat, int)
    capture_rate = _Value(int, min=0, max=255)
    base_happiness = _Value(int, min=0, max=255)
    held_items = _Map(Item, int)
    gender_rate = _Value(int)
    egg_groups = _List(EggGroup, min=1, max=2)
    hatch_counter = _Value(int, min=0, max=255)

    pokedex_numbers = _Map(Pokedex, int)

    # TODO family?
    evolutions = _List(Evolution)

    color = _Value(PokédexColor)
    shape = _Value(PokédexShape)
    genus = _Localized(str)
    flavor_text = _Localized(str)
    # TODO maybe want little wrapper types that can display as either imperial
    # or metric
    # TODO maybe also dump as metric rather than plain numbers
    # Inches and pounds are both defined as exact numbers of centimeters and
    # kilograms respectively, so this uses the largest units that can represent
    # both metric and imperial values as integers with no loss of precision:
    # myriameters (tenths of a millimeter) and micrograms.
    # Divide by 100 for centimeters, or by 254 for inches
    height = _Localized(int)
    # Divide by one billion for kilograms, or by 453592370 for pounds
    weight = _Localized(int)

    # TODO this belongs to a place, not to a pokemon
    #encounters = _Value(EncounterMap)

    # TODO having a custom type here is handy, but it's not a locus
    moves = _Value(MoveSet)

    # TODO should this be written in hex, maybe?
    game_index = _Value(int)

Pokemon = Pokémon


MoveEffect = _ForwardDeclaration()

class Move(VersionedLocus):
    game_index = _Value(int)

    name = _Localized(str)
    type = _Value(Type)
    power = _Value(int)
    pp = _Value(int)
    accuracy = _Value(int)
    priority = _Value(int)

    # FIXME should be enums
    damage_class = _Value(str)
    range = _Value(str)

    # FIXME oh goodness this is a self-referential one
    z_move = _Value(str)

    # FIXME this should be an enum really too
    effect = _Value(MoveEffect)
    # FIXME this is a bogus derived value now
    effect_chance = _Value(int)

    # NOTE: In the old schema, this stuff is in a separate table, since it's
    # not quite 100% reliable; in particular the lack of a value doesn't mean
    # that the effect cannot happen via code.  Also, consider Tri Attack, whose
    # inflicted ailments aren't listed here at all.  :(  Not sure what we
    # should do with it, since it's interesting for nerds but confusing for
    # everyone else.
    # FIXME this should probably be, like, _Set(MoveFlag)
    # FIXME also it doesn't dump using ? syntax like the yaml registry says
    flags = _Value(set)
    # FIXME these should be enums
    category = _Value(int)
    ailment = _Value(int)
    # FIXME this is bogus, it's per stat change
    # FIXME also, include stat changes?
    #stat_chance = _Value(int)
    # TODO i wonder if all these should be left out of the yaml if blank
    min_hits = _Value(int)
    max_hits = _Value(int)
    min_turns = _Value(int)
    max_turns = _Value(int)
    drain = _Value(int)
    healing = _Value(int)
    crit_rate = _Value(int)
    ailment_chance = _Value(int)
    flinch_chance = _Value(int)

    flavor_text = _Localized(str)


# ------------------------------------------------------------------------------
# The repository class, primary interface to the data

class LocusReader:
    def __init__(self, identifier, locus, **kwargs):
        self.identifier = identifier
        self.locus = locus
        # TODO what is kwargs here?  in this case we really want a slice, right...?

    def __getattr__(self):
        pass

    def __dir__(self):
        pass

class QuantumProperty:
    def __init__(self, qlocus, attr):
        self.qlocus = qlocus
        self.attr = attr

    def __repr__(self):
        return repr({key: getattr(locus, self.attr) for (key, locus) in self.qlocus.locus_map.items()})

class QuantumLocusReader:
    def __init__(self, identifier, locus_cls, locus_map):
        self.identifier = identifier
        self.locus_cls = locus_cls
        self.locus_map = locus_map

    def __getattr__(self, attr):
        return QuantumProperty(self, attr)

    def __repr__(self):
        return "<{}*: {}>".format(self.locus_cls.__name__, self.identifier)

class Repository:
    def __init__(self):
        # type -> identifier -> object
        self.objects = defaultdict(lambda: {})
        # type -> property -> value -> list of objects
        self.index = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    def add(self, identifier, locus, **kwargs):
        # TODO kwargs are used for slicing, e.g. a pokemon has a game, but this needs some rigid definition
        # TODO this should be declared by the type itself, obviously
        cls = type(locus)
        _basket = self.objects[cls].setdefault(identifier, {})
        # TODO so in the case of slicing (which is most loci), we don't
        # actually want to store a single object, but a sliced-up collection of
        # them (indicated by kwargs).  but then it's kind of up in the air what
        # we'll actually get /back/ when we go to fetch that object, and that
        # is unsatisfying to me.  i could make this a list of "baskets", which
        # may hold one object or a number of slices, but i'm not sure how i
        # feel about that; might have to just see how other loci work out.
        # TODO either way, this is very hardcoded and needs to not be
        _basket[kwargs['game']] = locus
        # TODO this is more complex now that names are multi-language
        #self.index[cls][cls.name][locus.name].add(locus)

    def fetch(self, cls, identifier):
        # TODO wrap in a...  multi-thing
        #return self.objects[cls][identifier]
        return QuantumLocusReader(identifier, cls, self.objects[cls][identifier])


# TODO clean this garbage up -- better way of iterating the type, actually work
# for something other than pokemon...  the only part that varies in the dumper
# is the tag, and the only part that varies in the loader is the class (which
# is determined from the tag)
POKEDEX_TYPES = camel.CamelRegistry(tag_prefix='tag:veekun.com,2005:pokedex/', tag_shorthand='!dex!')

@POKEDEX_TYPES.dumper(Pokémon, 'pokemon', version=None, inherit=True)
def _dump_locus(locus):
    data = OrderedDict()
    attrs = [(key, attr) for (key, attr) in type(locus).__dict__.items() if isinstance(attr, _Attribute)]
    attrs.sort(key=lambda kv: kv[1]._creation_order)

    for key, attr in attrs:
        if key in locus.__dict__:
            data[key.replace('_', '-')] = locus.__dict__[key]

    return data

def _make_locus_loader(cls):
    def load_locus(data, version):
        # TODO wrap with a writer thing?
        obj = cls()
        for key, value in data.items():
            key = key.replace('-', '_')
            assert hasattr(cls, key)
            setattr(obj, key, value)

        return obj
    return load_locus

POKEDEX_TYPES.loader('pokemon', version=None)(_make_locus_loader(Pokémon))

POKEDEX_TYPES.dumper(Move, 'move', version=None, inherit=True)(_dump_locus)
POKEDEX_TYPES.loader('move', version=None)(_make_locus_loader(Move))

POKEDEX_TYPES.dumper(Ability, 'ability', version=None, inherit=True)(_dump_locus)
POKEDEX_TYPES.loader('ability', version=None)(_make_locus_loader(Ability))

POKEDEX_TYPES.dumper(Item, 'item', version=None, inherit=True)(_dump_locus)
POKEDEX_TYPES.loader('item', version=None)(_make_locus_loader(Item))


def load_repository():
    repository = Repository()

    # just testing for now
    cam = camel.Camel([POKEDEX_TYPES])
    for game in ('jp-red', 'jp-green', 'jp-blue', 'ww-red', 'ww-blue', 'yellow'):
        path = "pokedex/data/{}/pokemon.yaml".format(game)
        with open(path) as f:
            all_pokemon = cam.load(f.read())
            for identifier, pokemon in all_pokemon.items():
                repository.add(identifier, pokemon, game=game)

    return repository, all_pokemon


def _temp_main():
    repository, all_pokemon = load_repository()

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
