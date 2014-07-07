"""Test the media accessors.

If run directly from the command line, also tests the accessors and the names
of all the media by getting just about everything in a naive brute-force way.
This, of course, takes a lot of time to run.
"""

import pytest

import os
import re

from pokedex.db import tables
from pokedex.util import media

path_re = re.compile('^[-a-z0-9./]*$')

def test_totodile(session, media_root):
    """Totodile's female sprite -- same as male"""
    totodile = session.query(tables.PokemonSpecies).filter_by(identifier=u'totodile').one()
    accessor = media.PokemonSpeciesMedia(media_root, totodile)
    assert accessor.sprite() == accessor.sprite(female=True)

def test_chimecho(session, media_root):
    """Chimecho's Platinum female backsprite -- diffeent from male"""
    chimecho = session.query(tables.PokemonSpecies).filter_by(identifier=u'chimecho').one()
    accessor = media.PokemonSpeciesMedia(media_root, chimecho)
    male = accessor.sprite('platinum', back=True, frame=2)
    female = accessor.sprite('platinum', back=True, female=True, frame=2)
    assert male != female

def test_venonat(session, media_root):
    """Venonat's shiny Yellow sprite -- same as non-shiny"""
    venonat = session.query(tables.PokemonSpecies).filter_by(identifier=u'venonat').one()
    accessor = media.PokemonSpeciesMedia(media_root, venonat)
    assert accessor.sprite('yellow') == accessor.sprite('yellow', shiny=True)

@pytest.mark.xfail
def test_arceus_icon(session, media_root):
    """Arceus normal-form icon -- same as base icon"""
    arceus = session.query(tables.PokemonSpecies).filter_by(identifier=u'arceus').one()
    accessor = media.PokemonSpeciesMedia(media_root, arceus)
    normal_arceus = [f for f in arceus.forms if f.form_identifier == 'normal'][0]
    normal_accessor = media.PokemonFormMedia(media_root, normal_arceus)
    assert accessor.icon() == normal_accessor.icon()

def test_strict_castform(session, media_root):
    """Castform rainy form overworld with strict -- unavailable"""
    with pytest.raises(ValueError):
        castform = session.query(tables.PokemonSpecies).filter_by(identifier=u'castform').first()
        rainy_castform = [f for f in castform.forms if f.form_identifier == 'rainy'][0]
        print rainy_castform
        rainy_castform = media.PokemonFormMedia(media_root, rainy_castform)
        rainy_castform.overworld('up', strict=True)

def test_strict_exeggcute(session, media_root):
    """Exeggcutes's female backsprite, with strict -- unavailable"""
    with pytest.raises(ValueError):
        exeggcute = session.query(tables.PokemonSpecies).filter_by(identifier=u'exeggcute').one()
        accessor = media.PokemonSpeciesMedia(media_root, exeggcute)
        accessor.sprite(female=True, strict=True)



def get_all_filenames(media_root):
    all_filenames = set()

    for dirpath, dirnames, filenames in os.walk(media_root):
        dirnames[:] = [dirname for dirname in dirnames if dirname != '.git']
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            assert path_re.match(path), path
            all_filenames.add(path)

    return all_filenames

def hit(filenames, method, *args, **kwargs):
    """
    Run the given accessor method with args & kwargs; if found remove the
    result path from filenames and return True, else return False.
    """
    try:
        medium = method(*args, **kwargs)
        #print 'Hit', medium.relative_path
        assert medium.exists
    except ValueError, e:
        #print 'DNF', e
        return False
    except:
        print 'Error while processing', method, args, kwargs
        raise
    try:
        filenames.remove(medium.path)
    except KeyError:
        pass
    return True

