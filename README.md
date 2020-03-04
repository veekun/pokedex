# pokedex

This is a Python library slash pile of data containing a whole lot of data scraped from Pokémon games.
It's the primary guts of [veekun](https://veekun.com/).

## Current status

The project is not _dead_, but it is _languishing_.
It's currently being maintained by only its creator ([eevee](https://eev.ee/)) and a couple of other contributors,
who are also occupied with a lot of other things.

The project needs to be modernized and to have a lot of rough edges fixed that would also make it easier
to maintain for the games and generations to come.

### Status of the YAML migration

**Update from 2017-06-18**

@eevee started on an experiment with switching to YAML for data storage some time ago, for a variety of reasons.
It's finally starting to show some promise — all of gen 7 was dumped to a YAML format, then loaded into the database
from there — but it'll take a lot more work to get this usable. The intended _upsides_ are:

- The data will include everything from older games, so you don't have to guess! 
Also, the veekun site will handle older games correctly, probably!
- Many more filtering and searching tools on veekun, since we won't have to fight SQL to write them!
- More interesting data we've never had before, like trainer teams and overworld items!
And models? Maps, even? Who knows, but working on this stuff should be easier with all this existing code in place!
- A project that's actually documented and not confusing as hell to use!
- A useful command line interface that doesn't require weird setup steps!

If you're interested in this work, hearing about that would be some great motivation! 
In the meantime, veekun will look a bit stagnant. 
We can't dedicate huge amounts of time to it, either, so this may take a while, if it ever gets done at all.
Sorry.


## How can I help?

I don't know! Not many people have the right combination of skills and interests to work on this. 
I guess you could pledge to my [Patreon](https://www.patreon.com/eevee) as some gentle encouragement. :)

If you are a developer, you can of course also contribute to the development of this project via Pull Requests.

### About editing CSV files

Fixing CSV data inconsistency or errors and putting that into a Pull Request it's also appreciated.

Even though, whilst for every new game that we integrate here the initial big dump of data comes directly from
the disassembled game files and scripts that parse their data, there is still some data that needs to be fixed or
introduced manually.

Pull Requests with manually-written modifications to the CSV files introducing data of new games without a trustful
data source will be discarded.

As mentioned, for new games we always try to automate this process with scripts that parse the disassembled game's data
data into CSV, excepting whenever we have to fix some data inconsistency or error.

Raw data can also sometimes come from external data miners, which have disassembled the game content and dumped all the
information into human-readable text files.

## Using the pokedex CLI

A guide is available under the project's [Wiki](https://github.com/veekun/pokedex/wiki).

### Docker support

If you want to use the CLI but you don't want to install all python requirements yourself locally in your
computer, you can use [Docker](https://www.docker.com/) and the provided Dockerfile will do everything for you.

You only need to clone this project, and under the project directory, use the docker helper script to run
any pokedex CLI command:

**Examples**:

Generating the SQLite database from the CSV files:
```bash
bin/docker-pokedex setup -v
```

Dumping the SQLite database back into the CSV files:
```bash
bin/docker-pokedex dump -l all
```

You also have a special command to re-build the docker image (e.g. after editing files):
```bash
bin/docker-pokedex rebuild
```

## License and Copyright

The software is licensed under the MIT license. See the [`LICENSE`](LICENSE) file for full copyright and license text. 
The short version is that you can do what you like with the code, as long as you say where you got it.

This repository includes data extracted from the Pokémon series of video games.
All of it is the intellectual property of Nintendo, Creatures, inc., and GAME FREAK, inc. and is protected by various 
copyrights and trademarks. The author believes that the use of this intellectual property for a fan reference is 
covered by fair use — the use is inherently educational, and the software would be severely impaired without the 
copyrighted material.

That said, any use of this library and its included data is **at your own legal risk**.
