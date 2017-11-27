# pokedex

This is a Python library slash pile of data containing a whole lot of data scraped from Pokémon games.  It's the primary guts of [veekun](https://veekun.com/).

## Current status

The project is not _dead_, but it is _languishing_.  It's currently being maintained by only a single person ([eevee](https://eev.ee/)), who is also preoccupied with a lot of other things.  It needs a lot of TLC to modernize it and fix a lot of rough edges.

I started on an experiment with switching to YAML for data storage some time ago, for a variety of reasons.  It's finally starting to show some promise — all of gen 7 was dumped to a YAML format, then loaded into the database from there — but it'll take a lot more work to get this usable.  The intended _upsides_ are:

- The data will include everything from older games, so you don't have to guess!  Also, the site will handle older games correctly, probably!
- Many more filtering and searching tools on veekun, since I won't have to fight SQL to write them!
- More interesting data we've never had before, like trainer teams and overworld items!  And models?  Maps, even?  Who knows, but working on this stuff should be easier with all this existing code in place!
- A project that's actually documented and not confusing as hell to use!
- A useful command line interface that doesn't require weird setup steps!

If you're interested in this work, hearing about that would be some great motivation!  In the meantime, veekun will look a bit stagnant.  I can't dedicate huge amounts of time to it, either, so this may take a while, if it ever gets done at all.  Sorry.


### How can I help?

I don't know!  Not many people have the right combination of skills and interests to work on this.  I guess you could pledge to my [Patreon](https://www.patreon.com/eevee) as some gentle encouragement.  :)


## Copyright and whatnot

The software is licensed under the MIT license.  See the `LICENSE` file for full copyright and license text.  The short version is that you can do what you like with the code, as long as you say where you got it.

This repository includes data extracted from the Pokémon series of video games.  All of it is the intellectual property of Nintendo, Creatures, inc., and GAME FREAK, inc. and is protected by various copyrights and trademarks.  The author believes that the use of this intellectual property for a fan reference is covered by fair use — the use is inherently educational, and the software would be severely impaired without the copyrighted material.

That said, any use of this library and its included data is **at your own legal risk**.
