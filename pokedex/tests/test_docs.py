import os
import re

from pokedex.db.tables import mapped_classes

def test_main_tables():
    """Check that tables.py and main-tables.rst are in sync: every table should
    be documented, and every documented table should exist."""

    main_tables_path = os.path.join(os.path.dirname(__file__), '../../doc/main-tables.rst')

    with open(main_tables_path) as f:
        doc_class_names = set(
            re.findall(r'^\.\. dex-table:: (\w+)$', f.read(), re.MULTILINE)
        )

    mapped_class_names = set(cls.__name__ for cls in mapped_classes)

    # EXTRA ITEMS IN THE LEFT SET: tables defined but not documented
    # EXTRA ITEMS IN THE RIGHT SET: tables documented but not defined
    assert mapped_class_names == doc_class_names

