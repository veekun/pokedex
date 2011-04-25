"""A pure-Python implementation of the A* search algorithm
"""

import heapq

class Node(object):
    """Node for the A* search algorithm.

    To get started, implement the `expand` method and call `search`.

    N.B. Node object must be hashable.
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

### The main algorithm

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


### Example/test


def test_example_knights():
    """Test/example: the "knights" problem

    Definition and another solution may be found at: 
    http://brandon.sternefamily.net/posts/2005/02/a-star-algorithm-in-python/
    """
    # Legal moves
    moves = { 1: [4, 7],
              2: [8, 10],
              3: [9],
              4: [1, 6, 10],
              5: [7],
              6: [4],
              7: [1, 5],
              8: [2, 9],
              9: [8, 3],
              10: [2, 4] }

    class Positions(dict, Node):
        """Node class representing positions as a dictionary.

        Keys are unique piece names, values are (color, position) where color
        is True for white, False for black.
        """
        def expand(self):
            for piece, (color, position) in self.items():
                for new_position in moves[position]:
                    if new_position not in (p for c, p in self.values()):
                        new_node = Positions(self)
                        new_node.update({piece: (color, new_position)})
                        yield 1, None, new_node

        def estimate(self, goal):
            # Number of misplaced figures
            misplaced = 0
            for piece, (color, position) in self.items():
                if (color, position) not in goal.values():
                    misplaced += 1
            return misplaced

        def is_goal(self, goal):
            return self.estimate(goal) == 0

        def __hash__(self):
            return hash(tuple(sorted(self.items())))

    initial = Positions({
            'White 1': (True, 1),
            'white 2': (True, 6),
            'Black 1': (False, 5),
            'black 2': (False, 7),
        })

    # Goal: colors should be switched
    goal = Positions((piece, (not color, position))
            for piece, (color, position) in initial.items())

    def print_board(positions, linebreak='\n', extra=''):
        board = dict((position, piece)
                for piece, (color, position) in positions.items())
        for i in range(1, 11):
            # line breaks
            if i in (2, 6, 9):
                print linebreak,
            print board.get(i, '_')[0],
        print extra

    def notify(cost, state, b, c):
        print 'Looking at state with cost %s:' % cost,
        print_board(state, '|', '(%s; %s; %s)' % (state.estimate(goal), b, c))

    solution_path = list(initial.search(goal, notify=notify))

    print 'Step', 0
    print_board(initial)
    for i, (cost, transition, positions) in enumerate(reversed(solution_path)):
        print 'Step', i + 1
        print_board(positions)

    # Check solution is correct
    cost, transition, positions = solution_path[0]
    assert set(positions.values()) == set(goal.values())
    assert cost == 40
