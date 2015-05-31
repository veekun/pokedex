The pokédex tables
==================

.. module:: pokedex.db.tables

The :mod:`pokedex.db.tables` module defines all of the tables in the Pokédex.
They are all defined with SQLAlchemy's
:mod:`~sqlalchemy.ext.declarative` extension.

To introspect the tables programmatically, you can use the following:

.. data:: mapped_classes

    A list of all the classes you see below.

.. data:: metadata

    The SQLAlchemy :class:`~sqlalchemy.schema.MetaData` containing all the
    tables.

Each of the classes has a ``translation_classes`` attribute: a potentially
empty list of translation classes. See :mod:`pokedex.db.multilang` for how
these work.

Many tables have these columns:

- **id**: An integer primary key. Sometimes it's semantically meaningful, most
  often it isn't.
- **identifier**: A string identifier of the class, and the preferred way to
  access individual items.
- **name**: A name (uses the multilang functionality)

Pokémon
-------

.. dex-table:: PokemonSpecies
.. dex-table:: Pokemon
.. dex-table:: PokemonForm
.. dex-table:: EvolutionChain
.. dex-table:: PokemonEvolution

Moves
-----

.. dex-table:: Move
.. dex-table:: MoveEffect
.. dex-table:: MoveMeta

Items
-----

.. dex-table:: Item
.. dex-table:: Berry

Types
-----

.. dex-table:: Type

Abilities
---------

.. dex-table:: Ability

Language
--------

.. dex-table:: Language

Version stuff
-------------

.. dex-table:: Generation
.. dex-table:: VersionGroup
.. dex-table:: Version
.. dex-table:: Pokedex
.. dex-table:: Region

Encounters
----------

.. dex-table:: Location
.. dex-table:: LocationArea
.. dex-table:: LocationAreaEncounterRate
.. dex-table:: Encounter
.. dex-table:: EncounterCondition
.. dex-table:: EncounterConditionValue
.. dex-table:: EncounterMethod
.. dex-table:: EncounterSlot


Contests
--------

.. dex-table:: ContestCombo
.. dex-table:: ContestEffect
.. dex-table:: SuperContestCombo
.. dex-table:: SuperContestEffect

Enum tables
-----------

.. dex-table:: BerryFirmness
.. dex-table:: ContestType
.. dex-table:: EggGroup
.. dex-table:: EvolutionTrigger
.. dex-table:: Gender
.. dex-table:: GrowthRate
.. dex-table:: ItemCategory
.. dex-table:: ItemFlingEffect
.. dex-table:: ItemPocket
.. dex-table:: MoveBattleStyle
.. dex-table:: MoveDamageClass
.. dex-table:: MoveMetaAilment
.. dex-table:: MoveMetaCategory
.. dex-table:: MoveTarget
.. dex-table:: Nature
.. dex-table:: PalParkArea
.. dex-table:: PokemonColor
.. dex-table:: PokemonMoveMethod
.. dex-table:: PokemonShape
.. dex-table:: Stat

Changelogs
----------

.. dex-table:: AbilityChangelog
.. dex-table:: MoveEffectChangelog
.. dex-table:: MoveChangelog

Flavor text
-----------

.. dex-table:: ItemFlavorText
.. dex-table:: AbilityFlavorText
.. dex-table:: MoveFlavorText
.. dex-table:: PokemonSpeciesFlavorText

Association tables
------------------

.. dex-table:: BerryFlavor
.. dex-table:: EncounterConditionValueMap
.. dex-table:: ItemFlag
.. dex-table:: ItemFlagMap
.. dex-table:: Machine
.. dex-table:: MoveFlag
.. dex-table:: MoveFlagMap
.. dex-table:: MoveMetaStatChange
.. dex-table:: NatureBattleStylePreference
.. dex-table:: NaturePokeathlonStat
.. dex-table:: PokeathlonStat
.. dex-table:: PokedexVersionGroup
.. dex-table:: PokemonAbility
.. dex-table:: PokemonEggGroup
.. dex-table:: PokemonFormPokeathlonStat
.. dex-table:: PokemonHabitat
.. dex-table:: PokemonMove
.. dex-table:: PokemonStat
.. dex-table:: PokemonItem
.. dex-table:: PokemonType
.. dex-table:: TypeEfficacy
.. dex-table:: VersionGroupPokemonMoveMethod
.. dex-table:: VersionGroupRegion

Index maps
----------

.. dex-table:: ItemGameIndex
.. dex-table:: LocationGameIndex
.. dex-table:: PokemonDexNumber
.. dex-table:: PokemonFormGeneration
.. dex-table:: PokemonGameIndex
.. dex-table:: TypeGameIndex

Mics tables
-----------

.. dex-table:: Experience
.. dex-table:: PalPark
.. dex-table:: Characteristic

Conquest tables
---------------

.. dex-table:: ConquestEpisode
.. dex-table:: ConquestEpisodeWarrior
.. dex-table:: ConquestKingdom
.. dex-table:: ConquestMaxLink
.. dex-table:: ConquestMoveData
.. dex-table:: ConquestMoveDisplacement
.. dex-table:: ConquestMoveEffect
.. dex-table:: ConquestMoveRange
.. dex-table:: ConquestPokemonAbility
.. dex-table:: ConquestPokemonEvolution
.. dex-table:: ConquestPokemonMove
.. dex-table:: ConquestPokemonStat
.. dex-table:: ConquestStat
.. dex-table:: ConquestTransformationPokemon
.. dex-table:: ConquestTransformationWarrior
.. dex-table:: ConquestWarrior
.. dex-table:: ConquestWarriorArchetype
.. dex-table:: ConquestWarriorRank
.. dex-table:: ConquestWarriorRankStatMap
.. dex-table:: ConquestWarriorSkill
.. dex-table:: ConquestWarriorSpecialty
.. dex-table:: ConquestWarriorStat
.. dex-table:: ConquestWarriorTransformation
