# encoding: utf8

u"""The Pokédex schema

Columns have a info dictionary with these keys:
- description: The description of the column
- official: True if the values appear in games or official material; False if
  they are fan-created or fan-written. This flag is currently only set for
  official text columns.
- markup: The format of a text column. Can be one of:
  - plaintext: Normal Unicode text (widely used in names)
  - markdown: Veekun's Markdown flavor (generally used in effect descriptions)
  - gametext: Transcription of in-game text that strives to be both
    human-readable and represent the original text exactly.
  - identifier: A fan-made identifier in the [-_a-z0-9]* format. Not intended
    for translation.
  - latex: A formula in LaTeX syntax.
- foreign: If set, the column contains foreign (non-English) text.

"""
# XXX: Check if "gametext" is set correctly everywhere

# XXX: Some columns paradoxically have official=True and markup='identifier'.
# This is when one column is used as both the English name (lowercased) and
# an identifier. This should be fixed.

from sqlalchemy import Column, ForeignKey, MetaData, PrimaryKeyConstraint, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, eagerload_all, relation
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import and_
from sqlalchemy.types import *

from pokedex.db import markdown

metadata = MetaData()
TableBase = declarative_base(metadata=metadata)

class Ability(TableBase):
    u"""An ability a pokémon can have, such as Static or Pressure.
    """
    __tablename__ = 'abilities'
    __singlename__ = 'ability'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(24), nullable=False,
        info=dict(description="The official English name of this ability", official=True, format='plaintext'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description="ID of the generation this ability was introduced in", detail=True))
    effect = Column(markdown.MarkdownColumn(5120), nullable=False,
        info=dict(description="Detailed description of this ability's effect", format='markdown'))
    short_effect = Column(markdown.MarkdownColumn(255), nullable=False,
        info=dict(description="Short summary of this ability's effect", format='markdown'))

class AbilityFlavorText(TableBase):
    u"""In-game flavor text of an ability
    """
    __tablename__ = 'ability_flavor_text'
    ability_id = Column(Integer, ForeignKey('abilities.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The versions this flavor text is shown in"))
    flavor_text = Column(Unicode(64), nullable=False,
        info=dict(description="The actual flavor text", official=True, format='gametext'))

class AbilityName(TableBase):
    u"""Non-English official name of an ability
    """
    __tablename__ = 'ability_names'
    ability_id = Column(Integer, ForeignKey('abilities.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the ability"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the language"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description="ID of the language", official=True, foreign=True, format='plaintext'))

class Berry(TableBase):
    u"""A Berry, consumable item that grows on trees

    For data common to all Items, such as the name, see the corresponding Item entry.
    """
    __tablename__ = 'berries'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False,
        info=dict(description="ID of the Item this Berry corresponds to"))
    firmness_id = Column(Integer, ForeignKey('berry_firmness.id'), nullable=False,
        info=dict(description="ID of this berry's firmness"))
    natural_gift_power = Column(Integer, nullable=True,
        info=dict(description="Power of Natural Gift when that move is used with this Berry"))
    natural_gift_type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        info=dict(description="ID of the Type that Natural Gift will have when used with this Berry"))
    size = Column(Integer, nullable=False,
        info=dict(description=u"Size of this Berry, in millimeters"))
    max_harvest = Column(Integer, nullable=False,
        info=dict(description="Maximum number of these berries that can grow on one tree"))
    growth_time = Column(Integer, nullable=False,
        info=dict(description="Time it takes the tree to grow one stage, in hours. Multiply by four to get overall time."))
    soil_dryness = Column(Integer, nullable=False,
        info=dict(description="The speed of soil drying the tree causes"))  # XXX: What's this exactly? I'm not a good farmer
    smoothness = Column(Integer, nullable=False,
        info=dict(description="Smoothness of this Berry, a culinary attribute. Higher is better."))

class BerryFirmness(TableBase):
    u"""A Berry firmness, such as "hard" or "very soft".
    """
    __tablename__ = 'berry_firmness'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(10), nullable=False,
        info=dict(description="English name of the firmness level", official=True, format='plaintext'))

class BerryFlavor(TableBase):
    u"""A Berry flavor level.
    """
    __tablename__ = 'berry_flavors'
    berry_id = Column(Integer, ForeignKey('berries.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the berry"))
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the flavor"))
    flavor = Column(Integer, nullable=False,
        info=dict(description="Level of the flavor in the berry"))

class ContestCombo(TableBase):
    u"""Combo of two moves in a Contest.
    """
    __tablename__ = 'contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the first move in the combo"))
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the second and final move in the combo"))

class ContestEffect(TableBase):
    u"""Effect of a move when used in a Contest.
    """
    __tablename__ = 'contest_effects'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    appeal = Column(SmallInteger, nullable=False,
        info=dict(description="The base number of hearts the user of this move gets"))
    jam = Column(SmallInteger, nullable=False,
        info=dict(description="The base number of hearts the user's opponent loses"))
    flavor_text = Column(Unicode(64), nullable=False,
        info=dict(description="English in-game description of this effect", official=True, format='gametext'))
    effect = Column(Unicode(255), nullable=False,
        info=dict(description="Detailed description of the effect", format='markdown'))

class ContestType(TableBase):
    u"""A Contest type, such as "cool" or "smart". Also functions as Berry flavor and Pokéblock color.
    """
    __tablename__ = 'contest_types'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(6), nullable=False,
        info=dict(description="The English name of the Contest type", official=True, format='identifier'))
    flavor = Column(Unicode(6), nullable=False,
        info=dict(description="The English name of the corresponding Berry flavor", official=True, format='identifier'))
    color = Column(Unicode(6), nullable=False,
        info=dict(description=u"The English name of the corresponding Pokéblock color", official=True, format='identifier'))

class EggGroup(TableBase):
    u"""An Egg group. Usually, two Pokémon can breed if they share an Egg Group.

    (exceptions are the Ditto and No Eggs groups)
    """
    __tablename__ = 'egg_groups'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u'The English "official" name. One NPC in Stadium uses these names; they are pretty bad.', official=True, format='identifier'))

class Encounter(TableBase):
    u"""Encounters with wild Pokémon.

    Bear with me, here.

    Within a given area in a given game, encounters are differentiated by the
    "slot" they are in and the state of the game world.

    What the player is doing to get an encounter, such as surfing or walking
    through tall grass, is called terrain.  Each terrain has its own set of
    encounter slots.

    Within a terrain, slots are defined primarily by rarity.  Each slot can
    also be affected by world conditions; for example, the 20% slot for walking
    in tall grass is affected by whether a swarm is in effect in that area.
    "Is there a swarm?" is a condition; "there is a swarm" and "there is not a
    swarm" are the possible values of this condition.

    A slot (20% walking in grass) and any appropriate world conditions (no
    swarm) are thus enough to define a specific encounter.

    Well, okay, almost: each slot actually appears twice.
    """

    __tablename__ = 'encounters'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the Version this applies to"))
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the Location of this encounter"))
    encounter_slot_id = Column(Integer, ForeignKey('encounter_slots.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter slot, which determines terrain and rarity"))
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the encountered Pokémon"))
    min_level = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u"The minimum level of the encountered Pokémon"))
    max_level = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u"The maxmum level of the encountered Pokémon"))

