# encoding: utf8
"""Faithful translations of calculations the games make."""
from __future__ import division

from itertools import izip

def nCr(n, r):
    """n-choose-r.

    Thanks for the "compact" solution go to:
    http://stackoverflow.com/questions/2096573/counting-combinations-and-permutations-efficiently
    """

    return reduce(
        lambda x, y: x * y[0] / y[1],
        izip(xrange(n - r + 1, n + 1),
             xrange(1, r + 1)),
        1)


def calculated_stat(base_stat, level, iv, effort, nature=None):
    """Returns the calculated stat -- i.e. the value actually shown in the game
    on a Pokémon's status tab.
    """

    # Remember: this is from C; use floor division!
    stat = (base_stat * 2 + iv + effort // 4) * level // 100 + 5

    if nature:
        stat = int(stat * nature)

    return stat

def calculated_hp(base_stat, level, iv, effort, nature=None):
    """Similar to `calculated_stat`, except with a slightly different formula
    used specifically for HP.
    """

    # Shedinja's base stat of 1 is special; its HP is always 1
    if base_stat == 1:
        return 1

    return (base_stat * 2 + iv + effort // 4) * level // 100 + 10 + level

def earned_exp(base_exp, level):
    """Returns the amount of EXP earned when defeating a Pokémon at the given
    level.
    """

    return base_exp * level // 7

def capture_chance(percent_hp, capture_rate,
                   ball_bonus=10, status_bonus=1,
                   capture_bonus=10, capture_modifier=0):
    """Calculates the chance that a Pokémon will be caught, given its capture
    rate and the percentage of HP it has remaining.

    Bonuses are such that 10 means "unchanged".

    Returns five values: the chance of a capture, then the chance of the ball
    shaking three, two, one, or zero times.  Each of these is a float such that
    0.0 <= n <= 1.0.  Feel free to ignore all but the first.
    """

    # HG/SS Pokéballs modify capture rate rather than the ball bonus
    capture_rate = capture_rate * capture_bonus // 10 + capture_modifier
    if capture_rate < 1:
        capture_rate = 1
    elif capture_rate > 255:
        capture_rate = 255

    # A slight math note:
    # The actual formula uses (3 * max_hp - 2 * curr_hp) / (3 * max_hp)
    # This uses (1 - 2/3 * curr_hp/max_hp)
    # Integer division is taken into account by flooring immediately
    # afterwards, so there should be no appreciable rounding error.
    base_chance = int(
        capture_rate * ball_bonus // 10 * (1 - 2/3 * percent_hp)
    )
    base_chance = base_chance * status_bonus // 10

    # Shake index involves integer sqrt.  Lovely.
    isqrt = lambda x: int(x ** 0.5)
    if not base_chance:
        # This is very silly.  Due to what must be an oversight, it's possible
        # for the above formula to end with a zero chance to catch, which is
        # then thrown blindly into the below denominator.  Luckily, the games'
        # division function is a no-op with a denominator of zero..  which
        # means a base_chance of 0 is effectively a base chance of 1.
        base_chance = 1
    shake_index = 1048560 // isqrt(isqrt(16711680 // base_chance))

    # Iff base_chance < 255, then shake_index < 65535.
    # The Pokémon now has four chances to escape.  The game starts picking
    # random uint16s.  If such a random number is < shake_index, the Pokémon
    # stays in the ball, and it wobbles.  If the number is >= shake_index, the
    # ball breaks open then and there, and the capture fails.
    # If all four are < shake_index, the Pokémon is caught.

    # If shake_index >= 65535, all four randoms must be < it, and the Pokémon
    # will be caught.  Skip hard math
    if shake_index >= 65535:
        return (1.0, 0.0, 0.0, 0.0, 0.0)

    # This brings up an interesting invariant: sum(return_value) == 1.0.
    # Something is guaranteed to happen.

    # Alrighty.  Here's some probability.
    # The chance that a single random uint16 will be < shake_index, thus
    # keeping the Pokémon in the ball, is:
    p = shake_index / 65536

    # Now, the chance for n wobbles is the chance that the Pokémon will stay in
    # the ball for (n-1) attempts, then break out on the nth.
    # The chance of capture is just the chance that the Pokémon stays in the
    # ball for all four tries.

    # There are five cases: captured, wobbled three times, etc.
    return [
        p**4,  # capture
        p**3 * (1 - p),
        p**2 * (1 - p),
        p**1 * (1 - p),
               (1 - p),
    ]
