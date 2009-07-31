# encoding: utf8
import sys

from sqlalchemy.exc import IntegrityError
import sqlalchemy.types

from .db import connect, metadata, tables as tables_module
from pokedex.lookup import lookup as pokedex_lookup

def main():
    if len(sys.argv) <= 1:
        help()

    command = sys.argv[1]
    args = sys.argv[2:]

    # Find the command as a function in this file
    func = globals().get("command_%s" % command, None)
    if func:
        func(*args)
    else:
        command_help()


def command_csvimport(engine_uri, directory='.'):
    import csv

    from sqlalchemy.orm.attributes import instrumentation_registry

    session = connect(engine_uri)

    metadata.create_all()

    # SQLAlchemy is retarded and there is no way for me to get a list of ORM
    # classes besides to inspect the module they all happen to live in for
    # things that look right.
    table_base = tables_module.TableBase
    orm_classes = {}  # table object => table class

    for name in dir(tables_module):
        # dir() returns strings!  How /convenient/.
        thingy = getattr(tables_module, name)

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

def command_csvexport(engine_uri, directory='.'):
    import csv
    session = connect(engine_uri)

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

def command_lookup(engine_uri, name):
    # XXX don't require uri!  somehow
    session = connect(engine_uri)

    results, exact = pokedex_lookup(session, name)
    if exact:
        print "Matched:"
    else:
        print "Fuzzy-matched:"

    for object in results:
        print object.__tablename__, object.name


def command_help():
    print u"""pokedex -- a command-line Pokédex interface

    help                        Displays this message.
    lookup {uri} [name]         Look up something in the Pokédex.

  These commands are only useful for developers:
    csvimport {uri} [dir]       Import data from a set of CSVs to the database
                                  given by the URI.
    csvexport {uri} [dir]       Export data from the database given by the URI
                                  to a set of CSVs.
                                Directory defaults to cwd.
""".encode(sys.getdefaultencoding(), 'replace')

    sys.exit(0)