class EncounterCondition(TableBase):
    u"""A conditions in the game world that affects pokémon encounters, such as time of day.
    """

    __tablename__ = 'encounter_conditions'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(64), nullable=False,
        info=dict(description="An English name of the condition", format='plaintext'))

class EncounterConditionValue(TableBase):
    u"""A possible state for a condition; for example, the state of 'swarm' could be 'swarm' or 'no swarm'.
    """

    __tablename__ = 'encounter_condition_values'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), primary_key=False, nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter condition this is a value of"))
    name = Column(Unicode(64), nullable=False,
        info=dict(description="An english name of this value", format='plaintext'))
    is_default = Column(Boolean, nullable=False,
        info=dict(description='Set if this value is "default" or "normal" in some sense'))

class EncounterConditionValueMap(TableBase):
    u"""Maps encounters to the specific conditions under which they occur.
    """
    __tablename__ = 'encounter_condition_value_map'
    encounter_id = Column(Integer, ForeignKey('encounters.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the encounter"))
    encounter_condition_value_id = Column(Integer, ForeignKey('encounter_condition_values.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the encounter condition value"))

class EncounterTerrain(TableBase):
    u"""A way the player can enter a wild encounter, e.g., surfing, fishing, or walking through tall grass.
    """

    __tablename__ = 'encounter_terrain'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(64), nullable=False,
        info=dict(description="An english name of this terrain", format='plaintext'))

class EncounterSlot(TableBase):
    u"""An abstract "slot" within a terrain, associated with both some set of conditions and a rarity.

    Note that there are two encounters per slot, so the rarities will only add
    up to 50.
    """

    __tablename__ = 'encounter_slots'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the Version group this slot is in"))
    encounter_terrain_id = Column(Integer, ForeignKey('encounter_terrain.id'), primary_key=False, nullable=False, autoincrement=False,
        info=dict(description="The ID of the terrain"))
    slot = Column(Integer, nullable=True,
        info=dict(description="The slot")) # XXX: What is this, exactly?
    rarity = Column(Integer, nullable=False,
        info=dict(description="The chance of the encounter, in percent"))  # XXX: It is in percent, right? I'm confused.

class EncounterSlotCondition(TableBase):
    u"""A condition that affects an encounter slot.
    """
    __tablename__ = 'encounter_slot_conditions'
    encounter_slot_id = Column(Integer, ForeignKey('encounter_slots.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter slot"))
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter condition"))

class EvolutionChain(TableBase):
    u"""A family of pokémon that are linked by evolution
    """
    __tablename__ = 'evolution_chains'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), nullable=False,
        info=dict(description="ID of the growth rate for this family"))
    baby_trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        info=dict(description="Item that a parent must hold while breeding to produce a baby"))

class EvolutionTrigger(TableBase):
    u"""An evolution type, such as "level" or "trade".
    """
    __tablename__ = 'evolution_triggers'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An English identifier", format='identifier'))

class Experience(TableBase):
    u"""EXP needed for a certain level with a certain growth rate
    """
    __tablename__ = 'experience'
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), primary_key=True, nullable=False,
        info=dict(description="ID of the growth rate"))
    level = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The level"))
    experience = Column(Integer, nullable=False,
        info=dict(description="The number of EXP points needed to get to that level"))

class Generation(TableBase):
    u"""A Generation of the pokémon franchise
    """
    __tablename__ = 'generations'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    main_region_id = Column(Integer, ForeignKey('regions.id'),
        info=dict(description="ID of the region this generation's main games take place in"))
    canonical_pokedex_id = Column(Integer, ForeignKey('pokedexes.id'),
        info=dict(description=u"ID of the pokédex this generation's main games use by default"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u'An English name of this generation, such as "Generation IV"', format='plaintext'))

class GrowthRate(TableBase):
    u"""Growth rate of a pokémon, i.e. the EXP → level function.
    """
    __tablename__ = 'growth_rates'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(20), nullable=False,
        info=dict(description="A name for the", format='identifier'))
    formula = Column(Unicode(500), nullable=False,
        info=dict(description="The formula", format='latex'))

class Item(TableBase):
    u"""An Item from the games, like "Poké Ball" or "Bicycle".
    """
    __tablename__ = 'items'
    __singlename__ = 'item'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(20), nullable=False,
        info=dict(description="The English name of the item", official=True, format='plaintext'))
    category_id = Column(Integer, ForeignKey('item_categories.id'), nullable=False,
        info=dict(description="ID of a category this item belongs to"))
    cost = Column(Integer, nullable=False,
        info=dict(description=u"Cost of the item when bought. Items sell for half this price."))
    fling_power = Column(Integer, nullable=True,
        info=dict(description=u"Power of the move Fling when used with this item."))
    fling_effect_id = Column(Integer, ForeignKey('item_fling_effects.id'), nullable=True,
        info=dict(description=u"ID of the fling-effect of the move Fling when used with this item. Note that these are different from move effects."))
    effect = Column(markdown.MarkdownColumn(5120), nullable=False,
        info=dict(description=u"Detailed English description of the item's effect.", format='markdown'))

    @property
    def appears_underground(self):
        u"""True if the item appears underground, as specified by the appropriate flag
        """
        return any(flag.identifier == u'underground' for flag in self.flags)

class ItemCategory(TableBase):
    u"""An item category
    """
    # XXX: This is fanon, right?
    __tablename__ = 'item_categories'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    pocket_id = Column(Integer, ForeignKey('item_pockets.id'), nullable=False,
        info=dict(description="ID of the pocket these items go to"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description="English name of the category", format='plaintext'))

class ItemFlag(TableBase):
    u"""An item attribute such as "consumable" or "holdable".
    """
    __tablename__ = 'item_flags'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(24), nullable=False,
        info=dict(description="Identifier of the flag", format='identifier'))
    name = Column(Unicode(64), nullable=False,
        info=dict(description="Short English description of the flag", format='plaintext'))

class ItemFlagMap(TableBase):
    u"""Maps an item flag to its item.
    """
    __tablename__ = 'item_flag_map'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="The ID of the item"))
    item_flag_id = Column(Integer, ForeignKey('item_flags.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="The ID of the item flag"))

class ItemFlavorText(TableBase):
    u"""An in-game description of an item
    """
    __tablename__ = 'item_flavor_text'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="The ID of the item"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="ID of the version group that sports this text"))
    flavor_text = Column(Unicode(255), nullable=False,
        info=dict(description="The flavor text itself", official=True, format='gametext'))

class ItemFlingEffect(TableBase):
    u"""An effect of the move Fling when used with a specific item
    """
    __tablename__ = 'item_fling_effects'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    effect = Column(Unicode(255), nullable=False,
        info=dict(description="English description of the effect", format='plaintext'))

