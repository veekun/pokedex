from pokedex.search import search


def configure_parser(parser):
    parser.set_defaults(func=command_search)

    parser.add_argument('--name', default=None)

    parser.add_argument('--attack', '--atk', dest='attack', default=None)
    parser.add_argument('--defense', '--def', dest='defense', default=None)
    parser.add_argument('--special-attack', '--spatk', dest='special-attack', default=None)
    parser.add_argument('--special-defense', '--spdef', dest='special-defense', default=None)
    parser.add_argument('--speed', dest='speed', default=None)
    parser.add_argument('--hp', dest='hp', default=None)


def command_search(parser, args):
    from pokedex.main import get_session
    session = get_session(args)
    results = search(session, **vars(args))
    for result in results:
        print(result.name)
