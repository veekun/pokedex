
from pokedex.util.movesets import main

result_map = {'OK': True, 'NO': False}

def test_cases():
    for argstring in u"""
            NO muk
            NO beedrill rage pursuit agility endeavor toxic
            NO ditto psystrike aeroblast mist-ball judgment
            OK lugia aeroblast punishment dive snore
            OK yanmega bug-bite bug-buzz tackle whirlwind
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
            NO mamoswine bite body-slam curse double-edge
            OK raichu volt-tackle
            OK raichu surf -v gold
            OK pikachu volt-tackle thunderbolt bide
            OK gyarados flail thrash iron-head outrage
            OK drifblim memento gust thunderbolt pain-split
            OK crobat nasty-plot brave-bird
            OK crobat brave-bird hypnosis
            NO crobat nasty-plot hypnosis
            OK garchomp double-edge thrash outrage
            OK nidoking counter disable amnesia head-smash
            OK aggron stomp smellingsalt screech fire-punch
            NO aggron endeavor body-slam
            OK tyranitar dragon-dance outrage thunder-wave surf
            NO butterfree morning-sun harden
            OK pikachu reversal bide nasty-plot discharge
            NO pikachu surf charge
            NO blissey wish counter
            NO clefairy copycat dynamicpunch
            """.strip().splitlines():
        def run_test(argstring):
            args = argstring.split()
            assert main(args[1:]) == result_map[args[0]]
        run_test.description = 'Moveset checker test: ' + argstring.strip()
        yield run_test, argstring
