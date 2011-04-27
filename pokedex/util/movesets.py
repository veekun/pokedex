#! /usr/bin/env python
# Encoding: UTF-8

import sys
import argparse
import itertools
import heapq
from collections import defaultdict, namedtuple

from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import not_, and_, or_

from pokedex.db import connect, tables, util

###
### Illegal Moveset exceptions
###

class IllegalMoveCombination(ValueError): pass
class TooManyMoves(IllegalMoveCombination): pass
class NoMoves(IllegalMoveCombination): pass
class MovesNotLearnable(IllegalMoveCombination): pass
class NoParent(IllegalMoveCombination): pass
class TargetExcluded(IllegalMoveCombination): pass
class DuplicateMoves(IllegalMoveCombination): pass

###
### Generic helpers
###

def powerset(iterable):
    # recipe from: http://docs.python.org/library/itertools.html
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r)
            for r in range(len(s)+1))

###
### Search information object
###

class MovesetSearch(object):
    def __init__(self, session, pokemon, version, moves, level=100, costs=None,
            exclude_versions=(), exclude_pokemon=(), debug_level=False):

        self.generator = None

        if not moves:
            raise NoMoves('No moves specified.')
        elif len(moves) > 4:
            raise NoMoves('Too many moves specified.')

        self.debug_level = debug_level

        self.session = session

        self.sketch = util.get(session, tables.Move, identifier=u'sketch').id
        self.unsketchable = set([
                util.get(session, tables.Move, identifier=u'struggle').id,
                util.get(session, tables.Move, identifier=u'chatter').id,
            ])
        self.no_eggs_group = util.get(session, tables.EggGroup,
                identifier=u'no-eggs').id
        self.ditto_group = util.get(session, tables.EggGroup,
                identifier=u'ditto').id

        if costs is None:
            self.costs = default_costs
        else:
            self.costs = costs

        self.load_pokemon()
        self.load_moves()

        self.excluded_families = frozenset(p.evolution_chain_id
                for p in exclude_pokemon)

        if debug_level > 1:
            print 'Specified moves:', [move.id for move in moves]

        self.goal_pokemon = pokemon.id
        self.goal_moves = frozenset(move.id for move in moves)
        self.goal_version_group = version.version_group_id
        self.goal_level = level

        if len(self.goal_moves) < len(moves):
            raise DuplicateMoves('Cannot learn duplicate moves')

        if pokemon:
            self.goal_evolution_chain = pokemon.evolution_chain_id
            if self.goal_evolution_chain in self.excluded_families:
                raise TargetExcluded('The target pokemon was excluded.')
        else:
            self.goal_evolution_chain = None

        # Fill self.generation_id_by_version_group
        self.load_version_groups(version.version_group_id,
                [v.version_group_id for v in exclude_versions])

        self.pokemon_moves = defaultdict(  # key: pokemon
                lambda: defaultdict(  # key: version_group
                    lambda: defaultdict(  # key: move
                        lambda: defaultdict(  # key: method
                            list))))  # ordered list of (level, cost)
        self.movepools = defaultdict(dict)  # evo chain -> move -> best cost
        self.learnpools = defaultdict(set)  # evo chain -> move, w/o egg moves

        easy_moves, non_egg_moves = self.load_pokemon_moves(
                self.goal_evolution_chain, 'family')

        self.hard_moves = self.goal_moves - easy_moves
        self.egg_moves = self.goal_moves - non_egg_moves
        if self.hard_moves:
            # Have to breed!
            self.load_pokemon_moves(self.goal_evolution_chain, 'others')

        self.construct_breed_graph()

        self.find_duplicate_versions()

        self.output_objects = dict()

        kwargs = dict()
        if debug_level:
            self._astar_debug_notify_counter = 0
            kwargs['notify'] = self.astar_debug_notify
            kwargs['estimate_error_callback'] = self.astar_estimate_error
        self.generator = InitialNode(self).find_all_paths(**kwargs)

    def load_version_groups(self, version, excluded):
        """Load generation_id_by_version_group
        """
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
        if self.debug_level > 1:
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
        """Load pokemon_moves, movepools, learnpools, smeargle_families

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
        if self.debug_level > 1:
            print 'Loading pokemon moves, %s %s' % (evolution_chain, selection)
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
                    tables.PokemonMove.move_id == self.sketch,
                    tables.PokemonMove.move_id.in_(
                            self.evolution_moves.values()),
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
        self.smeargle_families = set()
        costs = self.costs
        movepools = self.movepools
        learnpools = self.learnpools
        sketch_cost = costs['sketch']
        breed_cost = costs['breed']
        for pokemon, move, vg, method, level, chain in query:
            if move in self.goal_moves:
                if method == 'level-up':
                    cost = costs['level-up']
                else:
                    gen = self.generation_id_by_version_group[vg]
                    if method == 'machine' and gen < 5:
                        cost = costs['machine-once']
                    elif method == 'tutor' and gen == 3:
                        cost = costs['tutor-once']
                    elif method == 'egg':
                        cost = costs['breed']
                    else:
                        cost = costs[method]
                movepools[chain][move] = min(
                        movepools[chain].get(move, cost), cost)
                if method != 'egg':
                    learnpools[chain].add(move)
                    non_egg_moves.add(move)
                    if cost < breed_cost:
                        easy_moves.add(move)
            elif move == self.sketch:
                cost = sketch_cost
                self.smeargle_families.add(self.evolution_chains[pokemon])
            else:
                # An evolution move. We need to use it anyway if we need
                # the evolution, so the cost can be an arbitrary positive
                # number. But, do check if this family actually needs the move.
                evolution_chain = self.evolution_chains[pokemon]
                if move != self.evolution_moves.get(evolution_chain):
                    continue
                cost = 1
            self.pokemon_moves[pokemon][vg][move][method].append((level, cost))
        if self.debug_level > 1 and selection == 'family':
            print 'Easy moves:', sorted(easy_moves)
            print 'Non-egg moves:', sorted(non_egg_moves)
        if self.debug_level > 1:
            print 'Smeargle families:', sorted(self.smeargle_families)
        return easy_moves, non_egg_moves

    def trade_cost(self, version_group_from, version_group_to, max_generation=None):
        """Return cost of trading between versions, None if impossibble

        `max_generation` should be the maximum generation of the moves traded.
            (also of pokemon, if those aren't checked another way)
        """
        # XXX: this ignores HM transfer restrictions
        gen_from = self.generation_id_by_version_group[version_group_from]
        gen_to = self.generation_id_by_version_group[version_group_to]
        if gen_from == gen_to:
            return self.costs['trade']
        elif gen_from in (1, 2):
            if max_generation and max_generation > gen_to:
                return None
            elif gen_to in (1, 2):
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

    def load_pokemon(self):
        """Load pokemon breed groups and evolutions

        self.egg_groups: maps evolution chains to their sorted egg groups
            (wil contain empty tuple for no-eggs or ditto)
        self.evolution_chains: maps pokemon to their evolution chains
        self.pokemon_by_evolution_chain: maps evolution chains to their pokemon
        self.unbreedable: set of unbreedable pokemon

        self.evolution_parents[pokemon] = the pre-evolved form
        self.evolutions[pokemon] = list of (trigger, move, level, child)
        self.evolution_moves[evolution_chain] = move required for evolution
        self.babies[egg_group_id] = set of baby pokemon
        self.hatch_counters[pokemon] = hatch counter
        self.gender_rates[evolution_chain] = gender rate
        """
        eg1 = tables.PokemonEggGroup
        eg2 = aliased(tables.PokemonEggGroup)
        query = self.session.query(
                tables.Pokemon.id,
                tables.Pokemon.evolution_chain_id,
                tables.Pokemon.evolves_from_pokemon_id,
                eg1.egg_group_id,
                eg2.egg_group_id,
                tables.EvolutionChain.baby_trigger_item_id,
                tables.Pokemon.hatch_counter,
                tables.Pokemon.gender_rate,
            )
        query = query.join(tables.Pokemon.evolution_chain)
        query = query.join((eg1, eg1.pokemon_id == tables.Pokemon.id))
        query = query.outerjoin((eg2, and_(
                eg2.pokemon_id == tables.Pokemon.id,
                eg1.egg_group_id < eg2.egg_group_id,
            )))
        bad_groups = (self.no_eggs_group, self.ditto_group)
        unbreedable = dict()  # pokemon->evolution chain
        self.evolution_parents = dict()
        self.egg_groups = defaultdict(tuple)
        self.evolution_chains = dict()
        self.pokemon_by_evolution_chain = defaultdict(set)
        self.babies = defaultdict(set)
        self.hatch_counters = dict()
        self.gender_rates = dict()
        item_baby_chains = set()  # evolution chains with baby-trigger items
        for pokemon, evolution_chain, parent, g1, g2, baby_item, hatch_counter, gender_rate in query:
            self.hatch_counters[pokemon] = hatch_counter
            self.gender_rates[evolution_chain] = gender_rate
            if g1 in bad_groups:
                unbreedable[pokemon] = evolution_chain
            else:
                groups = (g1, g2) if g2 else (g1, )
                if len(self.egg_groups.get(evolution_chain, ())) <= len(groups):
                    self.egg_groups[evolution_chain] = groups
                for group in groups:
                    self.babies[group].add(pokemon)
            self.evolution_chains[pokemon] = evolution_chain
            self.pokemon_by_evolution_chain[evolution_chain].add(pokemon)
            if parent:
                self.evolution_parents[pokemon] = parent
                if baby_item:
                    item_baby_chains.add(evolution_chain)
        self.unbreedable = frozenset(unbreedable)

        self.evolutions = defaultdict(set)
        self.evolution_moves = dict()
        query = self.session.query(
                tables.PokemonEvolution.evolved_pokemon_id,
                tables.EvolutionTrigger.identifier,
                tables.PokemonEvolution.known_move_id,
                tables.PokemonEvolution.minimum_level,
            )
        query = query.join(tables.PokemonEvolution.trigger)
        for child, trigger, move, level in query:
            self.evolutions[self.evolution_parents[child]].add(
                    (trigger, move, level, child))
            if move:
                self.evolution_moves[self.evolution_chains[child]] = move

        if self.debug_level > 1:
            print 'Loaded %s pokemon: %s evo; %s families: %s breedable' % (
                    len(self.evolution_chains),
                    len(self.pokemon_by_evolution_chain),
                    len(self.egg_groups),
                    len(self.evolutions),
                )
            print 'Evolution moves: %s' % self.evolution_moves

        # Chains with unbreedable babies
        for baby, evolution_chain in unbreedable.items():
            if baby not in self.evolution_parents:
                groups = self.egg_groups[evolution_chain]
                for group in groups:
                    self.babies[group].add(baby)

        # Chains with item-triggered alternate babies
        for item_baby_chain in item_baby_chains:
            for item_baby in self.pokemon_by_evolution_chain[item_baby_chain]:
                if item_baby not in self.evolution_parents:
                    for regular_baby in self.evolutions[item_baby]:
                        for group in self.egg_groups[item_baby_chain]:
                            self.babies[group].add(pokemon)

    def load_moves(self):
        """Load move_generations"""
        query = self.session.query(
                tables.Move.id,
                tables.Move.generation_id,
            )
        self.move_generations = dict(query)

        if self.debug_level > 1:
            print 'Loaded %s moves' % len(self.move_generations)

    def construct_breed_graph(self):
        """Fills breeds_required

        breeds_required[egg_group][moveset] = minimum number of breeds needed
            from a pokemon in this group with this moveset to the goal pokemon
            with the goal moveset.
            The score cannot get lower by learning new moves, only by breeding.
            If missing, breeding or raising the pokemon won't do any good.
        Exceptions:
            For pokemon in the target family, breeds_required doesn't apply.
            For the empty moveset just check if any moveset is worthwhile (i.e.
            bool(breeds_required[egg_group])).
        """

        # Part I. Determining what moves can be passed/learned

        # eg1_movepools[egg_group_id] = set of moves passable by pkmn in that group
        eg1_movepools = defaultdict(set)
        # eg2_movepools[b_g_id1, b_g_id2] = ditto for pkmn in *both* groups
        eg2_movepools = defaultdict(set)
        # non_egg_pools = as eg1_movepools but for *learnable* moves
        learn_pools = defaultdict(set)

        goal_egg_groups = self.egg_groups[self.goal_evolution_chain]
        all_groups = set()

        for family, groups in self.egg_groups.iteritems():
            if not groups:
                continue
            if family == self.goal_evolution_chain:
                continue
            elif family in self.smeargle_families:
                pool = self.goal_moves
            else:
                pool = self.movepools[family]
                pool = set(pool) & self.goal_moves
            learnpool = self.learnpools[family] & pool
            for group in groups:
                eg1_movepools[group].update(pool)
                learn_pools[group].update(learnpool)
                all_groups.add(group)
            if len(groups) >= 2:
                eg2_movepools[groups].update(pool)

        if self.debug_level > 1:
            print 'Egg group summary:'
            for group in sorted(all_groups):
                print "%2s can pass: %s" % (group, sorted(eg1_movepools[group]))
                if learn_pools[group] != eg1_movepools[group]:
                    print "  but learn: %s" % sorted(learn_pools[group])
            for g2 in sorted(all_groups):
                for g1 in sorted(all_groups):
                    if eg2_movepools[g1, g2]:
                        print " %2s/%2s pass: %s" % (g1, g2, sorted(eg2_movepools[g1, g2]))
            print 'Goal groups:', goal_egg_groups

        # Part II. Determining which moves are worthwhile to pass

        # We want *all* paths, not just shortest ones, so use DFS.
        breeds_required = defaultdict(dict)
        def handle(group, moves, path):
            """
            group: the group of the parent
            moves: moves the parent should pass down
            path: previously visited groups - to prevent cycles
            """
            if not moves:
                # No more moves needed to pass down: success!
                return True
            if breeds_required[group].get(moves, 999) <= len(path):
                # Already done
                return True
            success = False
            # Breed some more
            path = path + (group, )
            for new_group in all_groups.difference(path):
                new_groups = tuple(sorted([group, new_group]))
                # Can we pass down all the requested moves?
                if moves.issubset(eg1_movepools[new_group]):
                    # Learn some of the moves: they don't have to be passed to us
                    for learned in powerset(moves & learn_pools[new_group]):
                        new_moves = moves.difference(learned)
                        local_success = handle(new_group, new_moves, path)
                        # If this chain eventually ended up being successful,
                        # it means that it is useful to pass this moveset
                        # to this group.
                        if local_success:
                            breeds_required[group][moves] = min(breeds_required[group].get(moves, 999), len(path) - 1)
                            success = True
            return success
        for group in goal_egg_groups:
            handle(group, self.hard_moves, ())
            for moves in powerset(self.goal_moves):
                if moves:
                    breeds_required[group][frozenset(moves)] = 1
        self.breeds_required = breeds_required

        if self.debug_level > 1:
            for group, movesetlist in breeds_required.items():
                print 'From egg group', group
                for moveset, cost in movesetlist.items():
                    print "   %s breeds with %s" % (cost, sorted(moveset))

    def find_duplicate_versions(self):
        """Fill `duplicate_versions`

        duplicate_versions[pokemon][version_group] = set of version groups that
            are identical as far as the pokemon learning those moves is
            concerned, and are in the same generation.
            Thus, trading between them is unnecessary.
        """
        self.duplicate_versions = dict()

        counter = 0
        for pokemon, vg_moves in self.pokemon_moves.items():
            dupes = self.duplicate_versions[pokemon] = dict()
            last = None
            last_moves = None
            last_gen = None
            for version_group, moves in vg_moves.items():
                gen = self.generation_id_by_version_group[version_group]
                if gen == last_gen and moves == last_moves:
                    last.add(version_group)
                    dupes[version_group] = last
                    counter += 1
                else:
                    last = set([version_group])
                    dupes[version_group] = last
                    last_moves = moves
                    last_gen = gen

        if self.debug_level > 1:
            print 'Deduplicated %s version groups' % counter

    def astar_debug_notify(self, cost, node, setsize, heapsize):
        counter = self._astar_debug_notify_counter
        if counter % 100 == 0:
            print 'A* iteration %s, cost %s; remaining: %s (%s)     \r' % (
                    counter, cost, setsize, heapsize),
            sys.stdout.flush()
        self._astar_debug_notify_counter += 1

    def astar_estimate_error(self, result):
        print '**warning: bad A* estimate**'
        print_result(result)

    def __iter__(self):
        return self.generator

    def get_by_id(self, table, id):
        key = table, 'id', id
        try:
            return self.output_objects[key]
        except KeyError:
            o = self.output_objects[key] = util.get(self.session, table, id=id)
            return o

    def get_by_identifier(self, table, ident):
        key = table, 'identifier', ident
        try:
            return self.output_objects[key]
        except KeyError:
            o = self.output_objects[key] = util.get(self.session,
                    table, identifier=ident)
            return o

    def get_list(self, table, ids):
        key = table, 'list', ids
        try:
            return self.output_objects[key]
        except KeyError:
            o = self.output_objects[key] = sorted(
                    (util.get(self.session, table, id=id) for id in ids),
                    key=lambda x: x.identifier)
            return o

###
### Costs
###

default_costs = {
    # Costs for learning a move in various ways
    'level-up': 20,  # The normal way
    'machine': 40,  # Machines are slightly inconvenient.
    'machine-once': 2000,  # before gen. 5, TMs only work once. Avoid.
    'tutor': 60,  # Tutors are slightly more inconvenient than TMs – can't carry them around
    'tutor-once': 2100,  # gen III: tutors only work once (well except Emerald frontier ones)

    # For technical reasons, 'sketch' is also used for learning Sketch and
    # by normal means, if it isn't included in the target moveset.
    # So the actual cost of a sketched move will be double this number.
    'sketch': 1,  # Cheap. Exclude Smeargle if you think it's too cheap.

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
    # Breeding should cost more than 3 times a lv-up/machine/tutor move.
    'evolution': 100,  # We have to do this anyway, usually.
    'evolution-delayed': 50,  # *in addition* to evolution. Who wants to mash B on every level.
    'breed': 400,  # Breeding's a pain.
    'trade': 200,  # Trading's a pain, but not as much as breeding.
    'transfer': 150,  # *in addition* to trade. Keep it below 'trade'.
    'forget': 300,  # Deleting a move. (Not needed unless deleting an evolution move.)
    'relearn': 150,  # Also a pain, though not as big as breeding.
    'per-level': 1,  # Prefer less grinding. This is for all lv-ups but the final “grow”

    # Breeding for moves the target pokemon leans easily is kind of stupid.
    # (Though not *very* stupid, and since the program considers evolution
    # chains as a group, the penalty should be much smaller than normal move cost.)
    'egg': 3,  # General cost of breeding a move
    'per-hatch-counter': 1,  # penalty for 1 initial hatch counter point (these range from 5 to 120)

    # Penalty for *not* breeding a required egg move; this makes parents
    # with more required moves gain a big advantage over the competition
    'breed-penalty': 100,
}

###
### A*
###

class Node(object):
    """Node for the A* search algorithm.

    To get started, implement the `expand` method and call `search`.

    N.B. Node objects must be hashable.
    """

    def expand(self):
        """Return a list of (costs, transition, next_node) for next states

        "Next states" are those reachable from this node.

        May return any finite iterable.
        """
        raise NotImplementedError

    def estimate(self, goal):
        """Return an *optimistic* estimate of the cost to the given goal node.

        If there are multiple goal states, return the lowest estimate among all
        of them.
        """
        return 0

    def is_goal(self, goal):
        """Return true iff this is a goal node.
        """
        return self == goal

    def find_path(self, goal=None, **kwargs):
        """Return the best path to the goal

        Returns an iterator of (cost, transition, node) triples, in reverse
        order (i.e. the first element will have the total cost and goal node).

        If `goal` will be passed to the `estimate` and `is_goal` methods.

        See a_star for the advanced keyword arguments, `notify` and
        `estimate_error_callback`.
        """
        paths = self.find_all_paths(goal=goal, **kwargs)
        try:
            return paths.next()
        except StopIteration:
            return None

    def find_all_paths(self, goal=None, **kwargs):
        """Yield the best path to each goal

        Returns an iterator of paths. See the `search` method for how paths
        look.

        Giving the `goal` argument will cause it to search for that goal,
        instead of consulting the `is_goal` method.
        This means that if you wish to find more than one path, you must not
        pass a `goal` to this method, and instead reimplament `is_goal`.

        See a_star for the advanced keyword arguments, `notify` and
        `estimate_error_callback`.
        """
        return a_star(
                initial=self,
                expand=lambda s: s.expand(),
                estimate=lambda s: s.estimate(goal),
                is_goal=lambda s: s.is_goal(goal),
                **kwargs)

def a_star(initial, expand, is_goal, estimate=lambda x: 0, notify=None,
            estimate_error_callback=None):
    """A* search algorithm for a consistent heuristic

    General background: http://en.wikipedia.org/wiki/A*_search_algorithm

    This algorithm will work in large or infinite search spaces.

    This version of the algorithm is modified for multiple possible goals:
    it does not end when it reaches a goal. Rather, it yields the best path
    for each goal.
    (Exhausting the iterator is of course not recommended for large search
    spaces.)

    Returns an iterable of paths, where each path is an iterable of
    (cummulative cost, transition, node) triples representing the path to
    the goal. The transition is the one leading to the corresponding node.
    The path is in reverse order, thus its first element will contain the
    total cost and the goal node.
    The initial node is not included in the returned path.

    Arguments:

    `initial`: the initial node

    `expand`: function yielding a (cost of transition, transition, next node)
        triple for each node reachable from its argument.
        The `transition` element is application data; it is not touched, only
        returned as part of the best path.
    `estimate`: function(x) returning optimistic estimate of cost from node x
        to a goal. If not given, 0 will be used for estimates.
    `is_goal`: function(x) returning true iff x is a goal node

    `notify`: If given, if is called at each step with three arguments:
        - current cost (with estimate). The cost to the next goal will not be
            smaller than this.
        - current node
        - open set cardinality: roughly, an estimate of the size of the
            boundary between "explored" and "unexplored" parts of node space
        - debug: stats that be useful for debugging or tuning (in this
            implementation, this is the open heap size)
        The number of calls to notify or the current cost can be useful as
        stopping criteria; the other values may help in tuning estimators.

    `estimate_error_callback`: function handling cases where an estimate was
        detected not to be optimistic (as A* requires). The function is given a
        path (as would be returned by a_star, except it does not lead to a goal
        node). By default, nothing is done (indeed, an estimate that's not
        strictly optimistic can be useful, esp. if the optimal path is not
        required)
    """
    # g: best cummulative cost (from initial node) found so far
    # h: optimistic estimate of cost to goal
    # f: g + h
    closed = set()  # nodes we don't want to visit again
    est = estimate(initial)  # estimate total cost
    opened = _HeapDict() # node -> (f, g, h)
    opened[initial] = (est, 0, est)
    came_from = {initial: None}  # node -> (prev_node, came_from[prev_node])
    while True:  # _HeapDict will raise StopIteration for us
        x, (f, g, h) = opened.pop()
        closed.add(x)

        if notify is not None:
            notify(f, x, len(opened.dict), len(opened.heap))

        if is_goal(x):
            yield _trace_path(came_from[x])

        for cost, transition, y in expand(x):
            if y in closed:
                continue
            tentative_g = g + cost

            old_f, old_g, h = opened.get(y, (None, None, None))

            if old_f is None:
                h = estimate(y)
            elif tentative_g > old_g:
                continue

            came_from[y] = ((tentative_g, transition, y), came_from[x])
            new_f = tentative_g + h

            opened[y] = new_f, tentative_g, h

            if estimate_error_callback is not None and new_f < f:
                estimate_error_callback(_trace_path(came_from[y]))

def _trace_path(cdr):
    """Backtrace an A* result"""
    # Convert a lispy list to a pythony iterator
    while cdr:
        car, cdr = cdr
        yield car

class _HeapDict(object):
    """A custom parallel heap/dict structure -- the best of both worlds.

    This is NOT a general-purpose class; it only supports what a_star needs.
    """
    # The dict has the definitive contents
    # The heap has (value, key) pairs. It may have some extra elements.
    def __init__(self):
        self.dict = {}
        self.heap = []

    def __setitem__(self, key, value):
        self.dict[key] = value
        heapq.heappush(self.heap, (value, key))

    def __delitem__(self, key):
        del self.dict[key]

    def get(self, key, default):
        """Return value for key, or default if not found
        """
        return self.dict.get(key, default)

    def pop(self):
        """Return (key, value) with the smallest value.

        Raise StopIteration (!!) if empty
        """
        while True:
            try:
                value, key = heapq.heappop(self.heap)
                if value is self.dict[key]:
                    del self.dict[key]
                    return key, value
            except KeyError:
                # deleted from dict = not here
                pass
            except IndexError:
                # nothing more to pop
                raise StopIteration

###
### Result objects
###

class Facade(object):
    """Facade for optput objects

    The main algorithm uses integers (and tiny strings, and sets, dicts,
    tuples you get the picture...).
    The rest of the world uses ORM objects.
    So, all objects that are returned in results have "object ID" attributes
    ending in an underscore (e.g. pokemon_), and this base class adds
    underscore-less properties that get the underlying object.
    """
    @property
    def pokemon(self):
        return self.search.session.query(tables.Pokemon).filter_by(id=self.pokemon_).one()

    @property
    def version_group(self):
        return self.search.get_by_id(tables.VersionGroup, self.version_group_)

    @property
    def versions(self):
        return self.version_group.versions

    @property
    def move(self):
        return self.search.get_by_id(tables.Move, self.move_)

    @property
    def moves(self):
        return self.search.get_list(tables.Move, self.moves_)

    @property
    def move_method(self):
        return self.search.get_by_identifier(tables.PokemonMoveMethod,
                self.move_method_)

    @property
    def evolution_trigger(self):
        return self.search.get_by_identifier(tables.EvolutionTrigger,
                self.evolution_trigger_)

###
### Search space transitions
###

class Action(Facade):
    pass

class StartAction(Action, namedtuple('StartAcion', 'search pokemon_ version_group_')):
    keyword = 'start'

    def __unicode__(self):
        vers = ' or '.join(v.name for v in self.versions)
        return u"Start with {0.pokemon.name} in {1}".format(self, vers)

class LearnAction(Action, namedtuple('LearnAction', 'search move_ move_method_')):
    keyword = 'start'

    def __unicode__(self):
        return u"Learn {0.move.name} by {0.move_method.name}".format(self)

class RelearnAction(Action, namedtuple('RelearnAction', 'search move_')):
    keyword = 'start'

    def __unicode__(self):
        return u"Relearn {0.move.name}".format(self)

class ForgetAction(Action, namedtuple('ForgetAction', 'search move_')):
    keyword = 'forget'

    def __unicode__(self):
        return u"Forget {0.move.name}".format(self)

class TradeAction(Action, namedtuple('TradeAction', 'search version_group_')):
    keyword = 'trade'

    def __unicode__(self):
        vers = ' or '.join(v.name for v in self.versions)
        return u"Trade to {1}".format(self, vers)

class EvolutionAction(Action, namedtuple('EvolutionAction', 'search pokemon_ evolution_trigger_')):
    keyword = 'evolution'

    def __unicode__(self):
        return u"Evolve to {0.pokemon.name} by {0.evolution_trigger.name}".format(self)

class GrowAction(Action, namedtuple('GrowAction', 'search level')):
    keyword = 'grow'

    def __unicode__(self):
        return u"Grow to level {0.level}".format(self)

class SketchAction(Action, namedtuple('SketchAction', 'search move_')):
    keyword = 'grow'

    def __unicode__(self):
        return u"Sketch {0.move.name}".format(self)

class BreedAction(Action, namedtuple('BreedAction', 'search pokemon_ moves_')):
    keyword = 'grow'

    def __unicode__(self):
        mvs = ', '.join(m.name for m in self.moves)
        return u"Breed {0.pokemon.name} with {1}".format(self, mvs)

###
### Search space nodes
###

class InitialNode(Node, namedtuple('InitialNode', 'search')):
    def expand(self):
        search = self.search
        for pokemon, version_groups in search.pokemon_moves.items():
            egg_groups = search.egg_groups[search.evolution_chains[pokemon]]
            if any(search.breeds_required[group] for group in egg_groups) or (
                    search.evolution_chains[pokemon] == search.goal_evolution_chain):
                for version_group in version_groups:
                    action = StartAction(search, pokemon, version_group)
                    node = PokemonNode(
                            search=search,
                            pokemon_=pokemon,
                            level=0,
                            version_group_=version_group,
                            moves_=frozenset(),
                            new_level=True,
                        )
                    yield 0, action, node

class PokemonNode(Node, Facade, namedtuple('PokemonNode',
        'search pokemon_ level version_group_ new_level moves_')):

    def __str__(self):
        return "lv.{level:3}{s} {self.pokemon.identifier:<10.10} in {version_group_:3} with {moves}".format(
                s='*' if self.new_level else ' ',
                moves=','.join(sorted(move.identifier for move in self.moves)) or '---',
                self=self,
                **self._asdict())

    def expand(self):
        search = self.search
        evo_chain = search.evolution_chains[self.pokemon_]
        if not self.moves_:
            # Learn something first
            # (other expand_* may rely on there being a move)
            return self.expand_learn()
        elif self.moves_.difference(self.search.goal_moves):
            # Learned too much!
            # Moves that aren't in the goal set are either Sketch or evolution
            # moves.
            # For the former, use the sketch; for the latter, evolve and
            # forget the move.
            return itertools.chain(
                    self.expand_sketch(),
                    self.expand_forget(),
                    self.expand_evolutions(),
                )
        elif evo_chain != search.goal_evolution_chain:
            if not any(self.moves_ in search.breeds_required[group]
                    for group in search.egg_groups[evo_chain]):
                # It doesn't make sense to train this any more, since there's
                # no way to pass the moves to the goal pokemon.
                return ()
        if len(self.moves_) == 4:
            learns = ()
        else:
            learns = self.expand_learn()
        return itertools.chain(
                learns,
                self.expand_trade(),
                self.expand_grow(),
                self.expand_evolutions(),
                self.expand_breed(),
            )

    def expand_learn(self):
        search = self.search
        moves = search.pokemon_moves[self.pokemon_][self.version_group_]
        for move, methods in moves.items():
            if move in self.moves_:
                continue
            for method, levels_costs in methods.items():
                if method == 'level-up':
                    for level, cost in levels_costs:
                        level_difference = level - self.level
                        if level_difference > 0 or (
                                level_difference == 0 and self.new_level):
                            cost += level - self.level * search.costs['per-level']
                            yield self._learn(move, method, cost,
                                level=level, new_level=True)
                        else:
                            yield self._learn(move, 'relearn',
                                search.costs['relearn'],
                                action=RelearnAction(self.search, move),
                                new_level=False)
                elif method in 'machine tutor'.split():
                    for level, cost in levels_costs:
                        yield self._learn(move, method, cost, new_level=False)
                elif method == 'egg':
                    # ignored here
                    pass
                elif method == 'light-ball-egg':
                    if self.level == 0 and self.new_level:
                        for level, cost in levels_costs:
                            yield self._learn(move, method, cost)
                elif method == 'stadium-surfing-pikachu':
                    for level, cost in levels_costs:
                        yield self._learn(move, method, cost, new_level=False)
                elif method == 'form-change':
                    # XXX: Form changes
                    pass
                else:
                    raise ValueError('Unknown move method %s' % method)

    def _learn(self, move, method, cost, action=None, **kwargs):
        kwargs['moves_'] = self.moves_.union([move])
        if action is None:
            action = LearnAction(self.search, move, method)
        return cost, action, self._replace(
                **kwargs)

    def expand_forget(self):
        cost = self.search.costs['forget']
        for move in self.moves_.difference(self.search.goal_moves):
            yield cost, ForgetAction(self.search, move), self._replace(
                    moves_=self.moves_.difference([move]), new_level=False)

    def expand_trade(self):
        search = self.search
        target_vgs = set(search.pokemon_moves[self.pokemon_])
        target_vgs.add(search.goal_version_group)
        target_vgs.discard(self.version_group_)
        max_generation = max(search.move_generations[m] for m in self.moves_)
        for version_group in target_vgs:
            cost = search.trade_cost(self.version_group_, version_group,
                    max_generation)
            if cost is not None:
                yield cost, TradeAction(search, version_group), self._replace(
                        version_group_=version_group, new_level=False)

    def expand_grow(self):
        search = self.search
        if (self.pokemon_ == search.goal_pokemon and
                self.version_group_ == search.goal_version_group and
                self.moves_ == search.goal_moves and
                self.level <= search.goal_level):
            kwargs = self._asdict()
            kwargs['level'] = search.goal_level
            kwargs['new_level'] = True
            yield 0, GrowAction(search, search.goal_level), GoalNode(**kwargs)

    def expand_evolutions(self):
        search = self.search
        for trigger, move, level, child in search.evolutions[self.pokemon_]:
            kwargs = dict(pokemon_=child)
            cost = search.costs['evolution']
            if move and move not in self.moves_:
                continue
            if level:
                if level > self.level:
                    kwargs['level'] = level
                    kwargs['new_level'] = True
                elif level == self.level and self.new_level:
                    pass
                else:
                    cost += search.costs['evolution-delayed']
            if trigger in 'level-up use-item'.split():
                pass
            elif trigger == 'trade':
                kwargs['new_level'] = False
            elif trigger == 'shed':
                # XXX: Shedinja!!
                pass
            else:
                raise ValueError('Unknown evolution trigger %s' % trigger)
            yield cost, EvolutionAction(search, child, trigger), self._replace(
                    **kwargs)

    def expand_breed(self):
        search = self.search
        if self.pokemon_ in search.unbreedable:
            return
        evo_chain = search.evolution_chains[self.pokemon_]
        egg_groups = search.egg_groups[evo_chain]
        breeds_required = search.breeds_required
        moves = self.moves_
        cost = search.costs['breed']
        cost += search.costs['egg'] * len(moves)
        cost += search.costs['breed-penalty'] * len(search.egg_moves - moves)
        gender_rate = search.gender_rates[evo_chain]
        goal_family = search.goal_evolution_chain
        goal_groups = search.egg_groups[goal_family]
        goal_compatible = set(goal_groups).intersection(egg_groups)
        if 0 < gender_rate:
            # Only pokemon that have males can pas down moves to other species
            # (and the other species must have females: checked in BreedNode)
            for group in egg_groups:
                if moves in breeds_required[group]:
                    yield cost, None, BreedNode(search=self.search, dummy='b',
                            group_=group, version_group_=self.version_group_,
                            moves_=self.moves_)
            # Since the target family is not included in our breed graph, we
            # breed with it explicitly. But again, there must be a female to
            # breed with.
            if goal_compatible and search.gender_rates[
                        search.goal_evolution_chain] < 8:
                yield cost, None, GoalBreedNode(search=self.search, dummy='g',
                        version_group_=self.version_group_, moves_=self.moves_)
        elif evo_chain == search.goal_evolution_chain:
            # Single-gender & genderless pokemon can pass on moves via
            # breeding with Ditto, to produce the same species again. Obviously
            # this is only useful when breeding the goal species.
            yield cost, None, GoalBreedNode(search=self.search, dummy='g',
                    version_group_=self.version_group_, moves_=self.moves_)

    def expand_sketch(self):
        moves = self.moves_
        sketch = self.search.sketch
        if sketch in moves:
            for sketched in sorted(self.search.goal_moves):
                if sketched in self.search.unsketchable:
                    continue
                if sketched not in moves:
                    moves = set(moves)
                    moves.remove(sketch)
                    moves.add(sketched)
                    action = SketchAction(self.search, sketched)
                    cost = self.search.costs['sketch']
                    yield cost, action, self._replace(
                            new_level=False, moves_=frozenset(moves))
                    return

    def estimate(self, g):
        # Given good estimates, A* finds solutions much faster.
        # However, here it seems we either have easy movesets, which
        # get found pretty easily by themselves, or hard ones, where
        # heuristics don't help too much, or impossible ones where they
        # don't matter at all.
        # So, keep the computations here to a minimum.
        search = self.search
        trade_cost = search.trade_cost(self.version_group_,
                search.goal_version_group)
        if trade_cost is None:
            trade_cost = search.costs['trade'] * 2
        return trade_cost

class BaseBreedNode(Node):
    """Breed node
    This serves to prevent duplicate breeds, by storing only the needed info
    in the namedtuple.
    Also, the base breed cost was already paid, so the breeding tends to happen
    later in the algorithm.
    """
    def expand(self):
        search = self.search
        vg = self.version_group_
        gen = search.generation_id_by_version_group[vg]
        hatch_level = 5 if (gen < 4) else 1
        for baby in self.babies():
            bred_moves = self.moves_
            moves = search.pokemon_moves[baby][vg]
            if not bred_moves.issubset(moves):
                continue
            if len(bred_moves) < 4:
                for move, methods in moves.items():
                    if 'light-ball-egg' in methods:
                        bred_moves = bred_moves.union([move])
            cost = search.costs['per-hatch-counter'] * search.hatch_counters[baby]
            yield 0, BreedAction(self.search, baby, bred_moves), PokemonNode(
                    search=self.search, pokemon_=baby, level=hatch_level,
                    version_group_=vg, moves_=bred_moves, new_level=True)

    @property
    def pokemon(self):
        return None

    def estimate(self, g):
        return 0

class BreedNode(BaseBreedNode, namedtuple('BreedNode',
        'search dummy group_ version_group_ moves_')):
    def babies(self):
        search = self.search
        for baby in search.babies[self.group_]:
            baby_chain = search.evolution_chains[baby]
            if self.moves_.issubset(search.movepools[baby_chain]) and (
                    search.gender_rates[baby_chain] > 0):
                yield baby

class GoalBreedNode(BaseBreedNode, namedtuple('GoalBreedNode',
        'search dummy version_group_ moves_')):
    def babies(self):
        search = self.search
        goal_family = search.goal_evolution_chain
        group = search.egg_groups[goal_family][0]
        for baby in search.pokemon_by_evolution_chain[goal_family]:
            if baby in search.babies[group]:
                yield baby

class GoalNode(PokemonNode):
    def expand(self):
        return ()

    def is_goal(self, g):
        return True
###
### CLI interface
###

def print_result(result, moves=()):
    template = u"{cost:4} {est:4} {action:45.45}{long:1} {pokemon:10}{level:>3}{nl:1}{versions:2} {moves}"
    print template.format(cost='Cost', est='Est.', action='Action', pokemon='Pokemon',
            long='', level='Lv.', nl='V', versions='er',
            moves=''.join(m.name[0].lower() for m in moves))
    for cost, action, node in reversed(list(result)):
        if action:
            print template.format(
                cost=cost,
                action=action,
                long='>' if (len(unicode(action)) > 45) else '',
                est=node.estimate(None),
                pokemon=node.pokemon.name,
                nl='.' if node.new_level else ' ',
                level=node.level,
                versions=''.join(v.name[0] for v in node.versions),
                moves=''.join('.' if m in node.moves else ' ' for m in moves) +
                    ''.join(m.name[0].lower() for m in node.moves if m not in moves),
            )

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

    session = connect(engine_args={'echo': args.debug > 2})

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
                return False
        return result

    pokemon = _get_list(tables.Pokemon, [args.pokemon], 'Pokemon')[0]
    moves = _get_list(tables.Move, args.move, 'Move')
    version = _get_list(tables.Version, [args.version], 'Version')[0]
    excl_versions = _get_list(tables.Version, args.exclude_version, 'Version')
    excl_pokemon = _get_list(tables.Pokemon, args.exclude_pokemon, 'Pokemon')

    if args.debug:
        print 'Starting search'

    no_results = True
    try:
        search = MovesetSearch(session, pokemon, version, moves, args.level,
            exclude_versions=excl_versions, exclude_pokemon=excl_pokemon,
            debug_level=args.debug)
    except IllegalMoveCombination, e:
        print 'Error:', e
    else:
        if args.debug:
            print 'Setup done'

        for result in search:
            if args.debug and search.output_objects:
                print '**warning: search looked up output objects**'
            no_results = False
            print '-' * 79
            print_result(result, moves=moves)
            # XXX: Support more than one result
            break

        if args.debug:
            print
            print 'Done'

    return (not no_results)

if __name__ == '__main__':
    sys.exit(not main(sys.argv[1:]))