class ItemInternalID(TableBase):
    u"""The internal ID number a game uses for an item
    """
    __tablename__ = 'item_internal_ids'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="The database ID of the item"))
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="ID of the generation of games"))
    internal_id = Column(Integer, nullable=False,
        info=dict(description="Internal ID of the item in the generation"))

class ItemName(TableBase):
    u"""A non-English name of an item
    """
    __tablename__ = 'item_names'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the item"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the language"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description="The name of the item in this language", foreign=True, format='plaintext'))

class ItemPocket(TableBase):
    u"""A pocket that categorizes items
    """
    __tablename__ = 'item_pockets'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An identifier of this pocket", format='identifier'))
    name = Column(Unicode(16), nullable=False,
        info=dict(description="A numeric ID", format='plaintext'))

class Language(TableBase):
    u"""A language the Pokémon games have been transleted into; except English
    """
    __tablename__ = 'languages'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    iso639 = Column(Unicode(2), nullable=False,
        info=dict(description="The two-letter code of the country where this language is spoken. Note that it is not unique."))
    iso3166 = Column(Unicode(2), nullable=False,
        info=dict(description="The two-letter code of the language. Note that it is not unique."))
    name = Column(Unicode(16), nullable=False,
        info=dict(description="The English name of the language", format='plaintext'))

class Location(TableBase):
    u"""A place in the Pokémon world
    """
    __tablename__ = 'locations'
    __singlename__ = 'location'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    region_id = Column(Integer, ForeignKey('regions.id'),
        info=dict(description="ID of the region this location is in"))
    name = Column(Unicode(64), nullable=False,
        info=dict(description="English name of the location", official=True, format='plaintext'))

class LocationArea(TableBase):
    u"""A sub-area of a location
    """
    __tablename__ = 'location_areas'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False,
        info=dict(description="ID of the location this area is part of"))
    internal_id = Column(Integer, nullable=False,
        info=dict(description="ID the games ude for this area"))
    name = Column(Unicode(64), nullable=True,
        info=dict(description="An English name of the area, if applicable", format='plaintext'))

class LocationAreaEncounterRate(TableBase):
    # XXX: What's this exactly? Someone add the docstring & revise the descriptions
    __tablename__ = 'location_area_encounter_rates'
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the area"))
    encounter_terrain_id = Column(Integer, ForeignKey('encounter_terrain.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the terrain"))
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, autoincrement=False,
        info=dict(description="ID of the version"))
    rate = Column(Integer, nullable=True,
        info=dict(description="The encounter rate"))  # units?

class LocationInternalID(TableBase):
    u"""IDs the games use internally for locations
    """
    __tablename__ = 'location_internal_ids'
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False, primary_key=True,
        info=dict(description="Database ID of the locaion"))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False, primary_key=True,
        info=dict(description="ID of the generation this entry to"))
    internal_id = Column(Integer, nullable=False,
        info=dict(description="Internal game ID of the location"))

class Machine(TableBase):
    u"""A TM or HM; numbered item that can teach a move to a pokémon
    """
    __tablename__ = 'machines'
    machine_number = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="Number of the machine for TMs, or 100 + the munber for HMs"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="Versions this entry applies to"))
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False,
        info=dict(description="ID of the corresponding Item"))
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False,
        info=dict(description="ID of the taught move"))

    @property
    def is_hm(self):
        u"""True if this machine is a HM, False if it's a TM
        """
        return self.machine_number >= 100

class MoveBattleStyle(TableBase):
    u"""A battle style of a move"""  # XXX: Explain better
    __tablename__ = 'move_battle_styles'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(8), nullable=False,
        info=dict(description="An English name for this battle style", format='plaintext'))

class MoveEffectCategory(TableBase):
    u"""Category of a move effect
    """
    __tablename__ = 'move_effect_categories'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(64), nullable=False,
        info=dict(description="English name of the category", format='plaintext'))
    can_affect_user = Column(Boolean, nullable=False,
        info=dict(description="Set if the user can be affected"))

class MoveEffectCategoryMap(TableBase):
    u"""Maps a move effect category to a move effect
    """
    __tablename__ = 'move_effect_category_map'
    move_effect_id = Column(Integer, ForeignKey('move_effects.id'), primary_key=True, nullable=False,
        info=dict(description="ID of the move effect"))
    move_effect_category_id = Column(Integer, ForeignKey('move_effect_categories.id'), primary_key=True, nullable=False,
        info=dict(description="ID of the category"))
    affects_user = Column(Boolean, primary_key=True, nullable=False,
        info=dict(description="Set if the user is affected"))

class MoveDamageClass(TableBase):
    u"""Damage class of a move, i.e. "Physical", "Special, or "None".
    """
    __tablename__ = 'move_damage_classes'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(8), nullable=False,
        info=dict(description="An English name of the class", format='plaintext'))
    description = Column(Unicode(64), nullable=False,
        info=dict(description="An English description of the class", format='plaintext'))

class MoveEffect(TableBase):
    u"""An effect of a move
    """
    __tablename__ = 'move_effects'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    short_effect = Column(Unicode(256), nullable=False,
        info=dict(description="A short summary of the effect", format='plaintext'))
    effect = Column(Unicode(5120), nullable=False,
        info=dict(description="A detailed description of the effect", format='plaintext'))

class MoveFlag(TableBase):
    u"""Maps a move flag to a move
    """
    # XXX: Other flags have a ___Flag class for the actual flag and ___FlagMap for the map,
    # these, somewhat confusingly, have MoveFlagType and MoveFlag
    __tablename__ = 'move_flags'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move"))
    move_flag_type_id = Column(Integer, ForeignKey('move_flag_types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the flag"))

class MoveFlagType(TableBase):
    u"""A Move attribute such as "snatchable" or "contact".
    """
    __tablename__ = 'move_flag_types'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="A short identifier for the flag", format='identifier'))
    name = Column(Unicode(32), nullable=False,
        info=dict(description="An English name for the flag", format='plaintext'))
    description = Column(markdown.MarkdownColumn(128), nullable=False,
        info=dict(description="A short English description of the flag", format='markdown'))

class MoveFlavorText(TableBase):
    u"""In-game description of a move
    """
    __tablename__ = 'move_flavor_text'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the version group this text appears in"))
    flavor_text = Column(Unicode(255), nullable=False,
        info=dict(description="The English flavor text", official=True, format='gametext'))

class MoveName(TableBase):
    u"""Non-English name of a move
    """
    __tablename__ = 'move_names'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the language"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description="ID of the language", foreign=True, format='plaintext'))

class MoveTarget(TableBase):
    u"""Targetting or "range" of a move, e.g. "Affects all opponents" or "Affects user".
    """
    __tablename__ = 'move_targets'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(32), nullable=False,
        info=dict(description="An English name", format='plaintext'))
    description = Column(Unicode(128), nullable=False,
        info=dict(description="An English description", format='plaintext'))