@pytest.mark.slow
@pytest.mark.xfail
def test_get_everything(session, media_root):
    """
    For every the accessor method, loop over the Cartesian products of all
    possible values for its arguments.
    Make sure we get every file in the repo, and that we get a file whenever
    we should.

    Well, there are exceptions of course.
    """

    versions = list(session.query(tables.Version).all())
    versions.append('red-green')

    # We don't have any graphics for Colosseum or XD
    versions.remove(session.query(tables.Version).filter_by(identifier=u'colosseum').one())
    versions.remove(session.query(tables.Version).filter_by(identifier=u'xd').one())

    black = session.query(tables.Version).filter_by(identifier=u'black').one()

    filenames = get_all_filenames(media_root)

    # Some small stuff first

    for damage_class in session.query(tables.MoveDamageClass).all():
        assert hit(filenames, media.DamageClassMedia(media_root, damage_class).icon)

    for habitat in session.query(tables.PokemonHabitat).all():
        assert hit(filenames, media.HabitatMedia(media_root, habitat).icon)

    for shape in session.query(tables.PokemonShape).all():
        assert hit(filenames, media.ShapeMedia(media_root, shape).icon)

    for item_pocket in session.query(tables.ItemPocket).all():
        assert hit(filenames, media.ItemPocketMedia(media_root, item_pocket).icon)
        assert hit(filenames, media.ItemPocketMedia(media_root, item_pocket).icon, selected=True)

    for contest_type in session.query(tables.ContestType).all():
        assert hit(filenames, media.ContestTypeMedia(media_root, contest_type).icon)

    for elemental_type in session.query(tables.Type).all():
        assert hit(filenames, media.TypeMedia(media_root, elemental_type).icon)

    # Items
    versions_for_items = [
        None,
        session.query(tables.Version).filter_by(identifier='emerald').one(),
    ]

    for item in session.query(tables.Item).all():
        accessor = media.ItemMedia(media_root, item)
        assert hit(filenames, accessor.berry_image) or not item.berry
        for rotation in (0, 90, 180, 270):
            assert hit(filenames, accessor.underground, rotation=rotation) or (
                    not item.appears_underground or rotation)
        for version in versions_for_items:
            success = hit(filenames, accessor.sprite, version=version)
            if version is None:
                assert success

    for color in 'red green blue pale prism'.split():
        for big in (True, False):
            accessor = media.UndergroundSphereMedia(media_root, color=color, big=big)
            assert hit(filenames, accessor.underground)

    for rock_type in 'i ii o o-big s t z'.split():
        accessor = media.UndergroundRockMedia(media_root, rock_type)
        for rotation in (0, 90, 180, 270):
            success = hit(filenames, accessor.underground, rotation=rotation)
            assert success or rotation

    # Pokemon!
    accessors = []

    accessors.append(media.UnknownPokemonMedia(media_root))
    accessors.append(media.EggMedia(media_root))
    manaphy = session.query(tables.PokemonSpecies).filter_by(identifier=u'manaphy').one()
    accessors.append(media.EggMedia(media_root, manaphy))
    accessors.append(media.SubstituteMedia(media_root))

    for form in session.query(tables.PokemonForm).all():
        accessors.append(media.PokemonFormMedia(media_root, form))

    for pokemon in session.query(tables.PokemonSpecies).all():
        accessors.append(media.PokemonSpeciesMedia(media_root, pokemon))

    for accessor in accessors:
        assert hit(filenames, accessor.footprint) or not accessor.is_proper
        assert hit(filenames, accessor.trozei) or not accessor.is_proper or (
                accessor.introduced_in > 3)
        assert hit(filenames, accessor.cry) or not accessor.is_proper
        assert hit(filenames, accessor.cropped_sprite) or not accessor.is_proper
        for female in (True, False):
            assert hit(filenames, accessor.icon, female=female) or not accessor.is_proper
            assert hit(filenames, accessor.sugimori, female=female) or (
                    not accessor.is_proper or int(accessor.species_id) >= 647)
            for shiny in (True, False):
                for frame in (1, 2):
                    for direction in 'up down left right'.split():
                        assert hit(filenames, accessor.overworld,
                                direction=direction,
                                shiny=shiny,
                                female=female,
                                frame=frame,
                            ) or not accessor.is_proper or (
                                    accessor.introduced_in > 4)
                    for version in versions:
                        for animated in (True, False):
                            for back in (True, False):
                                for color in (None, 'gray', 'gbc'):
                                    success = hit(filenames,
                                            accessor.sprite,
                                            version,
                                            animated=animated,
                                            back=back,
                                            color=color,
                                            shiny=shiny,
                                            female=female,
                                            frame=frame,
                                        )
                                    if (version == black and not animated
                                        and not back and not color and not
                                        shiny and not female and
                                        frame == 1):
                                        # All pokemon are in Black
                                        assert success or not accessor.is_proper
                                    if (str(accessor.species_id) == '1'
                                        and not animated and not color and
                                        frame == 1):
                                        # Bulbasaur is in all versions
                                        assert success

    # Remove exceptions
    exceptions = [os.path.join(media_root, dirname) for dirname in
            'chrome fonts ribbons'.split()]
    exceptions.append(os.path.join(media_root, 'items', 'hm-'))
    exceptions = tuple(exceptions)

    unaccessed_filenames = set(filenames)
    for filename in filenames:
        if filename.startswith(exceptions):
            unaccessed_filenames.remove(filename)
        if filename.endswith('-beta.png'):
            unaccessed_filenames.remove(filename)

    if unaccessed_filenames:
        print 'Unaccessed files:'
        for filename in unaccessed_filenames:
            print filename

    assert unaccessed_filenames == set()

    return (not filenames)
