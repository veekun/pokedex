import pytest
parametrize = pytest.mark.parametrize

from collections import Counter
import re

from sqlalchemy.orm import aliased, joinedload, lazyload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func

from pokedex.db import tables, util

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

def test_encounter_regions(session):
    """Check that encounter locations match the region of the game they're from.
    """

    sanity_q = session.query(tables.Encounter) \
        .join((tables.Version, tables.Encounter.version)) \
        .join((tables.VersionGroup, tables.Version.version_group)) \
        .join((tables.LocationArea, tables.Encounter.location_area)) \
        .join((tables.Location, tables.LocationArea.location)) \
        .join((tables.Region, tables.Location.region)) \
        .filter(~tables.VersionGroup.version_group_regions.any(tables.VersionGroupRegion.region_id == tables.Region.id))

    for e in sanity_q.limit(20):
        acceptable_regions = " or ".join(r.identifier for r in e.version.version_group.regions)
        if e.location_area.location.region is not None:
            print("{e} ({e.pokemon.identifier}, {e.slot.method.identifier}, {e.version.identifier}) is in {e.location_area.location.region.identifier} ({e.location_area.location.identifier}) but should be in {acceptable_regions} ({e.version.identifier})".format(e=e, acceptable_regions=acceptable_regions))
        else:
            print("{e} ({e.pokemon.identifier}, {e.slot.method.identifier}, {e.version.identifier}) is in a pseudo-location ({e.location_area.location.identifier}) that is not part of any region, but should be in {acceptable_regions} ({e.version.identifier})".format(e=e, acceptable_regions=acceptable_regions))

    # Encounter regions match the games they belong to
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
    """Check that one PokemonForm.order value isn't used for more species"""

    species_by_form_order = {}

    query = session.query(tables.PokemonForm)
    query = query.options(joinedload('pokemon.species'))

    for form in query:
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

def test_pokedex_numbers(session):
    """Check that pokedex numbers are contiguous (there are no gaps)"""

    dex_query = session.query(tables.Pokedex).order_by(tables.Pokedex.id)
    failed = False
    for dex in dex_query:
        query = session.query(tables.PokemonDexNumber.pokedex_number).filter_by(pokedex_id=dex.id)
        numbers = set([x[0] for x in query.all()])
        for i in range(1, max(numbers)):
            if i not in numbers:
                print("number {n} is missing from the {dex.name} pokedex".format(n=i, dex=dex))
                failed = True

    assert not failed, "missing pokedex numbers"


def test_default_forms(session):
    """Check that each pokemon has one default form and each species has one
    default pokemon."""

    q = session.query(tables.Pokemon)
    # TODO: could use table.Pokemon.forms.and_: https://docs.sqlalchemy.org/en/14/orm/queryguide.html#orm-queryguide-join-on-augmented
    q = q.outerjoin(tables.PokemonForm, (tables.PokemonForm.pokemon_id == tables.Pokemon.id) & (tables.PokemonForm.is_default==True))
    q = q.options(lazyload('*'))
    q = q.group_by(tables.Pokemon)
    q = q.add_columns(func.count(tables.PokemonForm.id))

    for pokemon, num_default_forms in q:
        if num_default_forms == 0:
            pytest.fail("pokemon %s has no default forms" % pokemon.name)
        elif num_default_forms > 1:
            pytest.fail("pokemon %s has %d default forms" % (pokemon.name, num_default_forms))

    q = session.query(tables.PokemonSpecies)
    q = q.outerjoin(tables.Pokemon, (tables.Pokemon.species_id == tables.PokemonSpecies.id) & (tables.Pokemon.is_default==True))
    q = q.options(lazyload('*'))
    q = q.group_by(tables.PokemonSpecies)
    q = q.add_columns(func.count(tables.Pokemon.id))

    for species, num_default_pokemon in q:
        if num_default_pokemon == 0:
            pytest.fail("species %s has no default pokemon" % species.name)
        elif num_default_pokemon > 1:
            pytest.fail("species %s has %d default pokemon" % (species.name, num_default_pokemon))

ROUTE_RE = re.compile(u'route-\\d+')

def test_location_identifiers(session):
    """Check that location identifiers for some common locations are prefixed
    with the region name, ala kalos-route-2"""

    q = session.query(tables.Location)
    q = q.join(tables.Region)
    q = q.options(lazyload('*'))
    for loc in q:
        if (loc.identifier in [u'victory-road', u'pokemon-league', u'safari-zone']
                or ROUTE_RE.match(loc.identifier)):
            if loc.region:
                region = loc.region.identifier.lower()
                suggested_identifier = region + "-" + loc.identifier
                pytest.fail("location %d: identifier %s should be prefixed with its region (e.g. %s)" % (loc.id, loc.identifier, suggested_identifier))
            else:
                pytest.fail("location %d: identifier %s should be prefixed with its region" % (loc.id, loc.identifier))
