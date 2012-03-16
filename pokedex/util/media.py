
"""Media accessors

All media accessor __init__s take a `root` argument, which should be a path
to the root of the media directory.
Alternatively, `root` can be a custom MediaFile subclass.

Most __init__s take an ORM object as a second argument.

Their various methods take a number of arguments specifying exactly which
file you want (such as the female sprite, backsprite, etc.).
ValueError is raised when the specified file cannot be found.

The accessors use fallbacks: for example Bulbasaur's males and females look the
same, so if you request Bulbasaur's female sprite, it will give you the common
image. Or for a Pokemon without individual form sprites, you will get the
common base sprite. Or for versions witout shiny Pokemon, you will always
get the non-shiny version (that's how shiny Pokemon looked there!).
However arguments such as `animated` don't use fallbacks.
You can set `strict` to True to disable these fallbacks and cause ValueError
to be raised when the exact specific file you asked for is not found. This is
useful for listing non-duplicate sprites, for example.

Use keyword arguments when calling the media-getting methods, unless noted
otherwise.

The returned "file" objects have useful attributes like relative_path,
path, and open().

All images are in the PNG format, except animations (GIF). All sounds are OGGs.
"""

import os
from functools import partial

class MediaFile(object):
    """Represents a file: picture, sound, etc.

    Attributes:
    path_elements: List of directory/file names that make up relative_path
    relative_path: Filesystem path relative to the root
    path: Absolute path to the file

    exists: True if the file exists

    media_available: false if no media is available at the given root.

    open(): Open the file
    """
    def __init__(self, root, *path_elements):
        self.path_elements = path_elements
        self.root = root

    @property
    def relative_path(self):
        return os.path.join(*self.path_elements)

    @property
    def path(self):
        return os.path.join(self.root, *self.path_elements)

    def open(self):
        """Open this file for reading, in the appropriate mode (i.e. binary)
        """
        return open(self.path, 'rb')

    @property
    def exists(self):
        return os.path.exists(self.path)

    @property
    def media_available(self):
        return os.path.isdir(self.root)

    def __eq__(self, other):
        return self.path == other.path

    def __ne__(self, other):
        return self.path != other.path

    def __str__(self):
        return '<Pokedex file %s>' % self.relative_path

class BaseMedia(object):
    def __init__(self, root):
        if isinstance(root, basestring):
            self.file_class = partial(MediaFile, root)
        else:
            self.file_class = root

    @property
    def available(self):
        return self.file_class().media_available

    def from_path_elements(self, path_elements, basename, extension,
            surely_exists=False):
        filename = basename + extension
        path_elements = [self.toplevel_dir] + path_elements + [filename]
        mfile = self.file_class(*path_elements)
        if surely_exists or mfile.exists:
            return mfile
        else:
            raise ValueError('File %s not found' % mfile.path)

