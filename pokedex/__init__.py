# encoding: utf8
from optparse import OptionParser
import sys

from .db import connect, metadata
import pokedex.db.load
from pokedex.lookup import lookup as pokedex_lookup

def main():
    if len(sys.argv) <= 1:
        command_help()

    command = sys.argv[1]
    args = sys.argv[2:]

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
    options, _ = parser.parse_args(list(args))

    session = connect(options.engine_uri)
    pokedex.db.load.dump(session, directory=options.directory)

def command_load(*args):
    parser = OptionParser()
    parser.add_option('-e', '--engine', dest='engine_uri', default=None)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    parser.add_option('-D', '--drop-tables', dest='drop_tables', default=False, action='store_true')
    options, _ = parser.parse_args(list(args))

    session = connect(options.engine_uri)

    pokedex.db.load.load(session, directory=options.directory,
                                  drop_tables=options.drop_tables)


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
usage: pokedex {command} [options...]
Run `pokedex setup` first, or nothing will work!

Commands:
    help                Displays this message.
    lookup [thing]      Look up something in the Pokédex.

System commands:
    load                Load Pokédex data into a database from CSV files.
    dump                Dump Pokédex data from a database into CSV files.

Options:
    -d|--directory      By default, load and dump will use the CSV files in the
                        pokedex install directory.  Use this option to specify
                        a different directory.
    -D|--drop-tables    With load, drop all tables before loading data.
    -e|--engine=URI     By default, all commands try to use a SQLite database
                        in the pokedex install directory.  Use this option to
                        specify an alternate database.
""".encode(sys.getdefaultencoding(), 'replace')

    sys.exit(0)
