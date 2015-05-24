# encoding: utf8

u"""The Pokédex schema.

Columns have a info dictionary with these keys:
- official: True if the values appear in games or official material; False if
  they are fan-created or fan-written. This flag is currently only set for
  official text columns.
- format: The format of a text column. Can be one of:
  - plaintext: Normal Unicode text (widely used in names)
  - markdown: Veekun's Markdown flavor (generally used in effect descriptions)
  - gametext: Transcription of in-game text that strives to be both
    human-readable and represent the original text exactly.
  - identifier: A fan-made identifier in the [-_a-z0-9]* format. Not intended
    for translation.
  - latex: A formula in LaTeX syntax.
- ripped: True for text that has been ripped from the games, and can be ripped
  again for new versions or languages

- string_getter: for translation columns, a function taking (text, session,
  language) that is used for properties on the main table. Used for Markdown
  text.

See `pokedex.db.multilang` for how localizable text columns work.  The session
classes in that module can be used to change the default language.
"""

from pokedex.db.tables.base import (
    metadata, TableBase, mapped_classes, Language, create_translation_table)

from pokedex.db.tables.core import (
    Ability, AbilityChangelog, AbilityFlavorText, Berry, BerryFirmness,
    BerryFlavor, Characteristic, ContestCombo, ContestEffect, ContestType,
    EggGroup, Encounter, EncounterCondition, EncounterConditionValue,
    EncounterConditionValueMap, EncounterMethod, EncounterSlot, EvolutionChain,
    EvolutionTrigger, Experience, Gender, Generation, GrowthRate, Item,
    ItemCategory, ItemFlag, ItemFlagMap, ItemFlavorText, ItemFlingEffect,
    ItemGameIndex, ItemPocket, Location, LocationArea,
    LocationAreaEncounterRate, LocationGameIndex, Machine, Move,
    MoveBattleStyle, MoveChangelog, MoveDamageClass, MoveEffect,
    MoveEffectChangelog, MoveFlag, MoveFlagMap, MoveFlavorText, MoveMeta,
    MoveMetaAilment, MoveMetaCategory, MoveMetaStatChange, MoveTarget, Nature,
    NatureBattleStylePreference, NaturePokeathlonStat, PalPark, PalParkArea,
    PokeathlonStat, Pokedex, PokedexVersionGroup, Pokemon, PokemonAbility,
    PokemonColor, PokemonDexNumber, PokemonEggGroup, PokemonEvolution,
    PokemonForm, PokemonFormGeneration, PokemonFormPokeathlonStat,
    PokemonGameIndex, PokemonHabitat, PokemonItem, PokemonMove,
    PokemonMoveMethod, PokemonShape, PokemonSpecies, PokemonSpeciesFlavorText,
    PokemonStat, PokemonType, Region, Stat, SuperContestCombo,
    SuperContestEffect, Type, TypeEfficacy, TypeGameIndex, Version,
    VersionGroup, VersionGroupPokemonMoveMethod, VersionGroupRegion)

from pokedex.db.tables.conquest import (
    ConquestEpisode, ConquestEpisodeWarrior, ConquestKingdom, ConquestMaxLink,
    ConquestMoveData, ConquestMoveDisplacement, ConquestMoveEffect,
    ConquestMoveRange, ConquestPokemonAbility, ConquestPokemonEvolution,
    ConquestPokemonMove, ConquestPokemonStat, ConquestStat,
    ConquestTransformationPokemon, ConquestTransformationWarrior,
    ConquestWarrior, ConquestWarriorArchetype, ConquestWarriorRank,
    ConquestWarriorRankStatMap, ConquestWarriorSkill, ConquestWarriorSpecialty,
    ConquestWarriorStat, ConquestWarriorTransformation)
