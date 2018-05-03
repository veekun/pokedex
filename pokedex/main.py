# encoding: utf8
from __future__ import print_function

import argparse
import os
import sys

import pokedex.cli.search
import pokedex.db
import pokedex.db.load
import pokedex.db.tables
import pokedex.lookup
from pokedex import defaults


def main(junk, *argv):
    parser = create_parser()
    
    if len(argv) <= 0:
        parser.print_help()
        sys.exit()

    args = parser.parse_args(argv)
    args.func(parser, args)


def setuptools_entry():
    main(*sys.argv)


def create_parser():
    """Build and return an ArgumentParser.
    """
    # Slightly clumsy workaround to make both `setup -v` and `-v setup` work
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        '-e', '--engine', dest='engine_uri', default=None,
        help=u'By default, all commands try to use a SQLite database '
            u'in the pokedex install directory.  Use this option (or '
            u'a POKEDEX_DB_ENGINE environment variable) to specify an '
            u'alternate database.',
        )
    common_parser.add_argument(
        '-i', '--index', dest='index_dir', default=None,
        help=u'By default, all commands try to put the lookup index in '
            u'the pokedex install directory.  Use this option (or a '
            u'POKEDEX_INDEX_DIR environment variable) to specify an '
            u'alternate loction.',
    )
    common_parser.add_argument(
        '-q', '--quiet', dest='verbose', action='store_false',
        help=u'Don\'t print system output.  This is the default for '
            'non-system commands and setup.',
    )
    common_parser.add_argument(
        '-v', '--verbose', dest='verbose', default=False, action='store_true',
        help=u'Print system output.  This is the default for system '
            u'commands, except setup.',
    )

    parser = argparse.ArgumentParser(
        prog='pokedex', description=u'A command-line Pokédex interface',
        parents=[common_parser],
    )

    cmds = parser.add_subparsers(title='commands', metavar='<command>', help='commands')
    cmd_help = cmds.add_parser(
        'help', help=u'Display this message',
        parents=[common_parser])
    cmd_help.set_defaults(func=command_help)

    cmd_lookup = cmds.add_parser(
        'lookup', help=u'Look up something in the Pokédex',
        parents=[common_parser])
    cmd_lookup.set_defaults(func=command_lookup)
    cmd_lookup.add_argument('criteria', nargs='+')

    cmd_search = cmds.add_parser(
        'search', help=u'Find things by various criteria',
        parents=[common_parser])
    pokedex.cli.search.configure_parser(cmd_search)

    cmd_load = cmds.add_parser(
        'load', help=u'Load Pokédex data into a database from CSV files',
        parents=[common_parser])
    cmd_load.set_defaults(func=command_load, verbose=True)
    # TODO get the actual default here
    cmd_load.add_argument(
        '-d', '--directory', dest='directory', default=None,
        help="directory containing the CSV files to load")
    cmd_load.add_argument(
        '-D', '--drop-tables', dest='drop_tables', default=False, action='store_true',
        help="drop all tables before loading data")
    cmd_load.add_argument(
        '-r', '--recursive', dest='recursive', default=False, action='store_true',
        help="load and drop all dependent tables (default is to use exactly the given list)")
    cmd_load.add_argument(
        '-S', '--safe', dest='safe', default=False, action='store_true',
        help="disable database-specific optimizations, such as Postgres's COPY FROM")
    # TODO need a custom handler for splittin' all of these
    cmd_load.add_argument(
        '-l', '--langs', dest='langs', default=None,
        help="comma-separated list of language codes to load, or 'none' (default: all)")
    cmd_load.add_argument(
        'tables', nargs='*',
        help="list of database tables to load (default: all)")

    cmd_dump = cmds.add_parser(
        'dump', help=u'Dump Pokédex data from a database into CSV files',
        parents=[common_parser])
    cmd_dump.set_defaults(func=command_dump, verbose=True)
    cmd_dump.add_argument(
        '-d', '--directory', dest='directory', default=None,
        help="directory to place the dumped CSV files")
    cmd_dump.add_argument(
        '-l', '--langs', dest='langs', default=None,
        help="comma-separated list of language codes to load, 'none', or 'all' (default: en)")
    cmd_dump.add_argument(
        'tables', nargs='*',
        help="list of database tables to load (default: all)")

    cmd_reindex = cmds.add_parser(
        'reindex', help=u'Rebuild the lookup index from the database',
        parents=[common_parser])
    cmd_reindex.set_defaults(func=command_reindex, verbose=True)

    cmd_setup = cmds.add_parser(
        'setup', help=u'Combine load and reindex',
        parents=[common_parser])
    cmd_setup.set_defaults(func=command_setup, verbose=False)

    cmd_status = cmds.add_parser(
        'status', help=u'Print which engine, index, and csv directory would be used for other commands',
        parents=[common_parser])
    cmd_status.set_defaults(func=command_status, verbose=True)

    return parser


