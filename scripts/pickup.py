#!/usr/bin/env python2

from random import randint
from collections import namedtuple

import pokedex.db
import pokedex.db.tables as t

Pickup = namedtuple('Pickup', 'version_group rates common_items rare_items')

# The item lists below are taken directly from the games, and differ from
# the popularly reported values, e.g., on Serebii and Bulbapedia, in the
# following ways:
#
#   - Hyper Potion at level 1-10, 1%, instead of various other items
#   - There are no Lucky Eggs. Anywhere. Ever.

# These rates have been verified in SoulSilver
rates = [30, 10, 10, 10, 10, 10, 10, 5, 3]

# The following function is a sketch how the pickup items are chosen, taken
# from SoulSilver (U). For full details set a breakpoint at 0x02244106.
#
# Note that the 1% items are backwards:
#   n=98 gives index 1, and n=99 gives index 0
def get_reward(pickup, level, n=None):
    if n is None:
        n = randint(0, 99)
    level = (level - 1) // 10
    assert 0 <= level < 10
    threshold = 0
    for index, rate in enumerate(pickup.rates):
        threshold += rate
        if n < threshold:
            return pickup.common_items[level + index]
    else:
        assert 98 <= n <= 99
        index = 99 - n
        assert 0 <= index <= 1
        return pickup.rare_items[level + index]

# Emerald (U)
# The rewards lists are located at 0x31c440 in the ROM.
# The second immediately follows the first, at 0x31C464. 
# 0x0031C440: 0D000E00 16000300 56005500 4B001700     ........V.U.K...
# 0x0031C450: 02001500 44004000 18003F00 13001900     ....D.@...?.....
# 0x0031C460: 45002500 15006E00 BB001300 2200B400     E.%...n....."...
# 0x0031C470: 4C012400 2101C800 3A011E28 323C4650     L.$.!...:..(2<FP
em = Pickup('emerald', rates,
    [0x0D, 0x0E, 0x16, 0x03, 0x56, 0x55, 0x4B, 0x17, 0x02,
     0x15, 0x44, 0x40, 0x18, 0x3F, 0x13, 0x19, 0x45, 0x25],
    [0x15, 0x6E, 0xBB, 0x13, 0x22, 0xB4, 0x14C, 0x24, 0x121, 0xC8, 0x13A],
)

# Diamond (U)
# The common rewards list is found at 0x1ddb64 in the ROM
# 0x001DDB60: 9301A100 11001200 1A000300 4F004E00     ............O.N.
# 0x001DDB70: 1B001900 02001C00 32006C00 6B006D00     ........2.l.k.m.
# 0x001DDB80: 17001D00 33002900 1B000080 1B000080     ....3.).........
# The rare rewards list is found at 0x1dda88 in the ROM
# 0x001DDA80: 0C641550 2A284014 19005C00 DD001700     .d.P*(@...\.....
# 0x001DDA90: 2600D600 73012800 4801EA00 61010000     &...s.(.H...a...
dp = Pickup('diamond-pearl', rates,
    [0x11, 0x12, 0x1A, 0x03, 0x4F, 0x4E, 0x1B, 0x19, 0x02,
     0x1C, 0x32, 0x6C, 0x6B, 0x6D, 0x17, 0x1D, 0x33, 0x29],
    [0x19, 0x5C, 0xDD, 0x17, 0x26, 0xD6, 0x173, 0x28, 0x148, 0xEA, 0x161],
)
pl = dp._replace(version_group='platinum')

