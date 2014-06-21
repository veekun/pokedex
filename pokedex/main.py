# encoding: utf8
from optparse import OptionParser
import os
import sys
import textwrap
import json
import base64
import ast
import pprint

import pokedex.db
import pokedex.db.load
import pokedex.db.tables
import pokedex.lookup
import pokedex.struct
from pokedex import defaults

def main(*argv):
    if len(argv) <= 1:
        command_help()

    command = argv[1]
    args = argv[2:]

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

def setuptools_entry():
    main(*sys.argv)


def get_parser(verbose=True):
    """Returns an OptionParser prepopulated with the global options.

    `verbose` is whether or not the options should be verbose by default.
    """
    parser = OptionParser()
    parser.add_option('-e', '--engine', dest='engine_uri', default=None)
    parser.add_option('-i', '--index', dest='index_dir', default=None)
    parser.add_option('-q', '--quiet', dest='verbose', default=verbose, action='store_false')
    parser.add_option('-v', '--verbose', dest='verbose', default=verbose, action='store_true')
    return parser

def get_session(options):
    """Given a parsed options object, connects to the database and returns a
    session.
    """

    engine_uri = options.engine_uri
    got_from = 'command line'

    if engine_uri is None:
        engine_uri, got_from = defaults.get_default_db_uri_with_origin()

    session = pokedex.db.connect(engine_uri)

    if options.verbose:
        print "Connected to database %(engine)s (from %(got_from)s)" \
            % dict(engine=session.bind.url, got_from=got_from)

    return session

def get_lookup(options, session=None, recreate=False):
    """Given a parsed options object, opens the whoosh index and returns a
    PokedexLookup object.
    """

    if recreate and not session:
        raise ValueError("get_lookup() needs an explicit session to regen the index")

    index_dir = options.index_dir
    got_from = 'command line'

    if index_dir is None:
        index_dir, got_from = defaults.get_default_index_dir_with_origin()

    if options.verbose:
        print "Opened lookup index %(index_dir)s (from %(got_from)s)" \
            % dict(index_dir=index_dir, got_from=got_from)

    lookup = pokedex.lookup.PokedexLookup(index_dir, session=session)

    if recreate:
        lookup.rebuild_index()

    return lookup

def get_csv_directory(options):
    """Prints and returns the csv directory we're about to use."""

    if not options.verbose:
        return

    csvdir = options.directory
    got_from = 'command line'

    if csvdir is None:
        csvdir, got_from = defaults.get_default_csv_dir_with_origin()

    print "Using CSV directory %(csvdir)s (from %(got_from)s)" \
        % dict(csvdir=csvdir, got_from=got_from)

    return csvdir


### Plumbing commands

def command_dump(*args):
    parser = get_parser(verbose=True)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    parser.add_option('-l', '--langs', dest='langs', default=None,
        help="Comma-separated list of languages to dump all strings for. "
            "Default is English ('en')")
    options, tables = parser.parse_args(list(args))

    session = get_session(options)
    get_csv_directory(options)

    if options.langs is not None:
        langs = [l.strip() for l in options.langs.split(',')]
    else:
        langs = None

    pokedex.db.load.dump(session, directory=options.directory,
                                  tables=tables,
                                  verbose=options.verbose,
                                  langs=langs)

def command_load(*args):
    parser = get_parser(verbose=True)
    parser.add_option('-d', '--directory', dest='directory', default=None)
    parser.add_option('-D', '--drop-tables', dest='drop_tables', default=False, action='store_true')
    parser.add_option('-r', '--recursive', dest='recursive', default=False, action='store_true')
    parser.add_option('-S', '--safe', dest='safe', default=False, action='store_true',
        help="Do not use backend-specific optimalizations.")
    parser.add_option('-l', '--langs', dest='langs', default=None,
        help="Comma-separated list of extra languages to load, or 'none' for none. "
            "Default is to load 'em all. Example: 'fr,de'")
    options, tables = parser.parse_args(list(args))

    if not options.engine_uri:
        print "WARNING: You're reloading the default database, but not the lookup index.  They"
        print "         might get out of sync, and pokedex commands may not work correctly!"
        print "To fix this, run `pokedex reindex` when this command finishes.  Or, just use"
        print "`pokedex setup` to do both at once."
        print

    if options.langs == 'none':
        langs = []
    elif options.langs is None:
        langs = None
    else:
        langs = [l.strip() for l in options.langs.split(',')]

    session = get_session(options)
    get_csv_directory(options)

    pokedex.db.load.load(session, directory=options.directory,
                                  drop_tables=options.drop_tables,
                                  tables=tables,
                                  verbose=options.verbose,
                                  safe=options.safe,
                                  recursive=options.recursive,
                                  langs=langs)

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
    get_csv_directory(options)
    pokedex.db.load.load(session, directory=None, drop_tables=True,
                                  verbose=options.verbose,
                                  safe=False)

    lookup = get_lookup(options, session=session, recreate=True)

    print "Recreated lookup index."


