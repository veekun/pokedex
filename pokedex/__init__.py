# encoding: utf8
from optparse import OptionParser
import os
import pkg_resources
import sys

import pokedex.db
import pokedex.db.load
import pokedex.lookup

def main():
    if len(sys.argv) <= 1:
        command_help()

    command = sys.argv[1]
    args = sys.argv[2:]

    # XXX there must be a better way to get Unicode argv
    # XXX this doesn't work on Windows durp
    enc = sys.stdin.encoding or 'utf8'
    args = [_.decode(enc) for _ in args]

    # Find the command as a function in this file
    func = globals().get("command_%s" % command, None)
    if func:
        func(*args)
    else:
        command_help()


def get_parser(verbose=True):
    """Returns an OptionParser prepopulated with the global options.

    `verbose` is whether or not the options should be verbose by default.
    """
    parser = OptionParser()
    parser.add_option('-e', '--engine', dest='engine_uri', default=os.environ.get('POKEDEX_DB_ENGINE', None))
    parser.add_option('-i', '--index', dest='index_dir', default=os.environ.get('POKEDEX_INDEX_DIR', None))
    parser.add_option('-q', '--quiet', dest='verbose', default=verbose, action='store_false')
    parser.add_option('-v', '--verbose', dest='verbose', default=verbose, action='store_true')
    return parser

def get_session(options):
    """Given a parsed options object, connects to the database and returns a
    session.
    """

    engine_uri = options.engine_uri
    got_from = None
    if engine_uri:
        got_from = 'command line'
    else:
        engine_uri = os.environ.get('POKEDEX_DB_ENGINE', None)
        if engine_uri:
            got_from = 'environment'
        else:
            got_from = 'default setting'

    session = pokedex.db.connect(engine_uri)

    if options.verbose:
        print "Connected to database {engine} (from {got_from})" \
            .format(engine=session.bind.url, got_from=got_from)

    return session

def get_lookup(options, session=None, recreate=False):
    """Given a parsed options object, opens the whoosh index and returns a
    PokedexLookup object.

    Unlike `get_session`, this function can actually do population as a side
    effect!  This is fallout from how PokedexLookup works.
    """
    # TODO fix the above

    if recreate and not session:
        raise ValueError("get_lookup() needs an explicit session to regen the index")

    index_dir = options.index_dir
    got_from = None
    if index_dir:
        got_from = 'command line'
    else:
        index_dir = os.environ.get('POKEDEX_INDEX_DIR', None)
        if index_dir:
            got_from = 'environment'
        else:
            index_dir = pkg_resources.resource_filename('pokedex',
                                                        'data/whoosh-index')
            got_from = 'default setting'

    if options.verbose:
        print "Opened lookup index {index_dir} (from {got_from})" \
            .format(index_dir=index_dir, got_from=got_from)

    lookup = pokedex.lookup.PokedexLookup(index_dir, session=session,
                                                     recreate=recreate)

    return lookup

def print_csv_directory(options):
    """Just prints the csv directory we're about to use."""

    if not options.verbose:
        return

    if options.directory:
        csvdir = options.directory
        got_from = 'command line'
    else:
        # This is the same as the db.load default
        csvdir = pkg_resources.resource_filename('pokedex', 'data/csv')
        got_from = 'default setting'

    print "Using CSV directory {csvdir} (from {got_from})" \
        .format(csvdir=csvdir, got_from=got_from)


### Plumbing commands

def command_dump(*args):
    parser = get_parser(verbose=True)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    options, tables = parser.parse_args(list(args))

    session = get_session(options)
    print_csv_directory(options)

    pokedex.db.load.dump(session, directory=options.directory,
                                  tables=tables,
                                  verbose=options.verbose)

def command_load(*args):
    parser = get_parser(verbose=True)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    parser.add_option('-D', '--drop-tables', dest='drop_tables', default=False, action='store_true')
    options, tables = parser.parse_args(list(args))

    if not options.engine_uri:
        print "WARNING: You're reloading the default database, but not the lookup index.  They"
        print "         might get out of sync, and pokedex commands may not work correctly!"
        print "To fix this, run `pokedex reindex` when this command finishes.  Or, just use"
        print "`pokedex setup` to do both at once."
        print

    session = get_session(options)
    print_csv_directory(options)

    pokedex.db.load.load(session, directory=options.directory,
                                  drop_tables=options.drop_tables,
                                  tables=tables,
                                  verbose=options.verbose)

def command_reindex(*args):
    parser = get_parser(verbose=True)
    options, _ = parser.parse_args(list(args))

    session = get_session(options)
    lookup = get_lookup(options, session=session, recreate=True)

    print "Recreated lookup index."


def command_setup(*args):
    parser = get_parser(verbose=False)
    options, _ = parser.parse_args(list(args))

    options.directory = None

    session = get_session(options)
    print_csv_directory(options)
    pokedex.db.load.load(session, directory=None, drop_tables=True,
                                  verbose=options.verbose)

    lookup = get_lookup(options, session=session, recreate=True)

    print "Recreated lookup index."


def command_status(*args):
    parser = get_parser(verbose=True)
    options, _ = parser.parse_args(list(args))
    options.verbose = True
    options.directory = None

    session = get_session(options)
    print_csv_directory(options)
    lookup = get_lookup(options, recreate=False)


### User-facing commands

def command_lookup(*args):
    parser = get_parser(verbose=False)
    options, words = parser.parse_args(list(args))

    name = u' '.join(words)

    session = get_session(options)
    lookup = get_lookup(options, session=session, recreate=False)

    results = lookup.lookup(name)
    if not results:
        print "No matches."
    elif results[0].exact:
        print "Matched:"
    else:
        print "Fuzzy-matched:"

    for result in results:
        if hasattr(result.object, 'full_name'):
            name = result.object.full_name
        else:
            name = result.object.name

        print "%s: %s" % (result.object.__tablename__, name),
        if result.language:
            print "(%s in %s)" % (result.name, result.language)
        else:
            print


def command_help():
    print u"""pokedex -- a command-line Pokédex interface
usage: pokedex {command} [options...]
Run `pokedex setup` first, or nothing will work!
See http://bugs.veekun.com/projects/pokedex/wiki/CLI for more documentation.

Commands:
    help                Displays this message.
    lookup [thing]      Look up something in the Pokédex.

System commands:
    load                Load Pokédex data into a database from CSV files.
    dump                Dump Pokédex data from a database into CSV files.
    reindex             Rebuilds the lookup index from the database.
    setup               Combines load and reindex.
    status              No effect, but prints which engine, index, and csv
                        directory would be used for other commands.

Global options:
    -e|--engine=URI     By default, all commands try to use a SQLite database
                        in the pokedex install directory.  Use this option (or
                        a POKEDEX_DB_ENGINE environment variable) to specify an
                        alternate database.
    -i|--index=DIR      By default, all commands try to put the lookup index in
                        the pokedex install directory.  Use this option (or a
                        POKEDEX_INDEX_DIR environment variable) to specify an
                        alternate loction.
    -q|--quiet          Don't print system output.  This is the default for
                        non-system commands and setup.
    -v|--verbose        Print system output.  This is the default for system
                        commands, except setup.

System options:
    -d|--directory=DIR  By default, load and dump will use the CSV files in the
                        pokedex install directory.  Use this option to specify
                        a different directory.
    -D|--drop-tables    With load, drop all tables before loading data.

    Additionally, load and dump accept a list of table names (possibly with
    wildcards) and/or csv fileames as an argument list.
""".encode(sys.getdefaultencoding(), 'replace')

    sys.exit(0)