class _BasePokemonMedia(BaseMedia):
    toplevel_dir = 'pokemon'
    has_gender_differences = False
    is_species = False
    is_proper = False
    introduced_in = 0

    # Info about of what's inside the pokemon main sprite directories, so we
    # don't have to check directory existence all the time.
    _pokemon_sprite_info = {
            'red-blue': (1, set('back gray'.split())),
            'red-green': (1, set('back gray'.split())),
            'yellow': (1, set('back gray gbc'.split())),
            'gold': (2, set('back shiny'.split())),
            'silver': (2, set('back shiny'.split())),
            'crystal': (2, set('animated back shiny'.split())),
            'ruby-sapphire': (3, set('back shiny'.split())),
            'emerald': (3, set('animated back shiny frame2'.split())),
            'firered-leafgreen': (3, set('back shiny'.split())),
            'diamond-pearl': (4, set('back shiny female frame2'.split())),
            'platinum': (4, set('back shiny female frame2'.split())),
            'heartgold-soulsilver': (4, set('back shiny female frame2'.split())),
            'black-white': (5, set('back shiny female'.split())),
        }

    def __init__(self, root, species_id, form_postfix=None):
        BaseMedia.__init__(self, root)
        self.species_id = str(species_id)
        self.form_postfix = form_postfix

    def _get_file(self, path_elements, extension, strict, surely_exists=False):
        basename = str(self.species_id)
        if self.form_postfix:
            fullname = basename + self.form_postfix
            try:
                return self.from_path_elements(
                        path_elements, fullname, extension,
                        surely_exists=surely_exists)
            except ValueError:
                if strict:
                    raise
        return self.from_path_elements(path_elements, basename, extension,
                surely_exists=surely_exists)

    def sprite(self,
            version='black-white',

            # The media directories are in this order:
            animated=False,
            back=False,
            color=None,
            shiny=False,
            female=False,
            frame=None,

            strict=False,
        ):
        """Get a main sprite sprite for a pokemon.

        Everything except version should be given as a keyword argument.

        Either specify version as an ORM object, or give the version path as
        a string (which is the only way to get 'red-green'). Leave the default
        for the latest version.

        animated: get a GIF animation (currently Crystal & Emerald only)
        back: get a backsprite instead of a front one
        color: can be 'color' (RGBY only) or 'gbc' (Yellow only)
        shiny: get a shiny sprite. In old versions, gives a normal sprite unless
            `strict` is set
        female: get a female sprite instead of male. For pokemon with no sexual
            dimorphism, gets the common sprite unless `strict` is set.
        frame: set to 2 to get the second frame of the animation
            (Emerald, DPP, and HG/SS only)

        If the sprite is not found, raise a ValueError.
        """
        if isinstance(version, basestring):
            version_dir = version
            try:
                generation, info = self._pokemon_sprite_info[version_dir]
            except KeyError:
                raise ValueError('Version directory %s not found', version_dir)
        else:
            version_dir = version.identifier
            try:
                generation, info = self._pokemon_sprite_info[version_dir]
            except KeyError:
                version_group = version.version_group
                version_dir = '-'.join(
                        v.identifier for v in version_group.versions)
                try:
                    generation, info = self._pokemon_sprite_info[version_dir]
                except KeyError:
                    raise ValueError('Version directory %s not found', version_dir)
        if generation < self.introduced_in:
            raise ValueError("Pokemon %s didn't exist in %s" % (
                    self.species_id, version_dir))
        path_elements = ['main-sprites', version_dir]
        if animated:
            if 'animated' not in info:
                raise ValueError("No animated sprites for %s" % version_dir)
            path_elements.append('animated')
            extension = '.gif'
        else:
            extension = '.png'
        if back:
            if version_dir == 'emerald':
                # Emerald backsprites are the same as ruby/sapphire
                if strict:
                    raise ValueError("Emerald uses R/S backsprites")
                if animated:
                    raise ValueError("No animated backsprites for Emerald")
                path_elements[1] = version_dir = 'ruby-sapphire'
            if version_dir == 'crystal' and animated:
                raise ValueError("No animated backsprites for Crystal")
            path_elements.append('back')
        if color == 'gray':
            if 'gray' not in info:
                raise ValueError("No grayscale sprites for %s" % version_dir)
            path_elements.append('gray')
        elif color == 'gbc':
            if 'gbc' not in info:
                raise ValueError("No GBC sprites for %s" % version_dir)
            path_elements.append('gbc')
        elif color:
            raise ValueError("Unknown color scheme: %s" % color)
        if shiny:
            if 'shiny' in info:
                path_elements.append('shiny')
            elif strict:
                raise ValueError("No shiny sprites for %s" % version_dir)
        if female:
            female_sprite = self.has_gender_differences
            # Chimecho's female back frame 2 sprite has one hand in
            # a slightly different pose, in Platinum and HGSS
            # (we have duplicate sprites frame 1, for convenience)
            if self.species_id == '358' and back and version_dir in (
                    'platinum', 'heartgold-soulsilver'):
                female_sprite = True
            female_sprite = female_sprite and 'female' in info
            if female_sprite:
                path_elements.append('female')
            elif strict:
                raise ValueError(
                    'Pokemon %s has no gender differences' % self.species_id)
        if not frame or frame == 1:
            pass
        elif frame == 2:
            if 'frame2' in info:
                path_elements.append('frame%s' % frame)
            else:
                raise ValueError("No frame 2 for %s" % version_dir)
        else:
            raise ValueError("Bad frame %s" % frame)
        return self._get_file(path_elements, extension, strict=strict,
                # Avoid a stat in the common case
                surely_exists=(self.is_species and version_dir == 'black-white'
                    and not back and not female))

    def _maybe_female(self, path_elements, female, strict):
        if female:
            if self.has_gender_differences:
                elements = path_elements + ['female']
                try:
                    return self._get_file(elements, '.png', strict=strict)
                except ValueError:
                    if strict:
                        raise
            elif strict:
                raise ValueError(
                    'Pokemon %s has no gender differences' % self.species_id)
        return self._get_file(path_elements, '.png', strict=strict)

    def icon(self, female=False, strict=False):
        """Get the Pokemon's menu icon"""
        return self._maybe_female(['icons'], female, strict)

    def sugimori(self, female=False, strict=False):
        """Get the Pokemon's official art, drawn by Ken Sugimori"""
        return self._maybe_female(['sugimori'], female, strict)

    def overworld(self,
            direction='down',
            shiny=False,
            female=False,
            frame=1,
            strict=False,
        ):
        """Get an overworld sprite

        direction: 'up', 'down', 'left', or 'right'
        shiny: true for a shiny sprite
        female: true for female sprite (or the common one for both M & F)
        frame: 2 for the second animation frame

        strict: disable fallback for `female`
        """
        path_elements = ['overworld']
        if shiny:
            path_elements.append('shiny')
        if female:
            if self.has_gender_differences:
                path_elements.append('female')
            elif strict:
                raise ValueError('No female overworld sprite')
            else:
                female = False
        path_elements.append(direction)
        if frame and frame > 1:
            path_elements.append('frame%s' % frame)
        try:
            return self._get_file(path_elements, '.png', strict=strict)
        except ValueError:
            if female and not strict:
                path_elements.remove('female')
                return self._get_file(path_elements, '.png', strict=strict)
            else:
                raise

    def footprint(self, strict=False):
        """Get the Pokemon's footprint"""
        return self._get_file(['footprints'], '.png', strict=strict)

    def trozei(self, strict=False):
        """Get the Pokemon's animated Trozei sprite"""
        return self._get_file(['trozei'], '.gif', strict=strict)

    def cry(self, strict=False):
        """Get the Pokemon's cry"""
        return self._get_file(['cries'], '.ogg', strict=strict)

    def cropped_sprite(self, strict=False):
        """Get the Pokemon's cropped sprite"""
        return self._get_file(['cropped'], '.png', strict=strict)