def command_status(*args):
    parser = get_parser(verbose=True)
    options, _ = parser.parse_args(list(args))
    options.verbose = True
    options.directory = None

    # Database, and a lame check for whether it's been inited at least once
    session = get_session(options)
    print "  - OK!  Connected successfully."

    if pokedex.db.tables.Pokemon.__table__.exists(session.bind):
        print "  - OK!  Database seems to contain some data."
    else:
        print "  - WARNING: Database appears to be empty."

    # CSV; simple checks that the dir exists
    csvdir = get_csv_directory(options)
    if not os.path.exists(csvdir):
        print "  - ERROR: No such directory!"
    elif not os.path.isdir(csvdir):
        print "  - ERROR: Not a directory!"
    else:
        print "  - OK!  Directory exists."

        if os.access(csvdir, os.R_OK):
            print "  - OK!  Can read from directory."
        else:
            print "  - ERROR: Can't read from directory!"

        if os.access(csvdir, os.W_OK):
            print "  - OK!  Can write to directory."
        else:
            print "  - WARNING: Can't write to directory!  " \
                "`dump` will not work.  You may need to sudo."

    # Index; the PokedexLookup constructor covers most tests and will
    # cheerfully bomb if they fail
    lookup = get_lookup(options, recreate=False)
    print "  - OK!  Opened successfully."


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


def command_pkm(*args):
    if args and args[0] == 'encode':
        mode = 'encode'
    elif args and args[0] == 'decode':
        mode = 'decode'
    else:
        print textwrap.dedent(u"""
            Convert binary Pokémon data (aka PKM files) to/from JSON/YAML.
            usage: pokedex pkm (encode|decode) [options] <file> ...

            Commands:
                encode         Convert a JSON or YAML representation of a
                               Pokémon to the binary format.
                decode         Convert the binary format to a JSON/YAML
                               representation.

            Options:
                --gen=NUM, -g  Generation to use (4 or 5)
                --format=FORMAT, -f FORMAT
                               Select the human-readable format to use.
                               FORMAT can be:
                               json (default): use JSON.
                               yaml: use YAML. Needs the PyYAML library
                                   installed.
                               python: use Python literal syntax
                --crypt, -c    Use encrypted binary format.
                --base64, -b   Use Base64 encoding for the binary format.
                --binary, -B   Output raw binary data. This is the default,
                               but you need to specify -B explicitly if you're
                               dumping binary data to a terminal.

            If no files are given, reads from standard input.
            """).encode(sys.getdefaultencoding(), 'replace')
        return
    parser = get_parser(verbose=False)
    parser.add_option('-g', '--gen', default=5, type=int)
    parser.add_option('-c', '--crypt', action='store_true')
    parser.add_option('-f', '--format', default='json')
    parser.add_option('-b', '--base64', action='store_true', default=None)
    parser.add_option('-B', '--no-base64', action='store_false', dest='base64')
    options, files = parser.parse_args(list(args[1:]))

    session = get_session(options)
    cls = pokedex.struct.save_file_pokemon_classes[options.gen]
    if options.format == 'yaml':
        import yaml

        # Override the default string handling function
        # to always return unicode objects.
        # Inspired by http://stackoverflow.com/questions/2890146
        # This prevents str/unicode SQLAlchemy warnings.
        def construct_yaml_str(self, node):
            return self.construct_scalar(node)
        class UnicodeLoader(yaml.SafeLoader):
            pass
        UnicodeLoader.add_constructor(u'tag:yaml.org,2002:str',
            construct_yaml_str)

    if options.format not in ('yaml', 'json', 'python'):
        raise parser.error('Bad "format"')

    if mode == 'encode' and options.base64 is None:
        try:
            isatty = sys.stdout.isatty
        except AttributeError:
            pass
        else:
            if isatty():
                parser.error('Refusing to dump binary data to terminal. '
                    'Please use -B to override, or -b for base64.')

    if not files:
        # Use sys.stdin in place of name, handle specially later
        files = [sys.stdin]

    for filename in files:
        if filename is sys.stdin:
            content = sys.stdin.read()
        else:
            with open(filename) as f:
                content = f.read()
        if mode == 'encode':
            if options.format == 'yaml':
                dict_ = yaml.load(content, Loader=UnicodeLoader)
            elif options.format == 'json':
                dict_ = json.loads(content)
            elif options.format == 'python':
                dict_ = ast.literal_eval(content)
            struct = cls(session=session, dict_=dict_)
            if options.crypt:
                data = struct.as_encrypted
            else:
                data = struct.as_struct
            if options.base64:
                print base64.b64encode(data)
            else:
                sys.stdout.write(data)
        else:
            if options.base64:
                content = base64.b64decode(content)
            struct = cls(
                blob=content, encrypted=options.crypt, session=session)
            dict_ = struct.export_dict()
            if options.format == 'yaml':
                print yaml.safe_dump(dict_, explicit_start=True),
            elif options.format == 'json':
                print json.dumps(dict_),
            elif options.format == 'python':
                pprint.pprint(dict_)


def command_help():
    print u"""pokedex -- a command-line Pokédex interface
usage: pokedex {command} [options...]
Run `pokedex setup` first, or nothing will work!
See https://github.com/veekun/pokedex/wiki/CLI for more documentation.

Commands:
    help                Displays this message.
    lookup [thing]      Look up something in the Pokédex.
    pkm                 Binary Pokémon format encoding/decoding. (experimental)

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

Load options:
    -D|--drop-tables    Drop all tables before loading data.
    -S|--safe           Disable engine-specific optimizations.
    -r|--recursive      Load (and drop) all dependent tables.
    -l|--langs          Load translations for the given languages.
                        By default, all available translations are loaded.
                        Separate multiple languages by a comma (-l en,de,fr)

Dump options:
    -l|--langs          Dump unofficial texts for given languages.
                        By default, English (en) is dumped.
                        Separate multiple languages by a comma (-l en,de,fr)
                        Use 'none' to not dump any unofficial texts.

    Additionally, load and dump accept a list of table names (possibly with
    wildcards) and/or csv fileames as an argument list.
""".encode(sys.getdefaultencoding(), 'replace')

    sys.exit(0)


if __name__ == '__main__':
    main(*sys.argv)
