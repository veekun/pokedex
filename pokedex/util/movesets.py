#! /usr/bin/env python
# Encoding: UTF-8

import sys
import argparse
from collections import defaultdict

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import not_, and_, or_

from pokedex.db import connect, tables, util

from pokedex.util import querytimer
from pokedex.util.astar import a_star

class IllegalMoveCombination(ValueError): pass
class TooManyMoves(IllegalMoveCombination): pass
class NoMoves(IllegalMoveCombination): pass
class MovesNotLearnable(IllegalMoveCombination): pass
class NoParent(IllegalMoveCombination): pass
class TargetExcluded(IllegalMoveCombination): pass

class MovesetSearch(object):
    def __init__(self, session, pokemon, version, moves, level=100, costs=None,
            exclude_versions=(), exclude_pokemon=(), debug=False):

        self.generator = self.error = None

        if not moves:
            self.error = NoMoves('No moves specified.')
            return
        elif len(moves) > 4:
            self.error = NoMoves('Too many moves specified.')
            return

        self.debug = debug

        self.session = session

        if costs is None:
            self.costs = default_costs
        else:
            self.costs = costs

        self.excluded_families = frozenset(p.evolution_chain_id
                for p in exclude_pokemon)

        if pokemon:
            self.goal_evolution_chain = pokemon.evolution_chain_id
            if self.goal_evolution_chain in self.excluded_families:
                self.error = TargetExcluded('The target pokemon was excluded.')
                return
        else:
            self.goal_evolution_chain = None

        if debug:
            print 'Specified moves:', [move.id for move in moves]

        self.goal_moves = frozenset(move.id for move in moves)
        self.goal_version_group = version.version_group_id

        # Fill self.generation_id_by_version_group
        self.load_version_groups(version.version_group_id,
                [v.version_group_id for v in exclude_versions])

        self.pokemon_moves = defaultdict(  # key: pokemon
                lambda: defaultdict(  # key: move
                    lambda: defaultdict(  # key: version_group
                        lambda: defaultdict(  # key: method
                            list))))  # list of (level, cost)
        self.movepools = defaultdict(dict)  # evo chain -> move -> best cost
        self.learnpools = defaultdict(set)  # as above, but not egg moves

        easy_moves, non_egg_moves = self.load_pokemon_moves(
                self.goal_evolution_chain, 'family')

        hard_moves = self.goal_moves - easy_moves
        egg_moves = self.goal_moves - non_egg_moves
        if hard_moves:
            # Have to breed!
            self.load_pokemon_moves(self.goal_evolution_chain, 'others')

    def load_version_groups(self, version, excluded):
        query = self.session.query(tables.VersionGroup.id,
                tables.VersionGroup.generation_id)
        query = query.join(tables.Version.version_group)
        if excluded:
            query = query.filter(not_(tables.VersionGroup.id.in_(excluded)))
        self.generation_id_by_version_group = dict(query)
        def expand(v2):
            for v1 in self.generation_id_by_version_group:
                if self.trade_cost(v1, v2):
                    yield 0, None, v1
        def is_goal(v):
            return True
        goal = self.goal_version_group
        filtered_map = {goal: self.generation_id_by_version_group[goal]}
        for result in a_star(self.goal_version_group, expand, is_goal):
            for cost, transition, version in result:
                filtered_map[version] = (
                        self.generation_id_by_version_group[version])
        self.generation_id_by_version_group = filtered_map
        if self.debug:
            print 'Excluded version groups:', excluded
            print 'Trade cost table:'
            print '%03s' % '',
            for g1 in sorted(self.generation_id_by_version_group):
                print '%03s' % g1,
            print
            for g1 in sorted(self.generation_id_by_version_group):
                print '%03s' % g1,
                for g2 in sorted(self.generation_id_by_version_group):
                    print '%03s' % (self.trade_cost(g1, g2) or '---'),
                print

    def load_pokemon_moves(self, evolution_chain, selection):
        """Load pokemon_moves, movepools, learnpools

        `selection`:
            'family' for loading only pokemon in evolution_chain
            'others' for loading only pokemon NOT in evolution_chain

        Returns: (easy_moves, non_egg_moves)
        If `selection` == 'family':
            easy_moves is a set of moves that are easier to obtain than by
                breeding
            non_egg_moves is a set of moves that don't require breeding
        Otherwise, these are empty sets.
        """
        if self.debug:
            print 'Loading moves, c%s %s' % (evolution_chain, selection)
        query = self.session.query(
                tables.PokemonMove.pokemon_id,
                tables.PokemonMove.move_id,
                tables.PokemonMove.version_group_id,
                tables.PokemonMoveMethod.identifier,
                tables.PokemonMove.level,
                tables.Pokemon.evolution_chain_id,
            )
        query = query.join(tables.PokemonMove.pokemon)
        query = query.filter(tables.PokemonMoveMethod.id == 
                tables.PokemonMove.pokemon_move_method_id)
        query = query.filter(tables.PokemonMove.version_group_id.in_(
                set(self.generation_id_by_version_group)))
        query = query.filter(or_(
                    tables.PokemonMove.level > 100,  # XXX: Chaff?
                    tables.PokemonMove.move_id.in_(self.goal_moves),
                ))
        if self.excluded_families:
            query = query.filter(not_(tables.Pokemon.evolution_chain_id.in_(
                    self.excluded_families)))
        if evolution_chain:
            if selection == 'family':
                query = query.filter(tables.Pokemon.evolution_chain_id == (
                        evolution_chain))
            elif selection == 'others':
                query = query.filter(tables.Pokemon.evolution_chain_id != (
                        evolution_chain))
        query = query.order_by(tables.PokemonMove.level)
        easy_moves = set()
        non_egg_moves = set()
        for pokemon, move, vg, method, level, chain in query:
            if move in self.goal_moves:
                cost = self.learn_cost(method, vg)
                self.movepools[chain][move] = min(
                        self.movepools[chain].get(move, cost), cost)
                if method != 'egg':
                    self.learnpools[chain].add(move)
                    non_egg_moves.add(move)
                    if cost < self.costs['breed']:
                        easy_moves.add(move)
            else:
                cost = 0
            self.pokemon_moves[pokemon][move][vg][method].append((level, cost))
        if self.debug and selection == 'family':
            print 'Easy moves:', sorted(easy_moves)
            print 'Non-egg moves:', sorted(non_egg_moves)
        return easy_moves, non_egg_moves

    def learn_cost(self, method, version_group):
        """Return cost of learning a move by method (identifier) in ver. group
        """
        if method == 'level-up':
            return self.costs['level-up']
        gen = self.generation_id_by_version_group[version_group]
        if method == 'machine' and gen < 5:
            return self.costs['machine-once']
        elif method == 'tutor' and gen == 3:
            return self.costs['tutor-once']
        elif method == 'egg':
            return self.costs['breed']
        else:
            return self.costs[method]

    def trade_cost(self, version_group_from, version_group_to, *thing_generations):
        """Return cost of trading between versions, None if impossibble

        `thing_generations` should be the generation IDs of the pokemon and
        moves being traded.
        """
        # XXX: this ignores HM transfer restrictions
        gen_from = self.generation_id_by_version_group[version_group_from]
        gen_to = self.generation_id_by_version_group[version_group_to]
        if gen_from == gen_to:
            return self.costs['trade']
        elif any(gen > gen_to for gen in thing_generations):
            return None
        elif gen_from in (1, 2):
            if gen_to in (1, 2):
                return self.costs['trade']
            else:
                return None
        elif gen_to in (1, 2):
            return None
        elif gen_from > gen_to:
            return None
        elif gen_from < gen_to - 1:
            return None
        else:
            return self.costs['trade'] + self.costs['transfer']

