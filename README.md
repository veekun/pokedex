# pokedex

This is a Python library slash pile of data containing a whole lot of data scraped from Pokémon games.  It's the primary guts of [veekun](https://veekun.com/).

## Current status

The project is not _dead_, but it is _languishing_.  It's currently being maintained by only a single person ([eevee](https://eev.ee/)), who is also preoccupied with a lot of other things.  It needs a lot of TLC to modernize it and fix a lot of rough edges, but updating it for newly-released games is even more urgent, and that's not happening very quickly either.

I started on an experiment with switching to YAML for data storage some time ago, for a variety of reasons.  Then new games came out and interrupted me.  I knew that if I didn't commit to the YAML thing then it would never get finished and I'd just grow to resent this project, so for Sun and Moon, I'm dumping to YAML _first_ and then loading that into the old database.  I'm also writing all the extraction code from scratch, since historically our process for new games has involved dozens of little ad-hoc programs we keep losing and a lot of manual effort.

That means the YAML project is finally starting to show some promise, but it's taking me forever to actually get Sun and Moon data on the site.

On the other hand, if I can get this going, the results could be _fantastic_:

- The data will include everything from older games, so you don't have to guess!  Also, the site will handle older games correctly, probably!
- Many more filtering and searching tools on veekun, since I won't have to fight SQL to write them!
- More interesting data we've never had before, like trainer teams and overworld items!  And models?  Maps, even?  Who knows, but working on this stuff should be easier with all this existing code in place!
- A project that's actually documented and not confusing as hell to use!
- A useful command line interface that doesn't require weird setup steps!

So please be patient.  :)


### How can I help?

I don't know!  Not many people have the right combination of skills and interests to work on this.  I guess you could pledge to my [Patreon](https://www.patreon.com/eevee) as some gentle encouragement.  :)


## Copyright and whatnot

The software is licensed under the MIT license.  See the `LICENSE` file for full copyright and license text.  The short version is that you can do what you like with the code, as long as you say where you got it.

This repository includes data extracted from the Pokémon series of video games.  All of it is the intellectual property of Nintendo, Creatures, inc., and GAME FREAK, inc. and is protected by various copyrights and trademarks.  The author believes that the use of this intellectual property for a fan reference is covered by fair use — the use is inherently educational, and the software would be severely impaired without the copyrighted material.

That said, any use of this library and its included data is **at your own legal risk**.