class Move(TableBase):
    u"""A Move: technique or attack a Pokémon can learn to use
    """
    __tablename__ = 'moves'
    __singlename__ = 'move'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(24), nullable=False,
        info=dict(description="The English name of the move", official=True, format='plaintext'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description="ID of the generation this move first appeared in"))
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        info=dict(description="ID of the move's elemental type"))
    power = Column(SmallInteger, nullable=False,
        info=dict(description="Base power of the move"))
    pp = Column(SmallInteger, nullable=False,
        info=dict(description="Base PP (Power Points) of the move"))
    accuracy = Column(SmallInteger, nullable=True,
        info=dict(description="Accuracy of the move; NULL means it never misses"))
    priority = Column(SmallInteger, nullable=False,
        info=dict(description="The move's priority bracket"))
    target_id = Column(Integer, ForeignKey('move_targets.id'), nullable=False,
        info=dict(description="ID of the target (range) of the move"))
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=False,
        info=dict(description="ID of the damage class (physical/special) of the move"))
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=False,
        info=dict(description="ID of the move's effect"))
    effect_chance = Column(Integer,
        info=dict(description="The chance for a secondary effect. What this is a chance of is specified by the move's effect."))
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), nullable=True,
        info=dict(description="ID of the move's Contest type (e.g. cool or smart)"))
    contest_effect_id = Column(Integer, ForeignKey('contest_effects.id'), nullable=True,
        info=dict(description="ID of the move's Contest effect"))
    super_contest_effect_id = Column(Integer, ForeignKey('super_contest_effects.id'), nullable=True,
        info=dict(description="ID of the move's Super Contest effect"))

class Nature(TableBase):
    u"""A nature a pokémon can have, such as Calm or Brave
    """
    __tablename__ = 'natures'
    __singlename__ = 'nature'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(8), nullable=False,
        info=dict(description="An English name of the nature", official=True, format='plaintext'))
    decreased_stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False,
        info=dict(description="ID of the stat that this nature decreases by 10% (if decreased_stat_id is the same, the effects cancel out)"))
    increased_stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False,
        info=dict(description="ID of the stat that this nature increases by 10% (if decreased_stat_id is the same, the effects cancel out)"))
    hates_flavor_id = Column(Integer, ForeignKey('contest_types.id'), nullable=False,
        info=dict(description=u"ID of the Berry flavor the Pokémon hates (if likes_flavor_id is the same, the effects cancel out)"))
    likes_flavor_id = Column(Integer, ForeignKey('contest_types.id'), nullable=False,
        info=dict(description=u"ID of the Berry flavor the Pokémon likes (if hates_flavor_id is the same, the effects cancel out)"))

    @property
    def is_neutral(self):
        u"""Returns True iff this nature doesn't alter a Pokémon's stats,
        bestow taste preferences, etc.
        """
        return self.increased_stat_id == self.decreased_stat_id

class NatureBattleStylePreference(TableBase):
    u"""Battle Palace move preference

    Specifies how likely a pokémon with a specific Nature is to use a move of
    a particular battl style in Battle Palace or Battle Tent
    """
    __tablename__ = 'nature_battle_style_preferences'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False,
        info=dict(description=u"ID of the pokémon's nature"))
    move_battle_style_id = Column(Integer, ForeignKey('move_battle_styles.id'), primary_key=True, nullable=False,
        info=dict(description="ID of the battle style"))
    low_hp_preference = Column(Integer, nullable=False,
        info=dict(description=u"Chance of using the move, in percent, if HP is under ½"))
    high_hp_preference = Column(Integer, nullable=False,
        info=dict(description=u"Chance of using the move, in percent, if HP is over ½"))

class NatureName(TableBase):
    u"""Non-english name of a Nature
    """
    __tablename__ = 'nature_names'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the nature"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the language"))
    name = Column(Unicode(8), nullable=False,
        info=dict(description="The nature's foreign name", foreign=True, format='plaintext'))

class NaturePokeathlonStat(TableBase):
    u"""Specifies how a Nature affects a Pokéathlon stat
    """
    __tablename__ = 'nature_pokeathlon_stats'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False,
        info=dict(description="ID of the nature"))
    pokeathlon_stat_id = Column(Integer, ForeignKey('pokeathlon_stats.id'), primary_key=True, nullable=False,
        info=dict(description="ID of the stat"))
    max_change = Column(Integer, nullable=False,
        info=dict(description="Maximum change"))

class PokeathlonStat(TableBase):
    u"""A Pokéathlon stat, such as "Stamina" or "Jump".
    """
    __tablename__ = 'pokeathlon_stats'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    name = Column(Unicode(8), nullable=False,
        info=dict(description="The English name of the stat", official=True, format='plaintext'))

class Pokedex(TableBase):
    u"""A collection of pokémon species ordered in a particular way
    """
    __tablename__ = 'pokedexes'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))
    region_id = Column(Integer, ForeignKey('regions.id'), nullable=True,
        info=dict(description=u"ID of the region this pokédex is used in, or None if it's global"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u"An English name of the pokédex", format='plaintext'))
    description = Column(Unicode(512),
        info=dict(description=u"A longer description of the pokédex", format='plaintext'))

class PokedexVersionGroup(TableBase):
    u"""Maps a pokédex to the version group that uses it
    """
    __tablename__ = 'pokedex_version_groups'
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokédex"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the version group"))

