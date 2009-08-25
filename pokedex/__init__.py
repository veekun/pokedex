# encoding: utf8
from optparse import OptionParser
import sys

from .db import connect, metadata
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


def command_dump(*args):
    parser = OptionParser()
    parser.add_option('-e', '--engine', dest='engine_uri', default=None)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    parser.add_option('-q', '--quiet', dest='verbose', default=True, action='store_false')
    options, _ = parser.parse_args(list(args))

    session = connect(options.engine_uri)
    pokedex.db.load.dump(session, directory=options.directory,
                                  verbose=options.verbose)

def command_load(*args):
    parser = OptionParser()
    parser.add_option('-e', '--engine', dest='engine_uri', default=None)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    parser.add_option('-D', '--drop-tables', dest='drop_tables', default=False, action='store_true')
    parser.add_option('-q', '--quiet', dest='verbose', default=True, action='store_false')
    options, _ = parser.parse_args(list(args))

    session = connect(options.engine_uri)

    pokedex.db.load.load(session, directory=options.directory,
                                  drop_tables=options.drop_tables,
                                  verbose=options.verbose)

def command_setup(*args):
    session = connect()
    pokedex.db.load.load(session, verbose=False, drop_tables=True)
    pokedex.lookup.open_index(session=session, recreate=True)


def command_lookup(name):
    results = pokedex.lookup.lookup(name)
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

Commands:
    help                Displays this message.
    lookup [thing]      Look up something in the Pokédex.

System commands:
    load                Load Pokédex data into a database from CSV files.
    dump                Dump Pokédex data from a database into CSV files.
    setup               Loads Pokédex data into the right place and creates a
                        lookup index in the right place.  No options or output.
                        This will blow away the default database and index!

Options:
    -d|--directory      By default, load and dump will use the CSV files in the
                        pokedex install directory.  Use this option to specify
                        a different directory.
    -D|--drop-tables    With load, drop all tables before loading data.
    -e|--engine=URI     By default, all commands try to use a SQLite database
                        in the pokedex install directory.  Use this option to
                        specify an alternate database.
    -q|--quiet          Turn off any unnecessary status output from dump/load.
""".encode(sys.getdefaultencoding(), 'replace')

    sys.exit(0)