class PokemonFormMedia(_BasePokemonMedia):
    """Media related to a PokemonForm
    """
    is_proper = True

    def __init__(self, root, pokemon_form):
        species_id = pokemon_form.species.id
        if pokemon_form.form_identifier:
            form_postfix = '-' + pokemon_form.form_identifier
        else:
            form_postfix = None
        _BasePokemonMedia.__init__(self, root, species_id, form_postfix)
        self.form = pokemon_form
        species = pokemon_form.species
        self.has_gender_differences = species.has_gender_differences
        self.introduced_in = pokemon_form.version_group.generation_id

class PokemonSpeciesMedia(_BasePokemonMedia):
    """Media related to a PokemonSpecies
    """
    is_species = True
    is_proper = True

    def __init__(self, root, species):
        _BasePokemonMedia.__init__(self, root, species.id)
        self.has_gender_differences = species.has_gender_differences
        self.introduced_in = species.generation_id

class UnknownPokemonMedia(_BasePokemonMedia):
    """Media related to the unknown Pokemon ("?")

    Note that not a lot of files are available for it.
    """
    def __init__(self, root):
        _BasePokemonMedia.__init__(self, root, '0')

class EggMedia(_BasePokemonMedia):
    """Media related to a pokemon egg

    Note that not a lot of files are available for these.

    Give a Manaphy as `species` to get the Manaphy egg.
    """
    def __init__(self, root, species=None):
        if species and species.identifier == 'manaphy':
            postfix = '-manaphy'
        else:
            postfix = None
        _BasePokemonMedia.__init__(self, root, 'egg', postfix)

class SubstituteMedia(_BasePokemonMedia):
    """Media related to the Substitute sprite

    Note that not a lot of files are available for Substitute.
    """
    def __init__(self, root):
        _BasePokemonMedia.__init__(self, root, 'substitute')

