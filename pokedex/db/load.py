"""CSV to database or vice versa."""
import csv
import fnmatch
import os.path
import sys

import sqlalchemy.sql.util
import sqlalchemy.types

import pokedex
from pokedex.db import metadata, tables, translations
from pokedex.defaults import get_default_csv_dir
from pokedex.db.dependencies import find_dependent_tables
from pokedex.db.oracle import rewrite_long_table_names


def _get_table_names(metadata, patterns):
    """Returns a list of table names from the given metadata.  If `patterns`
    exists, only tables matching one of the patterns will be returned.
    """
    if patterns:
        table_names = set()
        for pattern in patterns:
            if '.' in pattern or '/' in pattern:
                # If it looks like a filename, pull out just the table name
                _, filename = os.path.split(pattern)
                table_name, _ = os.path.splitext(filename)
                pattern = table_name

            table_names.update(fnmatch.filter(metadata.tables.keys(), pattern))
    else:
        table_names = metadata.tables.keys()

    return list(table_names)

def _get_verbose_prints(verbose):
    """If `verbose` is true, returns three functions: one for printing a
    starting message, one for printing an interim status update, and one for
    printing a success or failure message when finished.

    If `verbose` is false, returns no-op functions.
    """

    if not verbose:
        # Return dummies
        def dummy(*args, **kwargs):
            pass

        return dummy, dummy, dummy

    ### Okay, verbose == True; print stuff

    def print_start(thing):
        # Truncate to 66 characters, leaving 10 characters for a success
        # or failure message
        truncated_thing = thing[:66]

        # Also, space-pad to keep the cursor in a known column
        num_spaces = 66 - len(truncated_thing)

        print "%s...%s" % (truncated_thing, ' ' * num_spaces),
        sys.stdout.flush()

    if sys.stdout.isatty():
        # stdout is a terminal; stupid backspace tricks are OK.
        # Don't use print, because it always adds magical spaces, which
        # makes backspace accounting harder

        backspaces = [0]
        def print_status(msg):
            # Overwrite any status text with spaces before printing
            sys.stdout.write('\b' * backspaces[0])
            sys.stdout.write(' ' * backspaces[0])
            sys.stdout.write('\b' * backspaces[0])
            sys.stdout.write(msg)
            sys.stdout.flush()
            backspaces[0] = len(msg)

        def print_done(msg='ok'):
            # Overwrite any status text with spaces before printing
            sys.stdout.write('\b' * backspaces[0])
            sys.stdout.write(' ' * backspaces[0])
            sys.stdout.write('\b' * backspaces[0])
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()
            backspaces[0] = 0

    else:
        # stdout is a file (or something); don't bother with status at all
        def print_status(msg):
            pass

        def print_done(msg='ok'):
            print msg

    return print_start, print_status, print_done


