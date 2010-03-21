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


def calculated_stat(base_stat, level, iv, effort):
    """Returns the calculated stat -- i.e. the value actually shown in the game
    on a Pokémon's status tab.
    """

    # Remember: this is from C; use floor division!
    return (base_stat * 2 + iv + effort // 4) * level // 100 + 5

def calculated_hp(base_hp, level, iv, effort):
    """Similar to `calculated_stat`, except with a slightly different formula
    used specifically for HP.
    """

    # Shedinja's base stat of 1 is special; its HP is always 1
    if base_hp == 1:
        return 1

    return (base_hp * 2 + iv + effort // 4) * level // 100 + 10 + level

def earned_exp(base_exp, level):
    """Returns the amount of EXP earned when defeating a Pokémon at the given
    level.
    """

    return base_exp * level // 7

def capture_chance(current_hp, max_hp, capture_rate,
                   ball_bonus=1, status_bonus=1, heavy_modifier=0):
    """Calculates the chance that a Pokémon will be caught.

    Returns five values: the chance of a capture, then the chance of the ball
    shaking three, two, one, or zero times.  Each of these is a float such that
    0.0 <= n <= 1.0.  Feel free to ignore all but the first.
    """

    if heavy_modifier:
        # Only used by Heavy Ball.  Changes the target's capture rate outright
        capture_rate += heavy_modifier
        if capture_rate <= 1:
            capture_rate = 1

    # This should really be integer math, right?  But the formula uses FOURTH
    # ROOTS in a moment, so it can't possibly be.  It probably doesn't matter
    # either way, so whatever; use regular ol' division.  ball_bonus and
    # status_bonus can be 1.5, anyway.
    base_chance = ((3 * max_hp - 2 * current_hp) * capture_rate * ball_bonus) \
                / (3 * max_hp) \
                * status_bonus

    shake_index = (base_chance / 255) ** 0.25 * (2**16 - 1)

    # Iff base_chance < 255, then shake_index < 65535.
    # The game now picks four random uwords.  However many of them are <=
    # shake_index is the number of times the ball will shake.  If all four are
    # <= shake_index, the Pokémon is caught.

    # The RNG tends to work with integers, so integer math likely kicks in now.
    shake_index = int(shake_index)

    # If shake_index >= 65535, all four randoms must be <= it, and the Pokémon
    # will be caught.  Skip hard math
    if shake_index >= 65535:
        return (1.0, 0.0, 0.0, 0.0, 0.0)

    # This brings up an interesting invariant: sum(return_value) == 1.0.
    # Something is guaranteed to happen.

    # Alrighty.  Here's some probability.
    # The chance that a single random number will be <= shake_index is:
    p = (shake_index + 1) / 65536
    # Now, the chance that two random numbers will be <= shake_index is p**2.
    # And the chance that neither will be is (1 - p)**2.
    # With me so far?
    # The chance that one will be and one will NOT be is p * (1 - p) * 2.
    # The 2 is because they can go in any order: the first could be less, or
    # the second could be less.  That 2 is actually nCr(2, 1); the number of
    # ways of picking one item in any order from a group of two.
    # Try it yourself add up those three values and you'll get 1.

    # Right.  Hopefully, the following now makes sense.
    # There are five cases: four randoms are <= shake_index (which means
    # capture), or three are, etc.
    return [
        p**i * (1 - p)**(4 - i) * nCr(4, i)
        for i in reversed(range(5))
    ]
