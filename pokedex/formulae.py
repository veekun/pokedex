# encoding: utf8
"""Faithful translations of calculations the games make."""

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