class Pokemon(TableBase):
    u"""A species of pokémon. The core to this whole mess.

    Note that I use both 'forme' and 'form' in both code and the database.  I
    only use 'forme' when specifically referring to Pokémon that have multiple
    distinct species as forms—i.e., different stats or movesets.  'Form' is a
    more general term referring to any variation within a species, including
    purely cosmetic forms like Unown.
    """
    # XXX: Refine the form-specific docs
    # XXX: Update form/forme discussion when #179 is dealt with.
    __tablename__ = 'pokemon'
    __singlename__ = 'pokemon'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    name = Column(Unicode(20), nullable=False,
        info=dict(description=u"The English name of the pokémon", official=True, format='plaintext'))
    forme_name = Column(Unicode(16),
        info=dict(description=u"The name of this form, if the species has forms", format='plaintext'))
    forme_base_pokemon_id = Column(Integer, ForeignKey('pokemon.id'),
        info=dict(description=u"ID for the base form, if this species has one"))  # XXX: ?
    generation_id = Column(Integer, ForeignKey('generations.id'),
        info=dict(description=u"ID of the generation this species first appeared in"))
    evolution_chain_id = Column(Integer, ForeignKey('evolution_chains.id'),
        info=dict(description=u"ID of the species' evolution chain (a.k.a. family)"))
    height = Column(Integer, nullable=False,
        info=dict(description=u"The height of the pokémon, in decimeters (tenths of a meter)"))
    weight = Column(Integer, nullable=False,
        info=dict(description=u"The weight of the pokémon, in tenths of a kilogram (decigrams)"))
    species = Column(Unicode(16), nullable=False,
        info=dict(description=u'The short English flavor text, such as "Seed" or "Lizard"; usually affixed with the word "Pokémon"',
        official=True, format='plaintext'))
    color_id = Column(Integer, ForeignKey('pokemon_colors.id'), nullable=False,
        info=dict(description=u"ID of this pokémon's pokédex color, as used for a gimmick search function in the games."))
    pokemon_shape_id = Column(Integer, ForeignKey('pokemon_shapes.id'), nullable=True,
        info=dict(description=u"ID of this pokémon's body shape, as used for a gimmick search function in the games."))
    habitat_id = Column(Integer, ForeignKey('pokemon_habitats.id'), nullable=True,
        info=dict(description=u"ID of this pokémon's habitat, as used for a gimmick search function in the games."))
    gender_rate = Column(Integer, nullable=False,
        info=dict(description=u"The chance of this pokémon being female, in eighths; or -1 for genderless"))
    capture_rate = Column(Integer, nullable=False,
        info=dict(description=u"The base capture rate; up to 255"))
    base_experience = Column(Integer, nullable=False,
        info=dict(description=u"The base EXP gained when defeating this pokémon"))  # XXX: Is this correct?
    base_happiness = Column(Integer, nullable=False,
        info=dict(description=u"The tameness when caught by a normal ball"))
    is_baby = Column(Boolean, nullable=False,
        info=dict(description=u"True iff the pokémon is a baby"))  # XXX: What exactly makes it a baby?
    hatch_counter = Column(Integer, nullable=False,
        info=dict(description=u"Initial hatch counter: one must walk 255 × (hatch_counter + 1) steps before this pokémon's egg hatches, unless utilizing bonuses like Flame Body's"))
    has_gen4_fem_sprite = Column(Boolean, nullable=False,
        info=dict(description=u"Set iff the species' female front sprite is different from the male's in generation IV"))
    has_gen4_fem_back_sprite = Column(Boolean, nullable=False,
        info=dict(description=u"Set iff the species' female back sprite is different from the male's in generation IV"))

    ### Stuff to handle alternate Pokémon forms

    @property
    def national_id(self):
        u"""Returns the National Pokédex number for this Pokémon.  Use this
        instead of the id directly; alternate formes may make the id incorrect.
        """

        if self.forme_base_pokemon_id:
            return self.forme_base_pokemon_id
        return self.id

    @property
    def full_name(self):
        u"""Returns the name of this Pokémon, including its Forme, if any.
        """

        if self.forme_name:
            return "%s %s" % (self.forme_name.title(), self.name)
        return self.name

    @property
    def normal_form(self):
        u"""Returns the normal form for this Pokémon; i.e., this will return
        regular Deoxys when called on any Deoxys form.
        """

        if self.forme_base_pokemon:
            return self.forme_base_pokemon

        return self

    ### Not forms!

    def stat(self, stat_name):
        u"""Returns a PokemonStat record for the given stat name (or Stat row
        object).  Uses the normal has-many machinery, so all the stats are
        effectively cached.
        """
        if isinstance(stat_name, Stat):
            stat_name = stat_name.name

        for pokemon_stat in self.stats:
            if pokemon_stat.stat.name == stat_name:
                return pokemon_stat

        raise KeyError(u'No stat named %s' % stat_name)

    @property
    def better_damage_class(self):
        u"""Returns the MoveDamageClass that this Pokémon is best suited for,
        based on its attack stats.

        If the attack stats are about equal (within 5), returns None.  The
        value None, not the damage class called 'None'.
        """
        phys = self.stat(u'Attack')
        spec = self.stat(u'Special Attack')

        diff = phys.base_stat - spec.base_stat

        if diff > 5:
            return phys.stat.damage_class
        elif diff < -5:
            return spec.stat.damage_class
        else:
            return None

class PokemonAbility(TableBase):
    u"""Maps an ability to a pokémon that can have it
    """
    __tablename__ = 'pokemon_abilities'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False,
        info=dict(description=u"ID of the ability"))
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ability slot, i.e. 1 or 2 for gen. IV"))

class PokemonColor(TableBase):
    u"""The "pokédex color" of a pokémon species. Usually based on the pokémon's color.
    """
    __tablename__ = 'pokemon_colors'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    name = Column(Unicode(6), nullable=False,
        info=dict(description=u"The English name of the color", official=True, format='identifier'))

class PokemonDexNumber(TableBase):
    u"""The number of a Pokémon in a particular Pokédex (e.g. Jigglypuff is #138 in Hoenn's 'dex)
    """
    __tablename__ = 'pokemon_dex_numbers'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokédex"))
    pokedex_number = Column(Integer, nullable=False,
        info=dict(description=u"Number of the pokémon in that the pokédex"))

class PokemonEggGroup(TableBase):
    u"""Maps an Egg group to a pokémon; each pokémon belongs to one or two egg groups
    """
    __tablename__ = 'pokemon_egg_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    egg_group_id = Column(Integer, ForeignKey('egg_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the egg group"))

class PokemonEvolution(TableBase):
    u"""Specifies what causes a particular pokémon to evolve into another species.
    """
    __tablename__ = 'pokemon_evolution'
    from_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False,
        info=dict(description=u"ID of the pre-evolution species"))
    to_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the post-evolution species"))
    evolution_trigger_id = Column(Integer, ForeignKey('evolution_triggers.id'), nullable=False,
        info=dict(description=u"ID of the trigger type"))
    trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        info=dict(description=u"ID of the item that triggers the evolution in a way defined by evolution_trigger_id"))
    minimum_level = Column(Integer, nullable=True,
        info=dict(description=u"Minimum level, or None if level doean't matter"))
    gender = Column(Enum('male', 'female', name='pokemon_evolution_gender'), nullable=True,
        info=dict(description=u"Required gender, or None if gender doesn't matter"))
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True,
        info=dict(description=u"Required location, or None if it doesn't matter"))
    held_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        info=dict(description=u"An item the pokémon must hold, or None if it doesn't matter"))
    time_of_day = Column(Enum('morning', 'day', 'night', name='pokemon_evolution_time_of_day'), nullable=True,
        info=dict(description=u"Required time of day, or None if it doesn't matter"))
    known_move_id = Column(Integer, ForeignKey('moves.id'), nullable=True,
        info=dict(description=u"ID of a move the pokémon must know, or None if it doesn't matter"))
    minimum_happiness = Column(Integer, nullable=True,
        info=dict(description=u"Minimum tameness value the pokémon must have, or None if it doesn't matter"))
    minimum_beauty = Column(Integer, nullable=True,
        info=dict(description=u"Minimum Beauty value the pokémon must have, or None if it doesn't matter"))
    relative_physical_stats = Column(Integer, nullable=True,
        info=dict(description=u"Relation of Attack and Defense stats the pokémon must have, as sgn(atk-def), or None if that doesn't matter"))
    party_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=True,
        info=dict(description=u"ID of a pokémon that must be present in the party, or None if there's no such condition"))

class PokemonFlavorText(TableBase):
    u"""In-game pokédex descrption of a pokémon.
    """
    __tablename__ = 'pokemon_flavor_text'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the version that has this flavor text"))
    flavor_text = Column(Unicode(255), nullable=False,
        info=dict(description=u"ID of the version that has this flavor text", official=True, format='gametext'))