class _BaseItemMedia(BaseMedia):
    toplevel_dir = 'items'
    def underground(self, rotation=0):
        """Get the item's sprite as it appears in the Sinnoh underground

        Rotation can be 0, 90, 180, or 270.
        """
        if rotation:
            basename = self.identifier + '-%s' % rotation
        else:
            basename = self.identifier
        return self.from_path_elements(['underground'], basename, '.png')

class ItemMedia(_BaseItemMedia):
    """Media related to an item
    """
    def __init__(self, root, item):
        _BaseItemMedia.__init__(self, root)
        self.item = item
        self.identifier = item.identifier

    def sprite(self, version=None):
        """Get the item's sprite

        If version is not given, use the latest version.
        """
        identifier = self.identifier
        # Handle machines
        # We check the identifier, so that we don't query the machine
        # information for any item.
        if identifier.startswith(('tm', 'hm')):
            try:
                int(identifier[2:])
            except ValueError:
                # Not really a TM/HM
                pass
            else:
                machines = self.item.machines
                if version:
                    try:
                        machine = [
                                m for m in machines
                                if m.version_group == version.version_group
                            ][0]
                    except IndexError:
                        raise ValueError("%s doesn't exist in %s" % (
                                identifier, version.identifier))
                else:
                    # They're ordered, so get the last one
                    machine = machines[-1]
                type_identifier = machine.move.type.identifier
                identifier = identifier[:2] + '-' + type_identifier
        elif identifier.startswith('data-card-'):
            try:
                int(identifier[10:])
            except ValueError:
                # Not a real data card???
                pass
            else:
                identifier = 'data-card'
        if version is not None:
            generation_id = version.generation.id
            if generation_id <= 3 and identifier == 'dowsing-mchn':
                identifier = 'itemfinder'
            try:
                gen = 'gen%s' % generation_id
                return self.from_path_elements([gen], identifier, '.png')
            except ValueError:
                pass
        return self.from_path_elements([], identifier, '.png',
                surely_exists=True)

    def underground(self, rotation=0):
        """Get the item's sprite as it appears in the Sinnoh underground

        Rotation can be 0, 90, 180, or 270.
        """
        if not self.item.appears_underground:
            raise ValueError("%s doesn't appear underground" % self.identifier)
        return super(ItemMedia, self).underground(rotation=rotation)

    def berry_image(self):
        """Get a berry's big sprite
        """
        if not self.item.berry:
            raise ValueError("%s is not a berry" % self.identifier)
        return self.from_path_elements(['berries'], self.identifier, '.png')

class UndergroundRockMedia(_BaseItemMedia):
    """Media related to a rock in the Sinnoh underground

    rock_type can be one of: i, ii, o, o-big, s, t, z
    """
    def __init__(self, root, rock_type):
        _BaseItemMedia.__init__(self, root)
        self.identifier = 'rock-%s' % rock_type

class UndergroundSphereMedia(_BaseItemMedia):
    """Media related to a sphere in the Sinnoh underground

    color can be one of: red, blue, green, pale, prism
    """
    def __init__(self, root, color, big=False):
        _BaseItemMedia.__init__(self, root)
        self.identifier = '%s-sphere' % color
        if big:
            self.identifier += '-big'

class _SimpleIconMedia(BaseMedia):
    def __init__(self, root, thing):
        BaseMedia.__init__(self, root)
        self.identifier = thing.identifier

    def icon(self):
        return self.from_path_elements([], self.identifier, '.png')

class DamageClassMedia(_SimpleIconMedia):
    toplevel_dir = 'damage-classes'

class HabitatMedia(_SimpleIconMedia):
    toplevel_dir = 'habitats'

class ShapeMedia(_SimpleIconMedia):
    toplevel_dir = 'shapes'

class ItemPocketMedia(_SimpleIconMedia):
    toplevel_dir = 'item-pockets'
    def icon(self, selected=False):
        if selected:
            return self.from_path_elements(
                    ['selected'], self.identifier, '.png')
        else:
            return self.from_path_elements([], self.identifier, '.png')

class _LanguageIconMedia(_SimpleIconMedia):
    def icon(self, lang='en'):
        return self.from_path_elements([lang], self.identifier, '.png')

class ContestTypeMedia(_LanguageIconMedia):
    toplevel_dir = 'contest-types'

class TypeMedia(_LanguageIconMedia):
    toplevel_dir = 'types'

''' XXX: No accessors for:
chrome
fonts
ribbons
'''