# SoulSilver (U)
# The rewards lists are found in overlay 12. All overlays are compressed.
# After decompression, the common rewards can be found at 0x34B44.
# 0x00034B40: 2C012D01 11001200 1A000300 4F004E00     ,.-.........O.N.
# 0x00034B50: 1B001900 02001C00 32005000 51005D00     ........2.P.Q.].
# 0x00034B60: 17001D00 33002900 80000000 00000000     ....3.).........
# And the rare rewards can be found at 0x34A4C.
# 0x00034A40: 01C80596 0C641550 2A284014 19005C00     .....d.P*(@...\.
# 0x00034A50: DD001700 26001601 7F012800 9D01EA00     ....&.....(.....
# 0x00034A60: 61010000 08000000 01000000 02000000     a...............
# These lists can also be found in the RAM during battle, at 0x0226c404 and 0x226c30c.
hg = Pickup('heartgold-soulsilver', rates,
    [0x11, 0x12, 0x1A, 0x03, 0x4F, 0x4E, 0x1B, 0x19, 0x02,
     0x1C, 0x32, 0x50, 0x51, 0x5D, 0x17, 0x1D, 0x33, 0x29],
    [0x19, 0x5C, 0xDD, 0x17, 0x26, 0x116, 0x17F, 0x28, 0x19D, 0xEA, 0x161],
)

# White (J)
# Found in overlay 0x5C. As in SoulSilver, it must be decompressed.
# The common rewards are found at 0x7CE, with the rare rewards immediately
# preceding them at 0x7B8.
# 0x000007B0: 14191E23 282D3200 19005C00 DD001700     ...#(-2...\.....
# 0x000007C0: 26001601 19022800 1902EA00 19021100     &.....(.........
# 0x000007D0: 12001A00 03004F00 4E001B00 19000200     ......O.N.......
# 0x000007E0: 1C003200 50005100 5D001700 1D003300     ..2.P.Q.].....3.
# 0x000007F0: 29000000 61941B02 D5941B02 A9941B02     )...a...........
#
# Note that the rates have changed slightly: the 5/3 slots are now 4/4 slots.
bw = Pickup('black-white', [30, 10, 10, 10, 10, 10, 10, 4, 4],
    [0x11, 0x12, 0x1A, 0x03, 0x4F, 0x4E, 0x1B, 0x19, 0x02,
     0x1C, 0x32, 0x50, 0x51, 0x5D, 0x17, 0x1D, 0x33, 0x29],
    [0x19, 0x5C, 0xDD, 0x17, 0x26, 0x116, 0x219, 0x28, 0x219, 0xEA, 0x219],
)

# Black 2 (J)
# Found in overlay 0xA6. Must be decompressed.
# Common rewards at 0x7FA. Rare rewards immediately prior, at 0x7E4.
# Same items as B/W 1.
# 0x000007E0: 282D3200 19005C00 DD001700 26001601     (-2...\.....&...
# 0x000007F0: 19022800 1902EA00 19021100 12001A00     ..(.............
# 0x00000800: 03004F00 4E001B00 19000200 1C003200     ..O.N.........2.
# 0x00000810: 50005100 5D001700 1D003300 29000000     P.Q.].....3.)...
# 0x00000820: 61C81902 D5C81902 A9C81902 00000000     a...............
bw2 = bw._replace(version_group='black2-white2')


# Alright let's add these to the database

pickups = [em, dp, pl, hg, bw, bw2]

sess = pokedex.db.connect()

version_groups = {}
for vg in sess.query(t.VersionGroup).all():
    version_groups[vg.identifier] = vg

def get_item(generation_id, item_index):
    item = (sess.query(t.Item)
        .join(t.ItemGameIndex)
        .filter(t.ItemGameIndex.generation_id == generation_id)
        .filter(t.ItemGameIndex.game_index == item_index)
        .one())
    return item

for pickup in pickups:
    version_group = version_groups[pickup.version_group]

    def get_items(items):
        return [get_item(version_group.generation_id, item_index)
                for item_index in items]

    common_items = get_items(pickup.common_items)
    rare_items = get_items(pickup.rare_items)
    rates = pickup.rates + [1, 1]

    for tier in range(10):
        min_level = 1 + tier * 10
        max_level = 10 + tier * 10

        items = common_items[tier:tier+len(pickup.rates)]
        items += reversed(rare_items[tier:tier+2])

        for rarity, slot, item in zip(rates, range(len(rates)), items):
            pi = t.PickupItem()
            pi.version_group = version_group
            pi.min_level = min_level
            pi.max_level = max_level
            pi.slot = slot
            pi.item = item
            pi.rarity = rarity
            sess.add(pi)

sess.commit()
