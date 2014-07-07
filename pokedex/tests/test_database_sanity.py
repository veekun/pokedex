import pytest
parametrize = pytest.mark.parametrize

from sqlalchemy.orm import aliased, joinedload, lazyload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func

from pokedex.db import connect, tables, util

def test_encounter_slots(session):
    """Encounters have a version, which has a version group; encounters also
    have an encounter_slot, which has a version group.  The two version
    groups should match, universally.
    """

    version_group_a = aliased(tables.VersionGroup)
    version_group_b = aliased(tables.VersionGroup)

    sanity_q = session.query(tables.Encounter) \
        .join((tables.EncounterSlot, tables.Encounter.slot)) \
        .join((version_group_a, tables.EncounterSlot.version_group)) \
        .join((tables.Version, tables.Encounter.version)) \
        .join((version_group_b, tables.Version.version_group)) \
        .filter(version_group_a.id != version_group_b.id)

    # Encounter slots all match the encounters they belong to
    assert sanity_q.count() == 0

@parametrize('cls', tables.mapped_classes)
def test_nonzero_autoincrement_ids(session, cls):
    """Check that autoincrementing ids don't contain zeroes

    MySQL doesn't like these, see e.g. bug #580
    """
    if 'id' not in cls.__table__.c:
        return
    if not cls.__table__.c.id.autoincrement:
        return

    try:
        util.get(session, cls, id=0)
    except NoResultFound:
        pass
    else:
        pytest.fail("No zero id in %s" % cls.__name__)

def test_unique_form_order(session):
    """Check that tone PokemonForm.order value isn't used for more species"""

    species_by_form_order = {}

    query = session.query(tables.PokemonForm)
    query = query.options(joinedload('pokemon.species'))

    for form in query:
        print form.name
        try:
            previous_species = species_by_form_order[form.order]
        except KeyError:
            species_by_form_order[form.order] = form.species
        else:
            assert previous_species == form.species, (
                "PokemonForm.order == %s is used for %s and %s" % (
                        form.order,
                        species_by_form_order[form.order].name,
                        form.species.name))

def test_default_forms(session):
    """Check that each pokemon has one default form and each species has one
    default pokemon."""

    q = session.query(tables.Pokemon)
    q = q.join(tables.PokemonForm)
    q = q.filter(tables.PokemonForm.is_default==True)
    q = q.options(lazyload('*'))
    q = q.group_by(tables.Pokemon)
    q = q.add_columns(func.count(tables.PokemonForm.id))

    for pokemon, num_default_forms in q:
        if num_default_forms == 0:
            pytest.fail("pokemon %s has no default forms" % pokemon.name)
        elif num_default_forms > 1:
            pytest.fail("pokemon %s has %d default forms" % (pokemon.name, num_default_forms))

    q = session.query(tables.PokemonSpecies)
    q = q.join(tables.Pokemon)
    q = q.filter(tables.Pokemon.is_default==True)
    q = q.options(lazyload('*'))
    q = q.group_by(tables.PokemonSpecies)
    q = q.add_columns(func.count(tables.Pokemon.id))

    for species, num_default_pokemon in q:
        if num_default_pokemon == 0:
            pytest.fail("species %s has no default pokemon" % species.name)
        elif num_default_pokemon > 1:
            pytest.fail("species %s has %d default pokemon" % (species.name, num_default_pokemon))