def get_session(args):
    """Given a parsed options object, connects to the database and returns a
    session.
    """

    engine_uri = args.engine_uri
    got_from = 'command line'

    if engine_uri is None:
        engine_uri, got_from = defaults.get_default_db_uri_with_origin()

    session = pokedex.db.connect(engine_uri)

    if args.verbose:
        print("Connected to database %(engine)s (from %(got_from)s)"
            % dict(engine=session.bind.url, got_from=got_from))

    return session


def get_lookup(args, session=None, recreate=False):
    """Given a parsed options object, opens the whoosh index and returns a
    PokedexLookup object.
    """

    if recreate and not session:
        raise ValueError("get_lookup() needs an explicit session to regen the index")

    index_dir = args.index_dir
    got_from = 'command line'

    if index_dir is None:
        index_dir, got_from = defaults.get_default_index_dir_with_origin()

    if args.verbose:
        print("Opened lookup index %(index_dir)s (from %(got_from)s)"
            % dict(index_dir=index_dir, got_from=got_from))

    lookup = pokedex.lookup.PokedexLookup(index_dir, session=session)

    if recreate:
        lookup.rebuild_index()

    return lookup


def get_csv_directory(args):
    """Prints and returns the csv directory we're about to use."""

    if not args.verbose:
        return

    csvdir = args.directory
    got_from = 'command line'

    if csvdir is None:
        csvdir, got_from = defaults.get_default_csv_dir_with_origin()

    print("Using CSV directory %(csvdir)s (from %(got_from)s)"
        % dict(csvdir=csvdir, got_from=got_from))

    return csvdir


### Plumbing commands

def command_dump(parser, args):
    session = get_session(args)
    get_csv_directory(args)

    if args.langs is not None:
        langs = [l.strip() for l in args.langs.split(',')]
    else:
        langs = None

    pokedex.db.load.dump(
        session,
        directory=args.directory,
        tables=args.tables,
        verbose=args.verbose,
        langs=langs,
    )


def command_load(parser, args):
    if not args.engine_uri:
        print("WARNING: You're reloading the default database, but not the lookup index.  They")
        print("         might get out of sync, and pokedex commands may not work correctly!")
        print("To fix this, run `pokedex reindex` when this command finishes.  Or, just use")
        print("`pokedex setup` to do both at once.")
        print()

    if args.langs == 'none':
        langs = []
    elif args.langs is None:
        langs = None
    else:
        langs = [l.strip() for l in args.langs.split(',')]

    session = get_session(args)
    get_csv_directory(args)

    pokedex.db.load.load(
        session,
        directory=args.directory,
        drop_tables=args.drop_tables,
        tables=args.tables,
        verbose=args.verbose,
        safe=args.safe,
        recursive=args.recursive,
        langs=langs,
    )


def command_reindex(parser, args):
    session = get_session(args)
    get_lookup(args, session=session, recreate=True)
    print("Recreated lookup index.")


def command_setup(parser, args):
    args.directory = None

    session = get_session(args)
    get_csv_directory(args)
    pokedex.db.load.load(
        session, directory=None, drop_tables=True,
        verbose=args.verbose, safe=False)

    get_lookup(args, session=session, recreate=True)
    print("Recreated lookup index.")


def command_status(parser, args):
    args.directory = None

    # Database, and a lame check for whether it's been inited at least once
    session = get_session(args)
    print("  - OK!  Connected successfully.")

    if pokedex.db.tables.Pokemon.__table__.exists(session.bind):
        print("  - OK!  Database seems to contain some data.")
    else:
        print("  - WARNING: Database appears to be empty.")

    # CSV; simple checks that the dir exists
    csvdir = get_csv_directory(args)
    if not os.path.exists(csvdir):
        print("  - ERROR: No such directory!")
    elif not os.path.isdir(csvdir):
        print("  - ERROR: Not a directory!")
    else:
        print("  - OK!  Directory exists.")

        if os.access(csvdir, os.R_OK):
            print("  - OK!  Can read from directory.")
        else:
            print("  - ERROR: Can't read from directory!")

        if os.access(csvdir, os.W_OK):
            print("  - OK!  Can write to directory.")
        else:
            print("  - WARNING: Can't write to directory!  "
                "`dump` will not work.  You may need to sudo.")

    # Index; the PokedexLookup constructor covers most tests and will
    # cheerfully bomb if they fail
    get_lookup(args, recreate=False)
    print("  - OK!  Opened successfully.")


### User-facing commands

def command_lookup(parser, args):
    name = u' '.join(args.criteria)

    session = get_session(args)
    lookup = get_lookup(args, session=session, recreate=False)

    results = lookup.lookup(name)
    if not results:
        print("No matches.")
    elif results[0].exact:
        print("Matched:")
    else:
        print("Fuzzy-matched:")

    for result in results:
        if hasattr(result.object, 'full_name'):
            name = result.object.full_name
        else:
            name = result.object.name

        print("%s: %s" % (result.object.__tablename__, name), end='')
        if result.language:
            print("(%s in %s)" % (result.name, result.language))
        else:
            print()


def command_help(parser, args):
    parser.print_help()


if __name__ == '__main__':
    main(*sys.argv)
