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

    # Use autocommit in case rows fail due to foreign key incest
    session = connect(engine_uri, autocommit=True, autoflush=False)

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

        # Self-referential tables may contain rows with foreign keys of
        # other rows in the same table that do not yet exist.  We'll keep
        # a running list of these and try inserting them again after the
        # rest are done
        failed_rows = []

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

            try:
                session.add(row)
                session.flush()
            except IntegrityError as e:
                failed_rows.append(row)

        # Loop over the failed rows and keep trying to insert them.  If a loop
        # doesn't manage to insert any rows, bail.
        do_another_loop = True
        while failed_rows and do_another_loop:
            do_another_loop = False

            for i, row in enumerate(failed_rows):
                try:
                    session.add(row)
                    session.flush()

                    # Success!
                    del failed_rows[i]
                    do_another_loop = True
                except IntegrityError as e:
                    pass

        if failed_rows:
            print len(failed_rows), "rows failed"
        else:
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

        for row in session.query(table).all():
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
"""

    sys.exit(0)