class PokemonFormGroup(TableBase):
    # XXX: Give the docstring here & check column descriptions
    __tablename__ = 'pokemon_form_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the base form pokémon"))
    is_battle_only = Column(Boolean, nullable=False,
        info=dict(description=u"Set iff the forms only change in battle"))
    description = Column(markdown.MarkdownColumn(1024), nullable=False,
        info=dict(description=u"English description of how the forms work", format='markdown'))

class PokemonFormSprite(TableBase):
    # XXX: Give the docstring here & check column descriptions
    __tablename__ = 'pokemon_form_sprites'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    introduced_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of version group the form was introduced in"))
    name = Column(Unicode(16), nullable=True,
        info=dict(description=u"English name of the form", format='plaintext'))
    is_default = Column(Boolean, nullable=True,
        info=dict(description=u'Set iff the form is the base, normal, usual, or otherwise default form'))

class PokemonHabitat(TableBase):
    u"""The habitat of a pokémon, as given in the FireRed/LeafGreen version pokédex
    """
    __tablename__ = 'pokemon_habitats'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u"The English name of the habitat", official=True, format='plaintext'))

class PokemonInternalID(TableBase):
    u"""The number of a pokémon a game uses internally
    """
    __tablename__ = 'pokemon_internal_ids'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description=u"Database ID of the pokémon"))
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description=u"Database ID of the generation"))
    internal_id = Column(Integer, nullable=False,
        info=dict(description=u"Internal ID the generation's games use for the pokémon"))

class PokemonItem(TableBase):
    u"""Record of an item a pokémon can hold in the wild
    """
    __tablename__ = 'pokemon_items'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the version this applies to"))
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the item"))
    rarity = Column(Integer, nullable=False,
        info=dict(description=u"Chance of the pokémon holding the item, in percent"))

class PokemonMove(TableBase):
    u"""Record of a move a pokémon can learn
    """
    __tablename__ = 'pokemon_moves'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, index=True,
        info=dict(description=u"ID of the pokémon"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, index=True,
        info=dict(description=u"ID of the version group this applies to"))
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False, index=True,
        info=dict(description=u"ID of the move"))
    pokemon_move_method_id = Column(Integer, ForeignKey('pokemon_move_methods.id'), nullable=False, index=True,
        info=dict(description=u"ID of the method this move is learned by"))
    level = Column(Integer, nullable=True, index=True,
        info=dict(description=u"Level the move is learned at, if applicable"))
    order = Column(Integer, nullable=True,
        info=dict(description=u"A sort key to produce the correct ordering when all else is equal"))  # XXX: This needs a better description

    __table_args__ = (
        PrimaryKeyConstraint('pokemon_id', 'version_group_id', 'move_id', 'pokemon_move_method_id', 'level'),
        {},
    )

class PokemonMoveMethod(TableBase):
    u"""A method a move can be learned by, such as "Level up" or "Tutor".
    """
    __tablename__ = 'pokemon_move_methods'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    name = Column(Unicode(64), nullable=False,
        info=dict(description=u"An English name of the method", format='plaintext'))
    description = Column(Unicode(255), nullable=False,
        info=dict(description=u"A detailed description of how the method works", format='plaintext'))

class PokemonName(TableBase):
    u"""A non-English name of a pokémon.
    """
    __tablename__ = 'pokemon_names'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the language"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u"Name of the pokémon in the language", foreign=True, format='plaintext'))

class PokemonShape(TableBase):
    u"""The shape of a pokémon's body, as used in generation IV pokédexes.
    """
    __tablename__ = 'pokemon_shapes'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    name = Column(Unicode(24), nullable=False,
        info=dict(description=u"A boring English name of the body shape", format='plaintext'))
    awesome_name = Column(Unicode(16), nullable=False,
        info=dict(description=u"A splendiferous, technically English, name of the body shape", format='plaintext'))

class PokemonStat(TableBase):
    u"""A stat value of a pokémon
    """
    __tablename__ = 'pokemon_stats'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the stat"))
    base_stat = Column(Integer, nullable=False,
        info=dict(description=u"The base stat"))
    effort = Column(Integer, nullable=False,
        info=dict(description=u"The effort increase in this stat gained when this pokémon is defeated"))

class PokemonType(TableBase):
    u"""Maps a type to a pokémon. Each pokémon has 1 or 2 types.
    """
    __tablename__ = 'pokemon_types'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the pokémon"))
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        info=dict(description=u"ID of the type"))
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The type's slot, 1 or 2, used to sort types if there are two of them"))

class Region(TableBase):
    u"""Major areas of the world: Kanto, Johto, etc.
    """
    __tablename__ = 'regions'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u"The English name of the region", official=True, format='plaintext'))

class Stat(TableBase):
    u"""A Stat, such as Attack or Speed
    """
    __tablename__ = 'stats'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=True,
        info=dict(description=u"For offensive and defensive stats, the damage this stat relates to; otherwise None (the NULL value)"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u"The English name of the stat", official=True, format='plaintext'))

class SuperContestCombo(TableBase):
    u"""Combo of two moves in a Super Contest.
    """
    __tablename__ = 'super_contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the first move"))
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the second and last move"))

class SuperContestEffect(TableBase):
    u"""An effect a move can have when used in the Super Contest
    """
    __tablename__ = 'super_contest_effects'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    appeal = Column(SmallInteger, nullable=False,
        info=dict(description=u"Number of hearts the user will get when executing a move with this effect"))
    flavor_text = Column(Unicode(64), nullable=False,
        info=dict(description=u"An English description of the effect", format='plaintext'))

class TypeEfficacy(TableBase):
    u"""The effectiveness of damage of one type against pokémon of another type
    """
    __tablename__ = 'type_efficacy'
    damage_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the damage type; most commonly this is the same as the attack type"))
    target_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the defending pokémon's type"))
    damage_factor = Column(Integer, nullable=False,
        info=dict(description=u"The effectiveness, in percent"))

class Type(TableBase):
    u"""An elemental type, such as Grass or Steel
    """
    __tablename__ = 'types'
    __singlename__ = 'type'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    name = Column(Unicode(8), nullable=False,
        info=dict(description=u"The English name.", format='plaintext'))  # XXX: Is this official? The games don't spell "Electric" in full...
    abbreviation = Column(Unicode(3), nullable=False,
        info=dict(description=u"An arbitrary 3-letter abbreviation of the type", format='plaintext'))  # XXX: Or is it not arbitrary?
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description=u"ID of the generation this type first appeared in"))
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=False,
        info=dict(description=u"ID of the damage class this type's moves had before generation IV, or None for the ??? type"))

class TypeName(TableBase):
    u"""Non-English name of an elemental type
    """
    __tablename__ = 'type_names'
    type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the type"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the language"))
    name = Column(Unicode(16), nullable=False,
        info=dict(description=u"Name of the type in that language", foreign=True, format='plaintext'))

class VersionGroup(TableBase):
    u"""A group of related game versions
    """
    __tablename__ = 'version_groups'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description=u"ID of the generation the games of this group belong to"))