default_costs = {
    # Costs for learning a move in verious ways
    'level-up': 20,  # The normal way
    'machine': 40,  # Machines are slightly inconvenient.
    'machine-once': 2000,  # before gen. 5, TMs only work once. Avoid.
    'tutor': 60,  # Tutors are slightly more inconvenient than TMs – can't carry them around
    'tutor-once': 2100,  # gen III: tutors only work once (well except Emerald frontier ones)
    'sketch': 10,  # Quite cheap. (Doesn't include learning Sketch itself)

    # Gimmick moves – we need to use this method to learn the move anyway,
    # so make a big-ish dent in the score if missing
    'stadium-surfing-pikachu': 100,
    'light-ball-egg': 100,  #  … 

    # Ugh... I don't know?
    'colosseum-purification': 100,
    'xd-shadow': 100,
    'xd-purification': 100,
    'form-change': 100,

    # Other actions.
    # Breeding should cost more than 3 times than a lv-up/machine/tutor move.
    'evolution': 100,  # We have to do this anyway, usually.
    'evolution-delayed': 50,  # *in addition* to evolution. Who wants to mash B on every level.
    'breed': 400,  # Breeding's a pain.
    'trade': 200,  # Trading's a pain, but not as much as breeding.
    'transfer': 200,  # *in addition* to trade. For one-way cross-generation transfers
    'delete': 300,  # Deleting a move. (Not needed unless deleting an evolution move.)
    'relearn': 150,  # Also a pain, though not as big as breeding.
    'per-level': 1,  # Prefer less grinding. This is for all lv-ups but the final “grow”
}

