"""CSV to database or vice versa."""
import csv
import pkg_resources
import sys

from sqlalchemy.orm.attributes import instrumentation_registry
import sqlalchemy.types

from pokedex.db import metadata
import pokedex.db.tables as tables


def load(session, directory=None, drop_tables=False):
    """Load data from CSV files into the given database session.

    Tables are created automatically.

    `session`
        SQLAlchemy session to use.

    `directory`
        Directory the CSV files reside in.  Defaults to the `pokedex` data
        directory.

    `drop_tables`
        If set to True, existing `pokedex`-related tables will be dropped.
    """

    if not directory:
        directory = pkg_resources.resource_filename('pokedex', 'data/csv')

    # Drop all tables if requested
    if options.drop_tables:
        print 'Dropping tables...'
        metadata.drop_all()

    metadata.create_all()

    # SQLAlchemy is retarded and there is no way for me to get a list of ORM
    # classes besides to inspect the module they all happen to live in for
    # things that look right.
    table_base = tables.TableBase
    orm_classes = {}  # table object => table class

    for name in dir(tables):
        # dir() returns strings!  How /convenient/.
        thingy = getattr(tables, name)

        if not isinstance(thingy, type):
            # Not a class; bail
            continue
        elif not issubclass(thingy, table_base):
            # Not a declarative table; bail
            continue
        elif thingy == table_base:
            # Declarative table base, so not a real table; bail
            continue

        # thingy is definitely a table class!  Hallelujah.
        orm_classes[thingy.__table__] = thingy

    # Okay, run through the tables and actually load the data now
    for table_obj in metadata.sorted_tables:
        table_class = orm_classes[table_obj]
        table_name = table_obj.name

        # Print the table name but leave the cursor in a fixed column
        print table_name + '...', ' ' * (40 - len(table_name)),
        sys.stdout.flush()

        try:
            csvfile = open("%s/%s.csv" % (directory, table_name), 'rb')
        except IOError:
            # File doesn't exist; don't load anything!
            print 'no data!'
            continue

        reader = csv.reader(csvfile, lineterminator='\n')
        column_names = [unicode(column) for column in reader.next()]

        # Self-referential tables may contain rows with foreign keys of other
        # rows in the same table that do not yet exist.  Pull these out and add
        # them to the session last
        # ASSUMPTION: Self-referential tables have a single PK called "id"
        deferred_rows = []  # ( row referring to id, [foreign ids we need] )
        seen_ids = {}       # primary key we've seen => 1

        # Fetch foreign key columns that point at this table, if any
        self_ref_columns = []
        for column in table_obj.c:
            if any(_.references(table_obj) for _ in column.foreign_keys):
                self_ref_columns.append(column)

        for csvs in reader:
            row = table_class()

            for column_name, value in zip(column_names, csvs):
                column = table_obj.c[column_name]
                if column.nullable and value == '':
                    # Empty string in a nullable column really means NULL
                    value = None
                elif isinstance(column.type, sqlalchemy.types.Boolean):
                    # Boolean values are stored as string values 0/1, but both
                    # of those evaluate as true; SQLA wants True/False
                    if value == '0':
                        value = False
                    else:
                        value = True
                else:
                    # Otherwise, unflatten from bytes
                    value = value.decode('utf-8')

                setattr(row, column_name, value)

            # May need to stash this row and add it later if it refers to a
            # later row in this table
            if self_ref_columns:
                foreign_ids = [getattr(row, _.name) for _ in self_ref_columns]
                foreign_ids = [_ for _ in foreign_ids if _]  # remove NULL ids

                if not foreign_ids:
                    # NULL key.  Remember this row and add as usual.
                    seen_ids[row.id] = 1

                elif all(_ in seen_ids for _ in foreign_ids):
                    # Non-NULL key we've already seen.  Remember it and commit
                    # so we know the old row exists when we add the new one
                    session.commit()
                    seen_ids[row.id] = 1

                else:
                    # Non-NULL future id.  Save this and insert it later!
                    deferred_rows.append((row, foreign_ids))
                    continue

            session.add(row)

        session.commit()

        # Attempt to add any spare rows we've collected
        for row, foreign_ids in deferred_rows:
            if not all(_ in seen_ids for _ in foreign_ids):
                # Could happen if row A refers to B which refers to C.
                # This is ridiculous and doesn't happen in my data so far
                raise ValueError("Too many levels of self-reference!  "
                                 "Row was: " + str(row.__dict__))

            session.add(row)
            seen_ids[row.id] = 1
            session.commit()

        print 'loaded'



def dump(session, directory=None):
    """Dumps the contents of a database to a set of CSV files.  Probably not
    useful to anyone besides a developer.

    `session`
        SQLAlchemy session to use.

    `directory`
        Directory the CSV files should be put in.  Defaults to the `pokedex`
        data directory.
    """

    if not directory:
        directory = pkg_resources.resource_filename('pokedex', 'data/csv')

    for table_name in sorted(metadata.tables.keys()):
        print table_name
        table = metadata.tables[table_name]

        writer = csv.writer(open("%s/%s.csv" % (directory, table_name), 'wb'),
                            lineterminator='\n')
        columns = [col.name for col in table.columns]
        writer.writerow(columns)

        primary_key = table.primary_key
        for row in session.query(table).order_by(*primary_key).all():
            csvs = []
            for col in columns:
                # Convert Pythony values to something more universal
                val = getattr(row, col)
                if val == None:
                    val = ''
                elif val == True:
                    val = '1'
                elif val == False:
                    val = '0'
                else:
                    val = unicode(val).encode('utf-8')

                csvs.append(val)

            writer.writerow(csvs)