class VersionGroupRegion(TableBase):
    u"""Maps a region to a game version group that features it
    """
    __tablename__ = 'version_group_regions'
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False,
        info=dict(description=u"ID of the version"))
    region_id = Column(Integer, ForeignKey('regions.id'), primary_key=True, nullable=False,
        info=dict(description=u"ID of the region"))

class Version(TableBase):
    u"""A version of a mainline pokémon game
    """
    __tablename__ = 'versions'
    id = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"A numeric ID"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        info=dict(description=u"ID of the version group this game belongs to"))
    name = Column(Unicode(32), nullable=False,
        info=dict(description=u'The English name of the game, without the "Pokémon" prefix', official=True, format='plaintext'))


### Relations down here, to avoid ordering problems
Ability.flavor_text = relation(AbilityFlavorText, order_by=AbilityFlavorText.version_group_id, backref='ability')
Ability.foreign_names = relation(AbilityName, backref='ability')
Ability.generation = relation(Generation, backref='abilities')

AbilityFlavorText.version_group = relation(VersionGroup)

AbilityName.language = relation(Language)

Berry.berry_firmness = relation(BerryFirmness, backref='berries')
Berry.firmness = association_proxy('berry_firmness', 'name')
Berry.flavors = relation(BerryFlavor, order_by=BerryFlavor.contest_type_id, backref='berry')
Berry.natural_gift_type = relation(Type)

BerryFlavor.contest_type = relation(ContestType)

ContestCombo.first = relation(Move, primaryjoin=ContestCombo.first_move_id==Move.id,
                                    backref='contest_combo_first')
ContestCombo.second = relation(Move, primaryjoin=ContestCombo.second_move_id==Move.id,
                                     backref='contest_combo_second')

Encounter.location_area = relation(LocationArea, backref='encounters')
Encounter.pokemon = relation(Pokemon, backref='encounters')
Encounter.version = relation(Version, backref='encounters')
Encounter.slot = relation(EncounterSlot, backref='encounters')

EncounterConditionValue.condition = relation(EncounterCondition, backref='values')

Encounter.condition_value_map = relation(EncounterConditionValueMap, backref='encounter')
Encounter.condition_values = association_proxy('condition_value_map', 'condition_value')
EncounterConditionValueMap.condition_value = relation(EncounterConditionValue,
                                                      backref='encounter_map')

EncounterSlot.terrain = relation(EncounterTerrain, backref='slots')

EncounterSlot.condition_map = relation(EncounterSlotCondition, backref='slot')
EncounterSlot.conditions = association_proxy('condition_map', 'condition')
EncounterSlotCondition.condition = relation(EncounterCondition,
                                            backref='slot_map')

EvolutionChain.growth_rate = relation(GrowthRate, backref='evolution_chains')
EvolutionChain.baby_trigger_item = relation(Item, backref='evolution_chains')

Experience.growth_rate = relation(GrowthRate, backref='experience_table')

Generation.canonical_pokedex = relation(Pokedex, backref='canonical_for_generation')
Generation.versions = relation(Version, secondary=VersionGroup.__table__)
Generation.main_region = relation(Region)

GrowthRate.max_experience_obj = relation(Experience, primaryjoin=and_(Experience.growth_rate_id == GrowthRate.id, Experience.level == 100), uselist=False)
GrowthRate.max_experience = association_proxy('max_experience_obj', 'experience')

Item.berry = relation(Berry, uselist=False, backref='item')
Item.flags = relation(ItemFlag, secondary=ItemFlagMap.__table__)
Item.flavor_text = relation(ItemFlavorText, order_by=ItemFlavorText.version_group_id.asc(), backref='item')
Item.fling_effect = relation(ItemFlingEffect, backref='items')
Item.foreign_names = relation(ItemName, backref='item')
Item.machines = relation(Machine, order_by=Machine.version_group_id.asc())
Item.category = relation(ItemCategory)
Item.pocket = association_proxy('category', 'pocket')

ItemCategory.items = relation(Item, order_by=Item.name)
ItemCategory.pocket = relation(ItemPocket)

ItemFlavorText.version_group = relation(VersionGroup)

ItemInternalID.item = relation(Item, backref='internal_ids')
ItemInternalID.generation = relation(Generation)

ItemName.language = relation(Language)

ItemPocket.categories = relation(ItemCategory, order_by=ItemCategory.name)

Location.region = relation(Region, backref='locations')

LocationArea.location = relation(Location, backref='areas')

LocationInternalID.location = relation(Location, backref='internal_ids')
LocationInternalID.generation = relation(Generation)

Machine.item = relation(Item)
Machine.version_group = relation(VersionGroup)

Move.contest_effect = relation(ContestEffect, backref='moves')
Move.contest_combo_next = association_proxy('contest_combo_first', 'second')
Move.contest_combo_prev = association_proxy('contest_combo_second', 'first')
Move.contest_type = relation(ContestType, backref='moves')
Move.damage_class = relation(MoveDamageClass, backref='moves')
Move.flags = association_proxy('move_flags', 'flag')
Move.flavor_text = relation(MoveFlavorText, order_by=MoveFlavorText.version_group_id, backref='move')
Move.foreign_names = relation(MoveName, backref='move')
Move.generation = relation(Generation, backref='moves')
Move.machines = relation(Machine, backref='move')
Move.move_effect = relation(MoveEffect, backref='moves')
Move.move_flags = relation(MoveFlag, backref='move')
Move.super_contest_effect = relation(SuperContestEffect, backref='moves')
Move.super_contest_combo_next = association_proxy('super_contest_combo_first', 'second')
Move.super_contest_combo_prev = association_proxy('super_contest_combo_second', 'first')
Move.target = relation(MoveTarget, backref='moves')
Move.type = relation(Type, backref='moves')

Move.effect = markdown.MoveEffectProperty('effect')
Move.short_effect = markdown.MoveEffectProperty('short_effect')

MoveEffect.category_map = relation(MoveEffectCategoryMap)
MoveEffect.categories = association_proxy('category_map', 'category')
MoveEffectCategoryMap.category = relation(MoveEffectCategory)

MoveFlag.flag = relation(MoveFlagType)

MoveFlavorText.version_group = relation(VersionGroup)

MoveName.language = relation(Language)

Nature.foreign_names = relation(NatureName, backref='nature')
Nature.decreased_stat = relation(Stat, primaryjoin=Nature.decreased_stat_id==Stat.id,
                                       backref='decreasing_natures')
Nature.increased_stat = relation(Stat, primaryjoin=Nature.increased_stat_id==Stat.id,
                                       backref='increasing_natures')
Nature.hates_flavor = relation(ContestType, primaryjoin=Nature.hates_flavor_id==ContestType.id,
                                       backref='hating_natures')
Nature.likes_flavor = relation(ContestType, primaryjoin=Nature.likes_flavor_id==ContestType.id,
                                       backref='liking_natures')
Nature.battle_style_preferences = relation(NatureBattleStylePreference,
                                           order_by=NatureBattleStylePreference.move_battle_style_id,
                                           backref='nature')
Nature.pokeathlon_effects = relation(NaturePokeathlonStat, order_by=NaturePokeathlonStat.pokeathlon_stat_id)