def main(argv):
    parser = argparse.ArgumentParser(description=
        'Find out if the specified moveset is valid, and provide a suggestion '
        'on how to obtain it.')

    parser.add_argument('pokemon', metavar='POKEMON', type=unicode,
        help='Pokemon to check the moveset for')

    parser.add_argument('move', metavar='MOVE', type=unicode, nargs='*',
        help='Moves in the moveset')

    parser.add_argument('-l', '--level', metavar='LV', type=int, default=100,
        help='Level of the pokemon')

    parser.add_argument('-v', '--version', metavar='VER', type=unicode,
        default='black',
        help='Version to search in.')

    parser.add_argument('-V', '--exclude-version', metavar='VER', type=unicode,
        action='append', default=[],
        help='Versions to exclude (along with their '
            'counterparts, if any, e.g. `black` will also exclude White).')

    parser.add_argument('-P', '--exclude-pokemon', metavar='PKM', type=unicode,
        action='append', default=[],
        help='Pokemon to exclude (along with their families, e.g. `pichu` '
            'will also exclude Pikachu and Raichu).')

    parser.add_argument('-d', '--debug', action='append_const', const=1,
        default=[],
        help='Output timing and debugging information (can be specified more '
            'than once).')

    args = parser.parse_args(argv)
    args.debug = len(args.debug)

    if args.debug:
        print 'Connecting'

    session = connect(engine_args={'echo': args.debug > 1})

    if args.debug:
        print 'Parsing arguments'

    def _get_list(table, idents, name):
        result = []
        for ident in idents:
            try:
                result.append(util.get(session, table, identifier=ident))
            except NoResultFound:
                print>>sys.stderr, ('%s %s not found. Please use '
                        'the identifier.' % (name, ident))
                return 2
        return result

    pokemon = _get_list(tables.Pokemon, [args.pokemon], 'Pokemon')[0]
    moves = _get_list(tables.Move, args.move, 'Move')
    version = _get_list(tables.Version, [args.version], 'Version')[0]
    excl_versions = _get_list(tables.Version, args.exclude_version, 'Version')
    excl_pokemon = _get_list(tables.Pokemon, args.exclude_pokemon, 'Pokemon')

    if args.debug:
        print 'Starting search'

    search = MovesetSearch(session, pokemon, version, moves, args.level,
        exclude_versions=excl_versions, exclude_pokemon=excl_pokemon,
        debug=args.debug)

    if search.error:
        print 'Error:', search.error
        return 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
