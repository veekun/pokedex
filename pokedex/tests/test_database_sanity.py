
import pytest

from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound

from pokedex.db import connect, tables, util

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

    # Encounter slots all match the encounters they belong to
    assert sanity_q.count() == 0

def test_nonzero_autoincrement_ids():
    """Check that autoincrementing ids don't contain zeroes

    MySQL doesn't like these, see e.g. bug #580
    """

    session = connect()
    for cls in tables.mapped_classes:
        if 'id' in cls.__table__.c:
            if cls.__table__.c.id.autoincrement:
                def nonzero_id(cls):
                    with pytest.raises(NoResultFound):
                        util.get(session, cls, id=0)
                nonzero_id.description = "No zero id in %s" % cls.__name__
                yield nonzero_id, cls