NatureBattleStylePreference.battle_style = relation(MoveBattleStyle, backref='nature_preferences')

NatureName.language = relation(Language)

NaturePokeathlonStat.pokeathlon_stat = relation(PokeathlonStat, backref='nature_effects')

Pokedex.region = relation(Region, backref='pokedexes')
Pokedex.version_groups = relation(VersionGroup, secondary=PokedexVersionGroup.__table__, backref='pokedexes')

Pokemon.abilities = relation(Ability, secondary=PokemonAbility.__table__,
                                      order_by=PokemonAbility.slot,
                                      backref='pokemon')
Pokemon.formes = relation(Pokemon, primaryjoin=Pokemon.id==Pokemon.forme_base_pokemon_id,
                                               backref=backref('forme_base_pokemon',
                                                               remote_side=[Pokemon.id]))
Pokemon.pokemon_color = relation(PokemonColor, backref='pokemon')
Pokemon.color = association_proxy('pokemon_color', 'name')
Pokemon.dex_numbers = relation(PokemonDexNumber, order_by=PokemonDexNumber.pokedex_id.asc(), backref='pokemon')
Pokemon.default_form_sprite = relation(PokemonFormSprite,
                                       primaryjoin=and_(
                                            Pokemon.id==PokemonFormSprite.pokemon_id,
                                            PokemonFormSprite.is_default==True,
                                       ),
                                       uselist=False)
Pokemon.egg_groups = relation(EggGroup, secondary=PokemonEggGroup.__table__,
                                        order_by=PokemonEggGroup.egg_group_id,
                                        backref='pokemon')
Pokemon.evolution_chain = relation(EvolutionChain, backref='pokemon')
Pokemon.child_pokemon = relation(Pokemon,
    primaryjoin=Pokemon.id==PokemonEvolution.from_pokemon_id,
    secondary=PokemonEvolution.__table__,
    secondaryjoin=PokemonEvolution.to_pokemon_id==Pokemon.id,
    backref=backref('parent_pokemon', uselist=False),
)
Pokemon.flavor_text = relation(PokemonFlavorText, order_by=PokemonFlavorText.version_id.asc(), backref='pokemon')
Pokemon.foreign_names = relation(PokemonName, backref='pokemon')
Pokemon.pokemon_habitat = relation(PokemonHabitat, backref='pokemon')
Pokemon.habitat = association_proxy('pokemon_habitat', 'name')
Pokemon.items = relation(PokemonItem, backref='pokemon')
Pokemon.generation = relation(Generation, backref='pokemon')
Pokemon.shape = relation(PokemonShape, backref='pokemon')
Pokemon.stats = relation(PokemonStat, backref='pokemon', order_by=PokemonStat.stat_id.asc())
Pokemon.types = relation(Type, secondary=PokemonType.__table__, order_by=PokemonType.slot.asc())

PokemonDexNumber.pokedex = relation(Pokedex)

PokemonEvolution.from_pokemon = relation(Pokemon,
    primaryjoin=PokemonEvolution.from_pokemon_id==Pokemon.id,
    backref='child_evolutions',
)
PokemonEvolution.to_pokemon = relation(Pokemon,
    primaryjoin=PokemonEvolution.to_pokemon_id==Pokemon.id,
    backref=backref('parent_evolution', uselist=False),
)
PokemonEvolution.child_evolutions = relation(PokemonEvolution,
    primaryjoin=PokemonEvolution.from_pokemon_id==PokemonEvolution.to_pokemon_id,
    foreign_keys=[PokemonEvolution.to_pokemon_id],
    backref=backref('parent_evolution',
        remote_side=[PokemonEvolution.from_pokemon_id],
        uselist=False,
    ),
)
PokemonEvolution.trigger = relation(EvolutionTrigger, backref='evolutions')
PokemonEvolution.trigger_item = relation(Item,
    primaryjoin=PokemonEvolution.trigger_item_id==Item.id,
    backref='triggered_evolutions',
)
PokemonEvolution.held_item = relation(Item,
    primaryjoin=PokemonEvolution.held_item_id==Item.id,
    backref='required_for_evolutions',
)
PokemonEvolution.location = relation(Location, backref='triggered_evolutions')
PokemonEvolution.known_move = relation(Move, backref='triggered_evolutions')
PokemonEvolution.party_pokemon = relation(Pokemon,
    primaryjoin=PokemonEvolution.party_pokemon_id==Pokemon.id,
    backref='triggered_evolutions',
)

PokemonFlavorText.version = relation(Version)

PokemonItem.item = relation(Item, backref='pokemon')
PokemonItem.version = relation(Version)

PokemonFormGroup.pokemon = relation(Pokemon, backref=backref('form_group',
                                                             uselist=False))
PokemonFormSprite.pokemon = relation(Pokemon, backref='form_sprites')
PokemonFormSprite.introduced_in = relation(VersionGroup)

PokemonMove.pokemon = relation(Pokemon, backref='pokemon_moves')
PokemonMove.version_group = relation(VersionGroup)
PokemonMove.machine = relation(Machine, backref='pokemon_moves',
                               primaryjoin=and_(Machine.version_group_id==PokemonMove.version_group_id,
                                                Machine.move_id==PokemonMove.move_id),
                                foreign_keys=[Machine.version_group_id, Machine.move_id],
                                uselist=False)
PokemonMove.move = relation(Move, backref='pokemon_moves')
PokemonMove.method = relation(PokemonMoveMethod)

PokemonName.language = relation(Language)

PokemonStat.stat = relation(Stat)

# This is technically a has-many; Generation.main_region_id -> Region.id
Region.generation = relation(Generation, uselist=False)
Region.version_group_regions = relation(VersionGroupRegion, backref='region',
                                        order_by='VersionGroupRegion.version_group_id')
Region.version_groups = association_proxy('version_group_regions', 'version_group')

Stat.damage_class = relation(MoveDamageClass, backref='stats')

SuperContestCombo.first = relation(Move, primaryjoin=SuperContestCombo.first_move_id==Move.id,
                                        backref='super_contest_combo_first')
SuperContestCombo.second = relation(Move, primaryjoin=SuperContestCombo.second_move_id==Move.id,
                                         backref='super_contest_combo_second')

Type.damage_efficacies = relation(TypeEfficacy,
                                  primaryjoin=Type.id
                                      ==TypeEfficacy.damage_type_id,
                                  backref='damage_type')
Type.target_efficacies = relation(TypeEfficacy,
                                  primaryjoin=Type.id
                                      ==TypeEfficacy.target_type_id,
                                  backref='target_type')

Type.generation = relation(Generation, backref='types')
Type.damage_class = relation(MoveDamageClass, backref='types')
Type.foreign_names = relation(TypeName, backref='type')

TypeName.language = relation(Language)

Version.version_group = relation(VersionGroup, backref='versions')
Version.generation = association_proxy('version_group', 'generation')

VersionGroup.generation = relation(Generation, backref='version_groups')
VersionGroup.version_group_regions = relation(VersionGroupRegion, backref='version_group')
VersionGroup.regions = association_proxy('version_group_regions', 'region')
