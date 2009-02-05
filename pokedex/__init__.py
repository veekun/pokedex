# encoding: utf8
import sys

from .db import connect, metadata

def main():
    if len(sys.argv) <= 1:
        help()

    command = sys.argv[1]
    args = sys.argv[2:]

    # Find the command as a function in this file
    func = globals().get(command, None)
    if func and callable(func) and command != 'main':
        func(*args)
    else:
        help()


def csvimport(engine_uri, dir='.'):
    import csv

    from sqlalchemy.orm.attributes import instrumentation_registry

    session = connect(engine_uri)

    metadata.create_all()

    # This is a secret attribute on a secret singleton of a secret class that
    # appears to hopefully contain all registered classes as keys.
    # There is no other way to accomplish this, as far as I can tell.
    # Fuck.
    for table in sorted(instrumentation_registry.manager_finders.keys(),
                        key=lambda self: self.__table__.name):
        table_name = table.__table__.name
        print table_name

        reader = csv.reader(open("%s/%s.csv" % (dir, table_name), 'rb'), lineterminator='\n')
        columns = [unicode(column) for column in reader.next()]

        for csvs in reader:
            row = table()

            for column, value in zip(columns, csvs):
                value = value.decode('utf-8')
                setattr(row, column, value)

            session.add(row)

        session.commit()


def csvexport(engine_uri, dir='.'):
    import csv
    session = connect(engine_uri)

    for table_name in sorted(metadata.tables.keys()):
        print table_name
        table = metadata.tables[table_name]

        writer = csv.writer(open("%s/%s.csv" % (dir, table_name), 'wb'), lineterminator='\n')
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


def help():
    print u"""pokedex -- a command-line Pokédex interface

    help                        Displays this message.

  These commands are only useful for developers:
    csvimport {uri} [dir]       Import data from a set of CSVs to the database
                                  given by the URI.
    csvexport {uri} [dir]       Export data from the database given by the URI
                                  to a set of CSVs.
                                Directory defaults to cwd.
"""

    sys.exit(0)
