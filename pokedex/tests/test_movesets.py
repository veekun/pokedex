
import pytest
from pokedex.tests import single_params

import sys

from pokedex.db import connect
from pokedex.util.movesets import main

result_map = {'OK': True, 'NO': False}
session = connect()

argstrings = u"""
NO muk
NO beedrill rage pursuit agility endeavor toxic
NO ditto psystrike aeroblast mist-ball judgment
OK metapod tackle harden
OK lugia aeroblast punishment dive snore
OK yanmega bug-bite bug-buzz tackle whirlwind
OK yanmega whirlwind
OK crobat brave-bird quick-attack gust zen-headbutt
OK bagon defense-curl fire-fang hydro-pump shadow-claw
OK volcarona endure toxic fly fire-blast
OK hippopotas curse revenge sleep-talk swallow
OK hippopotas curse revenge sleep-talk snore
OK smeargle bug-bite bug-buzz splash fire-blast
NO smeargle bug-bite chatter splash fire-blast
NO azurill muddy-water iron-tail scald mimic
OK salamence dragon-dance dragon-claw fire-blast earthquake -v platinum
OK crawdaunt brick-break rock-slide facade toxic -v platinum
NO cleffa tickle wish amnesia splash
OK tyrogue pursuit
NO happiny softboiled
NO mamoswine bite body-slam curse double-edge
OK shedinja swords-dance
NO shedinja swords-dance screech
OK shedinja baton-pass grudge
OK shedinja screech double-team fury-cutter x-scissor
OK raichu volt-tackle
OK raichu surf -v gold
OK pikachu volt-tackle thunderbolt bide
OK gyarados flail thrash iron-head outrage
OK drifblim memento gust thunderbolt pain-split
OK crobat nasty-plot brave-bird
NO crobat nasty-plot hypnosis
OK garchomp double-edge thrash outrage
OK nidoking counter disable amnesia head-smash
OK aggron stomp smellingsalt screech fire-punch
OK tyranitar dragon-dance outrage thunder-wave surf
NO butterfree morning-sun harden
OK pikachu reversal bide nasty-plot discharge
NO pikachu surf charge
NO blissey wish counter
NO clefairy copycat dynamicpunch
OK rotom overheat
OK rotom blizzard
NO rotom overheat blizzard
OK deoxys superpower amnesia  spikes taunt
OK deoxys counter extremespeed spikes pursuit
OK pikachu reversal bide nasty-plot discharge
NO pikachu surf charge
OK pikachu volt-tackle encore headbutt grass-knot
#OK suicune extremespeed dig icy-wind bite
""".strip().splitlines()

@single_params(*argstrings)
def test_moveset(argstring):
    if argstring[0] == '#':
        xfail = True
        argstring = argstring[1:]
    else:
        xfail = False
    args = argstring.strip().split() + ['-q']
    try:
        assert bool(main(args[1:], session=session)) == result_map[args[0]]
    except AssertionError:
        if xfail:
            pytest.xfail()
        raise

if __name__ == '__main__':
    # XXX: Is there a profiler for py.test?
    # Just use cProfile for now.
    filename = 'movesets.profile'
    print 'Profiling the moveset checker'
    import cProfile
    ok_fail = [0, 0]
    def run_case(argv):
        print argv, '...',
        sys.stdout.flush()
        try:
            test_moveset(argv)
            ok_fail[0] += 1
            print 'ok'
        except (AssertionError, pytest.xfail.Exception):
            ok_fail[1] += 1
            print 'FAIL'
    cProfile.runctx("[(run_case(argv.strip())) for argv in argstrings]",
            globals(), locals(), filename=filename)
    if ok_fail[1]:
        print '*** FAILED ***'
        print "{0} tests: {1[0]} OK, {1[1]} failed".format(sum(ok_fail), ok_fail)
    else:
        print "{0} tests: OK".format(sum(ok_fail), ok_fail)
    print 'Profile stats saved to', filename
