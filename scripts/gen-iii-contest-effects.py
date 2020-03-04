#!/usr/bin/env python3
"""
This is an unmaintained one-shot script, only included in the repo for
reference.
"""

import struct

def main():
    NUM_MOVES = 354
    with open("pokeruby.gba", 'rb') as f:
        f.seek(0x3cf594 )
        data = f.read(8 * (NUM_MOVES + 1))


    effects = []
    combo_id_map = {} # combo_id => move_id
    combo_pairs = [] # [(combo starter, move id)]

    with open("update_contest_effect_ids.sql", "w") as f:
        for i in range(NUM_MOVES+1):
            effect, type, combo_id, *combo_prev = struct.unpack("<BBBBBBBx", data[i*8:(i+1)*8])
            print(i, idmap[effect], type, combo_id, combo_prev)
            if i:
                print("UPDATE moves SET contest_effect_id = %d, contest_type_id = %d WHERE id = %d;" % (idmap[effect], type+1, i), file=f)
            effects.append(effect)
            if combo_id:
                combo_id_map.setdefault(combo_id, []).append(i)
            for c in combo_prev:
                combo_pairs.append((c, i))

    move_pairs = []
    for combo_id, second_move_id in combo_pairs:
        for id1 in combo_id_map.get(combo_id, ()):
            move_pairs.append((id1, second_move_id))
    move_pairs.sort()
    with open("contest_combos.csv", "w") as f:
        print("first_move_id,second_move_id", file=f)
        for first, second in move_pairs:
            print(first, second, sep=",", file=f)


    num_effects = max(effects)+1
    with open("pokeruby.gba", 'rb') as f:
        f.seek(0x3d00ac)
        data = f.read(4 * num_effects)

    with open("contest_effects.csv", "w") as f:
        print("id,effect_type,appeal,jam", file=f)
        for i in range(num_effects):
            if i not in effects:
                continue
            effectType, appeal, jam = struct.unpack("<BBBx", data[i*4:(i+1)*4])
            #print(idmap[i],effectType, appeal//10, jam//10, sep=",")
            print(idmap[i], appeal//10, jam//10, sep=",", file=f)

idmap = {
    0: 1, # CONTEST_EFFECT_HIGHLY_APPEALING
    1: 3, # CONTEST_EFFECT_USER_MORE_EASILY_STARTLED
    2: 7, # CONTEST_EFFECT_GREAT_APPEAL_BUT_NO_MORE_MOVES
    3: 17, # CONTEST_EFFECT_REPETITION_NOT_BORING
    4: 16, # CONTEST_EFFECT_AVOID_STARTLE_ONCE
    5: 15, # CONTEST_EFFECT_AVOID_STARTLE
    #6: # CONTEST_EFFECT_AVOID_STARTLE_SLIGHTLY
    #7: # CONTEST_EFFECT_USER_LESS_EASILY_STARTLED
    #8: # CONTEST_EFFECT_STARTLE_FRONT_MON
    #9: # CONTEST_EFFECT_SLIGHTLY_STARTLE_PREV_MONS
    10: 9, # CONTEST_EFFECT_STARTLE_PREV_MON
    11: 8, # CONTEST_EFFECT_STARTLE_PREV_MONS
    12: 4, # CONTEST_EFFECT_BADLY_STARTLE_FRONT_MON
    13: 5, # CONTEST_EFFECT_BADLY_STARTLE_PREV_MONS
    #14: # CONTEST_EFFECT_STARTLE_PREV_MON_2
    #15: # CONTEST_EFFECT_STARTLE_PREV_MONS_2
    16: 22, # CONTEST_EFFECT_SHIFT_JUDGE_ATTENTION
    17: 10, # CONTEST_EFFECT_STARTLE_MON_WITH_JUDGES_ATTENTION
    18: 6, # CONTEST_EFFECT_JAMS_OTHERS_BUT_MISS_ONE_TURN
    19: 23, # CONTEST_EFFECT_STARTLE_MONS_SAME_TYPE_APPEAL
    #20: 0, # CONTEST_EFFECT_STARTLE_MONS_COOL_APPEAL
    #21: 0, # CONTEST_EFFECT_STARTLE_MONS_BEAUTY_APPEAL
    #22: 0, # CONTEST_EFFECT_STARTLE_MONS_CUTE_APPEAL
    #23: 0, # CONTEST_EFFECT_STARTLE_MONS_SMART_APPEAL
    #24: 0, # CONTEST_EFFECT_STARTLE_MONS_TOUGH_APPEAL
    #25: # CONTEST_EFFECT_MAKE_FOLLOWING_MON_NERVOUS
    26: 18, # CONTEST_EFFECT_MAKE_FOLLOWING_MONS_NERVOUS
    27: 33, # CONTEST_EFFECT_WORSEN_CONDITION_OF_PREV_MONS
    #28: # CONTEST_EFFECT_BADLY_STARTLES_MONS_IN_GOOD_CONDITION
    29: 27, # CONTEST_EFFECT_BETTER_IF_FIRST
    30: 28, # CONTEST_EFFECT_BETTER_IF_LAST
    31: 20, # CONTEST_EFFECT_APPEAL_AS_GOOD_AS_PREV_ONES
    32: 19, # CONTEST_EFFECT_APPEAL_AS_GOOD_AS_PREV_ONE
    33: 26, # CONTEST_EFFECT_BETTER_WHEN_LATER
    34: 25, # CONTEST_EFFECT_QUALITY_DEPENDS_ON_TIMING
    35: 12,  # CONTEST_EFFECT_BETTER_IF_SAME_TYPE
    #36: # CONTEST_EFFECT_BETTER_IF_DIFF_TYPE
    37: 2, # CONTEST_EFFECT_AFFECTED_BY_PREV_APPEAL
    38: 32, # CONTEST_EFFECT_IMPROVE_CONDITION_PREVENT_NERVOUSNESS
    39: 29, # CONTEST_EFFECT_BETTER_WITH_GOOD_CONDITION
    40: 30, # CONTEST_EFFECT_NEXT_APPEAL_EARLIER
    41: 31, # CONTEST_EFFECT_NEXT_APPEAL_LATER
    #42: # CONTEST_EFFECT_MAKE_SCRAMBLING_TURN_ORDER_EASIER
    43: 21, # CONTEST_EFFECT_SCRAMBLE_NEXT_TURN_ORDER
    44: 13, # CONTEST_EFFECT_EXCITE_AUDIENCE_IN_ANY_CONTEST
    45: 14, # CONTEST_EFFECT_BADLY_STARTLE_MONS_WITH_GOOD_APPEALS
    46: 11, # CONTEST_EFFECT_BETTER_WHEN_AUDIENCE_EXCITED
    47: 24, # CONTEST_EFFECT_DONT_EXCITE_AUDIENCE
}

from collections import Counter
c = Counter(idmap.values())
print([v for v in c if c[v] > 1])
assert len(idmap) == len(set(idmap.values()))

main()
