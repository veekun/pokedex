from nose.tools import *
import unittest
from sqlalchemy.orm import aliased

from pokedex.db import connect, tables

def test_encounter_slots():
    # Encounters have a version, which has a version group; encounters also
    # have an encounter_slot, which has a version group.  The two version
    # groups should match, universally.
    session = connect()

    version_group_a = aliased(tables.VersionGroup)
    version_group_b = aliased(tables.VersionGroup)

    sanity_q = session.query(tables.Encounter) \
        .join((tables.EncounterSlot, tables.Encounter.slot)) \
        .join((version_group_a, tables.EncounterSlot.version_group)) \
        .join((tables.Version, tables.Encounter.version)) \
        .join((version_group_b, tables.Version.version_group)) \
        .filter(version_group_a.id != version_group_b.id)

    assert_equal(sanity_q.count(), 0,
        "Encounter slots all match the encounters they belong to")