def load(session, tables=[], directory=None, drop_tables=False, verbose=False, safe=True, recursive=True, langs=None):
    """Load data from CSV files into the given database session.

    Tables are created automatically.

    `session`
        SQLAlchemy session to use.

    `tables`
        List of tables to load.  If omitted, all tables are loaded.

    `directory`
        Directory the CSV files reside in.  Defaults to the `pokedex` data
        directory.

    `drop_tables`
        If set to True, existing `pokedex`-related tables will be dropped.

    `verbose`
        If set to True, status messages will be printed to stdout.

    `safe`
        If set to False, load can be faster, but can corrupt the database if
        it crashes or is interrupted.

    `recursive`
        If set to True, load all dependent tables too.

    `langs`
        List of identifiers of extra language to load, or None to load them all
    """

    # First take care of verbosity
    print_start, print_status, print_done = _get_verbose_prints(verbose)


    if directory is None:
        directory = get_default_csv_dir()

    # XXX why isn't this done in command_load
    table_names = _get_table_names(metadata, tables)
    table_objs = [metadata.tables[name] for name in table_names]

    if recursive:
        table_objs.extend(find_dependent_tables(table_objs))

    table_objs = sqlalchemy.sql.util.sort_tables(table_objs)

    # Limit table names to 30 characters for Oracle
    oracle = (session.connection().dialect.name == 'oracle')
    if oracle:
        rewrite_long_table_names()

    # SQLite speed tweaks
    if not safe and session.connection().dialect.name == 'sqlite':
        session.connection().execute("PRAGMA synchronous=OFF")
        session.connection().execute("PRAGMA journal_mode=OFF")

    # Drop all tables if requested
    if drop_tables:
        bind = session.get_bind()
        print_start('Dropping tables')
        for n, table in enumerate(reversed(table_objs)):
            table.drop(checkfirst=True)

            # Drop columns' types if appropriate; needed for enums in
            # postgresql
            for column in table.c:
                try:
                    drop = column.type.drop
                except AttributeError:
                    pass
                else:
                    drop(bind=bind, checkfirst=True)

            print_status('%s/%s' % (n, len(table_objs)))
        print_done()

    print_start('Creating tables')
    for n, table in enumerate(table_objs):
        table.create()
        print_status('%s/%s' % (n, len(table_objs)))
    print_done()
    connection = session.connection()

    # Okay, run through the tables and actually load the data now
    for table_obj in table_objs:
        if oracle:
            table_name = table_obj._original_name
        else:
            table_name = table_obj.name

        insert_stmt = table_obj.insert()

        print_start(table_name)

        try:
            csvpath = "%s/%s.csv" % (directory, table_name)
            csvfile = open(csvpath, 'rb')
        except IOError:
            # File doesn't exist; don't load anything!
            print_done('missing?')
            continue

        csvsize = os.stat(csvpath).st_size

        reader = csv.reader(csvfile, lineterminator='\n')
        column_names = [unicode(column) for column in reader.next()]

        if not safe and session.connection().dialect.name == 'postgresql':
            """
            Postgres' CSV dialect works with our data, if we mark the not-null
            columns with FORCE NOT NULL.
            COPY is only allowed for DB superusers. If you're not one, use safe
            loading (pokedex load -S).
            """
            session.commit()
            not_null_cols = [c for c in column_names if not table_obj.c[c].nullable]
            if not_null_cols:
                force_not_null = 'FORCE NOT NULL ' + ','.join('"%s"' % c for c in not_null_cols)
            else:
                force_not_null = ''
            command = "COPY %(table_name)s (%(columns)s) FROM '%(csvpath)s' CSV HEADER %(force_not_null)s"
            session.connection().execute(
                command % dict(
                    table_name=table_name,
                    csvpath=csvpath,
                    columns=','.join('"%s"' % c for c in column_names),
                    force_not_null=force_not_null,
                )
            )
            session.commit()
            print_done()
            continue

        # Self-referential tables may contain rows with foreign keys of other
        # rows in the same table that do not yet exist.  Pull these out and add
        # them to the session last
        # ASSUMPTION: Self-referential tables have a single PK called "id"
        deferred_rows = []  # ( row referring to id, [foreign ids we need] )
        seen_ids = set()    # primary keys we've seen

        # Fetch foreign key columns that point at this table, if any
        self_ref_columns = []
        for column in table_obj.c:
            if any(x.references(table_obj) for x in column.foreign_keys):
                self_ref_columns.append(column)

        new_rows = []
        def insert_and_commit():
            if not new_rows:
                return
            session.connection().execute(insert_stmt, new_rows)
            session.commit()
            new_rows[:] = []

            progress = "%d%%" % (100 * csvfile.tell() // csvsize)
            print_status(progress)

        for csvs in reader:
            row_data = {}

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

                # nb: Dictionaries flattened with ** have to have string keys
                row_data[ str(column_name) ] = value

            # May need to stash this row and add it later if it refers to a
            # later row in this table
            if self_ref_columns:
                foreign_ids = set(row_data[x.name] for x in self_ref_columns)
                foreign_ids.discard(None)  # remove NULL ids

                if not foreign_ids:
                    # NULL key.  Remember this row and add as usual.
                    seen_ids.add(row_data['id'])

                elif foreign_ids.issubset(seen_ids):
                    # Non-NULL key we've already seen.  Remember it and commit
                    # so we know the old row exists when we add the new one
                    insert_and_commit()
                    seen_ids.add(row_data['id'])

                else:
                    # Non-NULL future id.  Save this and insert it later!
                    deferred_rows.append((row_data, foreign_ids))
                    continue

            # Insert row!
            new_rows.append(row_data)

            # Remembering some zillion rows in the session consumes a lot of
            # RAM.  Let's not do that.  Commit every 1000 rows
            if len(new_rows) >= 1000:
                insert_and_commit()

        insert_and_commit()

        # Attempt to add any spare rows we've collected
        for row_data, foreign_ids in deferred_rows:
            if not foreign_ids.issubset(seen_ids):
                # Could happen if row A refers to B which refers to C.
                # This is ridiculous and doesn't happen in my data so far
                raise ValueError("Too many levels of self-reference!  "
                                 "Row was: " + str(row))

            session.connection().execute(
                insert_stmt.values(**row_data)
            )
            seen_ids.add(row_data['id'])
        session.commit()

        print_done()


    print_start('Translations')
    transl = translations.Translations(csv_directory=directory)

    new_row_count = 0
    for translation_class, rows in transl.get_load_data(langs):
        table_obj = translation_class.__table__
        if table_obj in table_objs:
            insert_stmt = table_obj.insert()
            session.connection().execute(insert_stmt, rows)
            session.commit()
            # We don't have a total, but at least show some increasing number
            new_row_count += len(rows)
            print_status(str(new_row_count))

    print_done()

    # SQLite check
    if session.connection().dialect.name == 'sqlite':
        session.connection().execute("PRAGMA integrity_check")



def dump(session, tables=[], directory=None, verbose=False, langs=None):
    """Dumps the contents of a database to a set of CSV files.  Probably not
    useful to anyone besides a developer.

    `session`
        SQLAlchemy session to use.

    `tables`
        List of tables to dump.  If omitted, all tables are dumped.

    `directory`
        Directory the CSV files should be put in.  Defaults to the `pokedex`
        data directory.

    `verbose`
        If set to True, status messages will be printed to stdout.

    `langs`
        List of identifiers of languages to dump unofficial texts for
    """

    # First take care of verbosity
    print_start, print_status, print_done = _get_verbose_prints(verbose)

    languages = dict((l.id, l) for l in session.query(pokedex.db.tables.Language))

    if not directory:
        directory = get_default_csv_dir()

    table_names = _get_table_names(metadata, tables)
    table_names.sort()

    # Oracle needs to dump from tables with shortened names to csvs with the
    # usual names
    oracle = (session.connection().dialect.name == 'oracle')
    if oracle:
        rewrite_long_table_names()

    for table_name in table_names:
        print_start(table_name)
        table = metadata.tables[table_name]

        if oracle:
            filename = '%s/%s.csv' % (directory, table._original_name)
        else:
            filename = '%s/%s.csv' % (directory, table_name)

        writer = csv.writer(open(filename, 'wb'), lineterminator='\n')

        columns = [col.name for col in table.columns]

        # For name tables, always dump rows for official languages, as well as
        # for those in `langs` if specified.
        # For other translation tables, only dump rows for languages in `langs`
        # if specified, or for official languages by default.
        # For non-translation tables, dump all rows.
        if 'local_language_id' in columns:
            if langs is None:
                def include_row(row):
                    return languages[row.local_language_id].official
            elif any(col.info.get('official') for col in table.columns):
                def include_row(row):
                    return (languages[row.local_language_id].official or
                            languages[row.local_language_id].identifier in langs)
            else:
                def include_row(row):
                    return languages[row.local_language_id].identifier in langs
        else:
            def include_row(row):
                return True

        writer.writerow(columns)

        primary_key = table.primary_key
        for row in session.query(table).order_by(*primary_key).all():
            if include_row(row):
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

        print_done()
