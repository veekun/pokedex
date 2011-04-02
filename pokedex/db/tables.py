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
- ripped: True for text that has been ripped from the games, and can be ripped
  again for new versions or languages

See `pokedex.db.multilang` for how localizable text columns work.  The session
classes in that module can be used to change the default language.
"""
# XXX: Check if "gametext" is set correctly everywhere

import collections
from functools import partial

from sqlalchemy import Column, ForeignKey, MetaData, PrimaryKeyConstraint, Table, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relation
from sqlalchemy.orm.session import Session
from sqlalchemy.orm.interfaces import AttributeExtension
from sqlalchemy.sql import and_
from sqlalchemy.schema import ColumnDefault
from sqlalchemy.types import *

from pokedex.db import markdown, multilang

class TableSuperclass(object):
    """Superclass for declarative tables, to give them some generic niceties
    like stringification.
    """
    def __unicode__(self):
        """Be as useful as possible.  Show the primary key, and an identifier
        if we've got one.
        """
        typename = u'.'.join((__name__, type(self).__name__))

        pk_constraint = self.__table__.primary_key
        if not pk_constraint:
            return u"<%s object at %x>" % (typename, id(self))

        pk = u', '.join(unicode(getattr(self, column.name))
            for column in pk_constraint.columns)
        try:
            return u"<%s object (%s): %s>" % (typename, pk, self.identifier)
        except AttributeError:
            return u"<%s object (%s)>" % (typename, pk)

    def __str__(self):
        return unicode(self).encode('utf8')

mapped_classes = []
class TableMetaclass(DeclarativeMeta):
    def __init__(cls, name, bases, attrs):
        super(TableMetaclass, cls).__init__(name, bases, attrs)
        if hasattr(cls, '__tablename__'):
            mapped_classes.append(cls)
            cls.translation_classes = []

metadata = MetaData()
TableBase = declarative_base(metadata=metadata, cls=TableSuperclass, metaclass=TableMetaclass)


### Need Language first, to create the partial() below

class Language(TableBase):
    u"""A language the Pokémon games have been translated into
    """
    __tablename__ = 'languages'
    __singlename__ = 'language'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    iso639 = Column(Unicode(2), nullable=False,
        info=dict(description="The two-letter code of the country where this language is spoken. Note that it is not unique.", format='identifier'))
    iso3166 = Column(Unicode(2), nullable=False,
        info=dict(description="The two-letter code of the language. Note that it is not unique.", format='identifier'))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    official = Column(Boolean, nullable=False, index=True,
        info=dict(description=u"True iff games are produced in the language."))
    order = Column(Integer, nullable=True,
        info=dict(description=u"Order for sorting in foreign name lists."))

create_translation_table = partial(multilang.create_translation_table, language_class=Language)

create_translation_table('language_names', Language, 'names',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

### The actual tables

class Ability(TableBase):
    u"""An ability a Pokémon can have, such as Static or Pressure.
    """
    __tablename__ = 'abilities'
    __singlename__ = 'ability'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="This ability's unique ID; matches the games' internal ID"))
    identifier = Column(Unicode(24), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description="The ID of the generation this ability was introduced in", detail=True))

create_translation_table('ability_names', Ability, 'names',
    relation_lazy='joined',
    name = Column(Unicode(24), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True, ripped=True)),
)
create_translation_table('ability_prose', Ability, 'prose',
    effect = Column(markdown.MarkdownColumn(5120), nullable=False,
        info=dict(description="A detailed description of this ability's effect", format='markdown')),
    short_effect = Column(markdown.MarkdownColumn(255), nullable=False,
        info=dict(description="A short summary of this ability's effect", format='markdown')),
)

class AbilityChangelog(TableBase):
    """History of changes to abilities across main game versions."""
    __tablename__ = 'ability_changelog'
    __singlename__ = 'ability_changelog'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="This change's unique ID"))
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False,
        info=dict(description="The ID of the ability that changed"))
    changed_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        info=dict(description="The ID of the version group in which the ability changed"))

create_translation_table('ability_changelog_prose', AbilityChangelog, 'prose',
    effect = Column(markdown.MarkdownColumn(255), nullable=False,
        info=dict(description="A description of the old behavior", format='markdown'))
)

class AbilityFlavorText(TableBase):
    u"""In-game flavor text of an ability
    """
    __tablename__ = 'ability_flavor_text'
    ability_id = Column(Integer, ForeignKey('abilities.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the ability"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the version group this flavor text is taken from"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The language"))
    flavor_text = Column(Unicode(64), nullable=False,
        info=dict(description="The actual flavor text", official=True, format='gametext'))

class Berry(TableBase):
    u"""A Berry, consumable item that grows on trees

    For data common to all items, such as the name, see the corresponding item entry.
    """
    __tablename__ = 'berries'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="This Berry's in-game number"))
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False,
        info=dict(description="The ID of the item that represents this Berry"))
    firmness_id = Column(Integer, ForeignKey('berry_firmness.id'), nullable=False,
        info=dict(description="The ID of this Berry's firmness category"))
    natural_gift_power = Column(Integer, nullable=True,
        info=dict(description="Natural Gift's power when used with this Berry"))
    natural_gift_type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        info=dict(description="The ID of the Type that Natural Gift has when used with this Berry"))
    size = Column(Integer, nullable=False,
        info=dict(description=u"The size of this Berry, in millimeters"))
    max_harvest = Column(Integer, nullable=False,
        info=dict(description="The maximum number of these berries that can grow on one tree in Generation IV"))
    growth_time = Column(Integer, nullable=False,
        info=dict(description="Time it takes the tree to grow one stage, in hours.  Berry trees go through four of these growth stages before they can be picked."))
    soil_dryness = Column(Integer, nullable=False,
        info=dict(description="The speed at which this Berry dries out the soil as it grows.  A higher rate means the soil dries more quickly."))
    smoothness = Column(Integer, nullable=False,
        info=dict(description="The smoothness of this Berry, used in making Pokéblocks or Poffins"))

class BerryFirmness(TableBase):
    u"""A Berry firmness, such as "hard" or "very soft".
    """
    __tablename__ = 'berry_firmness'
    __singlename__ = 'berry_firmness'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this firmness"))
    identifier = Column(Unicode(10), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('berry_firmness_names', BerryFirmness, 'names',
    relation_lazy='joined',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class BerryFlavor(TableBase):
    u"""A Berry flavor level.
    """
    __tablename__ = 'berry_flavors'
    berry_id = Column(Integer, ForeignKey('berries.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the berry"))
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the flavor"))
    flavor = Column(Integer, nullable=False,
        info=dict(description="The level of the flavor in the berry"))

class ContestCombo(TableBase):
    u"""Combo of two moves in a Contest.
    """
    __tablename__ = 'contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the first move in the combo"))
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the second and final move in the combo"))

class ContestEffect(TableBase):
    u"""Effect of a move when used in a Contest.
    """
    __tablename__ = 'contest_effects'
    __singlename__ = 'contest_effect'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this effect"))
    appeal = Column(SmallInteger, nullable=False,
        info=dict(description="The base number of hearts the user of this move gets"))
    jam = Column(SmallInteger, nullable=False,
        info=dict(description="The base number of hearts the user's opponent loses"))

create_translation_table('contest_effect_prose', ContestEffect, 'prose',
    flavor_text = Column(Unicode(64), nullable=False,
        info=dict(description="The in-game description of this effect", official=True, format='gametext')),
    effect = Column(Unicode(255), nullable=False,
        info=dict(description="A detailed description of the effect", format='plaintext')),
)

class ContestType(TableBase):
    u"""A Contest type, such as "cool" or "smart", and their associated Berry flavors and Pokéblock colors.
    """
    __tablename__ = 'contest_types'
    __singlename__ = 'contest_type'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this Contest type"))
    identifier = Column(Unicode(6), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('contest_type_names', ContestType, 'names',
    relation_lazy='joined',
    name = Column(Unicode(6), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
    flavor = Column(Unicode(6), nullable=False,
        info=dict(description="The name of the corresponding Berry flavor", official=True, format='plaintext')),
    color = Column(Unicode(6), nullable=False,
        info=dict(description=u"The name of the corresponding Pokéblock color", official=True, format='plaintext')),
)

class EggGroup(TableBase):
    u"""An Egg group. Usually, two Pokémon can breed if they share an Egg Group.

    (exceptions are the Ditto and No Eggs groups)
    """
    __tablename__ = 'egg_groups'
    __singlename__ = 'egg_group'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this group"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description=u"An identifier.", format='identifier'))

create_translation_table('egg_group_prose', EggGroup, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

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
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this encounter"))
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the version this applies to"))
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the location of this encounter"))
    encounter_slot_id = Column(Integer, ForeignKey('encounter_slots.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter slot, which determines terrain and rarity"))
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the encountered Pokémon"))
    min_level = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u"The minimum level of the encountered Pokémon"))
    max_level = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u"The maxmum level of the encountered Pokémon"))

class EncounterCondition(TableBase):
    u"""A conditions in the game world that affects Pokémon encounters, such as time of day.
    """

    __tablename__ = 'encounter_conditions'
    __singlename__ = 'encounter_condition'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this condition"))
    identifier = Column(Unicode(64), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('encounter_condition_prose', EncounterCondition, 'prose',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class EncounterConditionValue(TableBase):
    u"""A possible state for a condition; for example, the state of 'swarm' could be 'swarm' or 'no swarm'.
    """

    __tablename__ = 'encounter_condition_values'
    __singlename__ = 'encounter_condition_value'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), primary_key=False, nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter condition this is a value of"))
    identifier = Column(Unicode(64), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    is_default = Column(Boolean, nullable=False,
        info=dict(description='Set if this value is the default state for the condition'))

create_translation_table('encounter_condition_value_prose', EncounterConditionValue, 'prose',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class EncounterConditionValueMap(TableBase):
    u"""Maps encounters to the specific conditions under which they occur.
    """
    __tablename__ = 'encounter_condition_value_map'
    encounter_id = Column(Integer, ForeignKey('encounters.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter"))
    encounter_condition_value_id = Column(Integer, ForeignKey('encounter_condition_values.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The ID of the encounter condition value"))

class EncounterSlot(TableBase):
    u"""An abstract "slot" within a terrain, associated with both some set of conditions and a rarity.

    Note that there are two encounters per slot, so the rarities will only add
    up to 50.
    """

    __tablename__ = 'encounter_slots'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for this slot"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, autoincrement=False,
        info=dict(description="The ID of the version group this slot is in"))
    encounter_terrain_id = Column(Integer, ForeignKey('encounter_terrain.id'), primary_key=False, nullable=False, autoincrement=False,
        info=dict(description="The ID of the terrain"))
    slot = Column(Integer, nullable=True,
        info=dict(description="This slot's order for the location and terrain"))
    rarity = Column(Integer, nullable=False,
        info=dict(description="The chance of the encounter as a percentage"))

class EncounterTerrain(TableBase):
    u"""A way the player can enter a wild encounter, e.g., surfing, fishing, or walking through tall grass.
    """

    __tablename__ = 'encounter_terrain'
    __singlename__ = __tablename__
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A unique ID for the terrain"))
    identifier = Column(Unicode(64), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('encounter_terrain_prose', EncounterTerrain, 'prose',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class EvolutionChain(TableBase):
    u"""A family of Pokémon that are linked by evolution
    """
    __tablename__ = 'evolution_chains'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), nullable=False,
        info=dict(description="ID of the growth rate for this family"))
    baby_trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        info=dict(description="Item that a parent must hold while breeding to produce a baby"))

class EvolutionTrigger(TableBase):
    u"""An evolution type, such as "level" or "trade".
    """
    __tablename__ = 'evolution_triggers'
    __singlename__ = 'evolution_trigger'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('evolution_trigger_prose', EvolutionTrigger, 'prose',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class Experience(TableBase):
    u"""EXP needed for a certain level with a certain growth rate
    """
    __tablename__ = 'experience'
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the growth rate"))
    level = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The level"))
    experience = Column(Integer, nullable=False,
        info=dict(description="The number of EXP points needed to get to that level"))

class Generation(TableBase):
    u"""A Generation of the Pokémon franchise
    """
    __tablename__ = 'generations'
    __singlename__ = 'generation'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    main_region_id = Column(Integer, ForeignKey('regions.id'),
        info=dict(description="ID of the region this generation's main games take place in"))
    canonical_pokedex_id = Column(Integer, ForeignKey('pokedexes.id'),
        info=dict(description=u"ID of the Pokédex this generation's main games use by default"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description=u'An identifier', format='identifier'))

create_translation_table('generation_names', Generation, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class GrowthRate(TableBase):
    u"""Growth rate of a Pokémon, i.e. the EXP → level function.
    """
    __tablename__ = 'growth_rates'
    __singlename__ = 'growth_rate'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(20), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    formula = Column(Unicode(500), nullable=False,
        info=dict(description="The formula", format='latex'))

create_translation_table('growth_rate_prose', GrowthRate, 'prose',
    name = Column(Unicode(20), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class Item(TableBase):
    u"""An Item from the games, like "Poké Ball" or "Bicycle".
    """
    __tablename__ = 'items'
    __singlename__ = 'item'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(20), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    category_id = Column(Integer, ForeignKey('item_categories.id'), nullable=False,
        info=dict(description="ID of a category this item belongs to"))
    cost = Column(Integer, nullable=False,
        info=dict(description=u"Cost of the item when bought. Items sell for half this price."))
    fling_power = Column(Integer, nullable=True,
        info=dict(description=u"Power of the move Fling when used with this item."))
    fling_effect_id = Column(Integer, ForeignKey('item_fling_effects.id'), nullable=True,
        info=dict(description=u"ID of the fling-effect of the move Fling when used with this item. Note that these are different from move effects."))

    @property
    def appears_underground(self):
        u"""True if the item appears underground, as specified by the appropriate flag
        """
        return any(flag.identifier == u'underground' for flag in self.flags)

create_translation_table('item_names', Item, 'names',
    relation_lazy='joined',
    name = Column(Unicode(20), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True, ripped=True)),
)
create_translation_table('item_prose', Item, 'prose',
    short_effect = Column(Unicode(256), nullable=False,
        info=dict(description="A short summary of the effect", format='plaintext')),
    effect = Column(markdown.MarkdownColumn(5120), nullable=False,
        info=dict(description=u"Detailed description of the item's effect.", format='markdown')),
)
create_translation_table('item_flavor_summaries', Item, 'flavor_summaries',
    flavor_summary = Column(Unicode(512), nullable=True,
        info=dict(description=u"Text containing facts from all flavor texts, for languages without official game translations", official=False, format='plaintext', ripped=True)),
)

class ItemCategory(TableBase):
    u"""An item category
    """
    # XXX: This is fanon, right?
    __tablename__ = 'item_categories'
    __singlename__ = 'item_category'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    pocket_id = Column(Integer, ForeignKey('item_pockets.id'), nullable=False,
        info=dict(description="ID of the pocket these items go to"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('item_category_prose', ItemCategory, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class ItemFlag(TableBase):
    u"""An item attribute such as "consumable" or "holdable".
    """
    __tablename__ = 'item_flags'
    __singlename__ = 'item_flag'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(24), nullable=False,
        info=dict(description="Identifier of the flag", format='identifier'))

create_translation_table('item_flag_prose', ItemFlag, 'prose',
    name = Column(Unicode(24), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    description = Column(Unicode(64), nullable=False,
        info=dict(description="Short description of the flag", format='plaintext')),
)

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
    __singlename__ = 'item_flavor_text'
    summary_column = Item.flavor_summaries_table, 'flavor_summary'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="The ID of the item"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="ID of the version group that sports this text"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The language"))
    flavor_text = Column(Unicode(255), nullable=False,
        info=dict(description="The flavor text itself", official=True, format='gametext'))

class ItemFlingEffect(TableBase):
    u"""An effect of the move Fling when used with a specific item
    """
    __tablename__ = 'item_fling_effects'
    __singlename__ = 'item_fling_effect'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))

create_translation_table('item_fling_effect_prose', ItemFlingEffect, 'prose',
    effect = Column(Unicode(255), nullable=False,
        info=dict(description="Description of the effect", format='plaintext')),
)

class ItemGameIndex(TableBase):
    u"""The internal ID number a game uses for an item
    """
    __tablename__ = 'item_game_indices'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="The database ID of the item"))
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description="ID of the generation of games"))
    game_index = Column(Integer, nullable=False,
        info=dict(description="Internal ID of the item in the generation"))

class ItemPocket(TableBase):
    u"""A pocket that categorizes items
    """
    __tablename__ = 'item_pockets'
    __singlename__ = 'item_pocket'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An identifier of this pocket", format='identifier'))

create_translation_table('item_pocket_names', ItemPocket, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class Location(TableBase):
    u"""A place in the Pokémon world
    """
    __tablename__ = 'locations'
    __singlename__ = 'location'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    region_id = Column(Integer, ForeignKey('regions.id'),
        info=dict(description="ID of the region this location is in"))
    identifier = Column(Unicode(64), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('location_names', Location, 'names',
    relation_lazy='joined',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class LocationArea(TableBase):
    u"""A sub-area of a location
    """
    __tablename__ = 'location_areas'
    __singlename__ = 'location_area'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False,
        info=dict(description="ID of the location this area is part of"))
    game_index = Column(Integer, nullable=False,
        info=dict(description="ID the games ude for this area"))
    identifier = Column(Unicode(64), nullable=True,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('location_area_prose', LocationArea, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

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

class LocationGameIndex(TableBase):
    u"""IDs the games use internally for locations
    """
    __tablename__ = 'location_game_indices'
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False, primary_key=True, autoincrement=False,
        info=dict(description="Database ID of the locaion"))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False, primary_key=True, autoincrement=False,
        info=dict(description="ID of the generation this entry to"))
    game_index = Column(Integer, nullable=False,
        info=dict(description="Internal game ID of the location"))

class Machine(TableBase):
    u"""A TM or HM; numbered item that can teach a move to a Pokémon
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

class Move(TableBase):
    u"""A Move: technique or attack a Pokémon can learn to use
    """
    __tablename__ = 'moves'
    __singlename__ = 'move'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(24), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description="ID of the generation this move first appeared in"))
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        info=dict(description="ID of the move's elemental type"))
    power = Column(SmallInteger, nullable=False,
        info=dict(description="Base power of the move"))
    pp = Column(SmallInteger, nullable=True,
        info=dict(description="Base PP (Power Points) of the move, nullable if not applicable (e.g. Struggle and Shadow moves)."))
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
    effect_chance = Column(Integer, nullable=True,
        info=dict(description="The chance for a secondary effect. What this is a chance of is specified by the move's effect."))
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), nullable=True,
        info=dict(description="ID of the move's Contest type (e.g. cool or smart)"))
    contest_effect_id = Column(Integer, ForeignKey('contest_effects.id'), nullable=True,
        info=dict(description="ID of the move's Contest effect"))
    super_contest_effect_id = Column(Integer, ForeignKey('super_contest_effects.id'), nullable=True,
        info=dict(description="ID of the move's Super Contest effect"))

create_translation_table('move_names', Move, 'names',
    relation_lazy='joined',
    name = Column(Unicode(24), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True, ripped=True))
)
create_translation_table('move_flavor_summaries', Move, 'flavor_summaries',
    flavor_summary = Column(Unicode(512), nullable=True,
        info=dict(description=u"Text containing facts from all flavor texts, for languages without official game translations", official=False, format='plaintext', ripped=True)),
)

class MoveBattleStyle(TableBase):
    u"""A battle style of a move"""  # XXX: Explain better
    __tablename__ = 'move_battle_styles'
    __singlename__ = 'move_battle_style'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(8), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('move_battle_style_prose', MoveBattleStyle, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(8), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class MoveChangelog(TableBase):
    """History of changes to moves across main game versions."""
    __tablename__ = 'move_changelog'
    __singlename__ = 'move_changelog'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move that changed"))
    changed_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the version group in which the move changed"))
    type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        info=dict(description="Prior type of the move, or NULL if unchanged"))
    power = Column(SmallInteger, nullable=True,
        info=dict(description="Prior base power of the move, or NULL if unchanged"))
    pp = Column(SmallInteger, nullable=True,
        info=dict(description="Prior base PP of the move, or NULL if unchanged"))
    accuracy = Column(SmallInteger, nullable=True,
        info=dict(description="Prior accuracy of the move, or NULL if unchanged"))
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=True,
        info=dict(description="Prior ID of the effect, or NULL if unchanged"))
    effect_chance = Column(Integer, nullable=True,
        info=dict(description="Prior effect chance, or NULL if unchanged"))

class MoveDamageClass(TableBase):
    u"""Any of the damage classes moves can have, i.e. physical, special, or non-damaging.
    """
    __tablename__ = 'move_damage_classes'
    __singlename__ = 'move_damage_class'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('move_damage_class_prose', MoveDamageClass, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    description = Column(Unicode(64), nullable=False,
        info=dict(description="A description of the class", format='plaintext')),
)

class MoveEffect(TableBase):
    u"""An effect of a move
    """
    __tablename__ = 'move_effects'
    __singlename__ = 'move_effect'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))

create_translation_table('move_effect_prose', MoveEffect, 'prose',
    short_effect = Column(Unicode(256), nullable=False,
        info=dict(description="A short summary of the effect", format='plaintext')),
    effect = Column(Unicode(5120), nullable=False,
        info=dict(description="A detailed description of the effect", format='plaintext')),
)

class MoveEffectCategory(TableBase):
    u"""Category of a move effect
    """
    __tablename__ = 'move_effect_categories'
    __singlename__ = 'move_effect_category'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(64), nullable=False,
        info=dict(description="An identifier", format='identifier'))
    can_affect_user = Column(Boolean, nullable=False,
        info=dict(description="Set if the user can be affected"))

create_translation_table('move_effect_category_prose', MoveEffectCategory, 'prose',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
)

class MoveEffectCategoryMap(TableBase):
    u"""Maps a move effect category to a move effect
    """
    __tablename__ = 'move_effect_category_map'
    move_effect_id = Column(Integer, ForeignKey('move_effects.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move effect"))
    move_effect_category_id = Column(Integer, ForeignKey('move_effect_categories.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the category"))
    affects_user = Column(Boolean, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="Set if the user is affected"))

class MoveEffectChangelog(TableBase):
    """History of changes to move effects across main game versions."""
    __tablename__ = 'move_effect_changelog'
    __singlename__ = 'move_effect_changelog'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=False,
        info=dict(description="The ID of the effect that changed"))
    changed_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        info=dict(description="The ID of the version group in which the effect changed"))

    __table_args__ = (
        UniqueConstraint(effect_id, changed_in_version_group_id),
        {},
    )

create_translation_table('move_effect_changelog_prose', MoveEffectChangelog, 'prose',
    effect = Column(markdown.MarkdownColumn(512), nullable=False,
        info=dict(description="A description of the old behavior", format='markdown')),
)

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
    __singlename__ = 'move_flag_type'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(32), nullable=False,
        info=dict(description="A short identifier for the flag", format='identifier'))

create_translation_table('move_flag_type_prose', MoveFlagType, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    description = Column(markdown.MarkdownColumn(128), nullable=False,
        info=dict(description="A short description of the flag", format='markdown')),
)

class MoveFlavorText(TableBase):
    u"""In-game description of a move
    """
    __tablename__ = 'move_flavor_text'
    summary_column = Move.flavor_summaries_table, 'flavor_summary'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move"))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the version group this text appears in"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The language"))
    flavor_text = Column(Unicode(255), nullable=False,
        info=dict(description="The flavor text", official=True, format='gametext'))

class MoveMeta(TableBase):
    u"""Metadata for move effects, sorta-kinda ripped straight from the game"""
    __tablename__ = 'move_meta'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    meta_category_id = Column(Integer, ForeignKey('move_meta_categories.id'), nullable=False,
        info=dict(description="ID of the move category"))
    meta_ailment_id = Column(Integer, ForeignKey('move_meta_ailments.id'), nullable=False,
        info=dict(description="ID of the caused ailment"))
    min_hits = Column(Integer, nullable=True, index=True,
        info=dict(description="Minimum number of hits per use"))
    max_hits = Column(Integer, nullable=True, index=True,
        info=dict(description="Maximum number of hits per use"))
    min_turns = Column(Integer, nullable=True, index=True,
        info=dict(description="Minimum number of turns the user is forced to use the move"))
    max_turns = Column(Integer, nullable=True, index=True,
        info=dict(description="Maximum number of turns the user is forced to use the move"))
    recoil = Column(Integer, nullable=False, index=True,
        info=dict(description="Recoil damage, in percent of damage done"))
    healing = Column(Integer, nullable=False, index=True,
        info=dict(description="Healing, in percent of user's max HP"))
    crit_rate = Column(Integer, nullable=False, index=True,
        info=dict(description="Critical hit rate bonus"))
    ailment_chance = Column(Integer, nullable=False, index=True,
        info=dict(description="Chance to cause an ailment, in percent"))
    flinch_chance = Column(Integer, nullable=False, index=True,
        info=dict(description="Chance to cause flinching, in percent"))
    stat_chance = Column(Integer, nullable=False, index=True,
        info=dict(description="Chance to cause a stat change, in percent"))

class MoveMetaAilment(TableBase):
    u"""Common status ailments moves can inflict on a single Pokémon, including
    major ailments like paralysis and minor ailments like trapping.
    """
    __tablename__ = 'move_meta_ailments'
    __singlename__ = 'move_meta_ailment'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(24), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('move_meta_ailment_names', MoveMetaAilment, 'names',
    relation_lazy='joined',
    name = Column(Unicode(24), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class MoveMetaCategory(TableBase):
    u"""Very general categories that loosely group move effects."""
    __tablename__ = 'move_meta_categories'
    __singlename__ = 'move_meta_category'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))

create_translation_table('move_meta_category_prose', MoveMetaCategory, 'prose',
    relation_lazy='joined',
    description = Column(Unicode(64), nullable=False,
        info=dict(description="A description of the category", format="plaintext", official=False)),
)

class MoveMetaStatChange(TableBase):
    u"""Stat changes moves (may) make."""
    __tablename__ = 'move_meta_stat_changes'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the move"))
    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the stat"))
    change = Column(Integer, nullable=False, index=True,
        info=dict(description="Amount of increase/decrease, in stages"))

class MoveTarget(TableBase):
    u"""Targetting or "range" of a move, e.g. "Affects all opponents" or "Affects user".
    """
    __tablename__ = 'move_targets'
    __singlename__ = 'move_target'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(32), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('move_target_prose', MoveTarget, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    description = Column(Unicode(128), nullable=False,
        info=dict(description="A description", format='plaintext')),
)

class Nature(TableBase):
    u"""A nature a Pokémon can have, such as Calm or Brave
    """
    __tablename__ = 'natures'
    __singlename__ = 'nature'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(8), nullable=False,
        info=dict(description="An identifier", format='identifier'))
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

create_translation_table('nature_names', Nature, 'names',
    relation_lazy='joined',
    name = Column(Unicode(8), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True, ripped=True)),
)

class NatureBattleStylePreference(TableBase):
    u"""Battle Palace move preference

    Specifies how likely a Pokémon with a specific Nature is to use a move of
    a particular battl style in Battle Palace or Battle Tent
    """
    __tablename__ = 'nature_battle_style_preferences'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon's nature"))
    move_battle_style_id = Column(Integer, ForeignKey('move_battle_styles.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the battle style"))
    low_hp_preference = Column(Integer, nullable=False,
        info=dict(description=u"Chance of using the move, in percent, if HP is under ½"))
    high_hp_preference = Column(Integer, nullable=False,
        info=dict(description=u"Chance of using the move, in percent, if HP is over ½"))

class NaturePokeathlonStat(TableBase):
    u"""Specifies how a Nature affects a Pokéathlon stat
    """
    __tablename__ = 'nature_pokeathlon_stats'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the nature"))
    pokeathlon_stat_id = Column(Integer, ForeignKey('pokeathlon_stats.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="ID of the stat"))
    max_change = Column(Integer, nullable=False,
        info=dict(description="Maximum change"))

class PokeathlonStat(TableBase):
    u"""A Pokéathlon stat, such as "Stamina" or "Jump".
    """
    __tablename__ = 'pokeathlon_stats'
    __singlename__ = 'pokeathlon_stat'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    identifier = Column(Unicode(8), nullable=False,
        info=dict(description="An identifier", format='identifier'))

create_translation_table('pokeathlon_stat_names', PokeathlonStat, 'names',
    name = Column(Unicode(8), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class Pokedex(TableBase):
    u"""A collection of Pokémon species ordered in a particular way
    """
    __tablename__ = 'pokedexes'
    __singlename__ = 'pokedex'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="A numeric ID"))
    region_id = Column(Integer, ForeignKey('regions.id'), nullable=True,
        info=dict(description=u"ID of the region this Pokédex is used in, or None if it's global"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))

create_translation_table('pokedex_prose', Pokedex, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    description = Column(Unicode(512), nullable=False,
        info=dict(description=u"A longer description of the Pokédex", format='plaintext')),
)

class Pokemon(TableBase):
    u"""A species of Pokémon.  The core to this whole mess.
    """
    __tablename__ = 'pokemon'
    __singlename__ = 'pokemon'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    identifier = Column(Unicode(20), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'),
        info=dict(description=u"ID of the generation this species first appeared in"))
    evolution_chain_id = Column(Integer, ForeignKey('evolution_chains.id'),
        info=dict(description=u"ID of the species' evolution chain (a.k.a. family)"))
    height = Column(Integer, nullable=False,
        info=dict(description=u"The height of the Pokémon, in decimeters (tenths of a meter)"))
    weight = Column(Integer, nullable=False,
        info=dict(description=u"The weight of the Pokémon, in tenths of a kilogram (decigrams)"))
    color_id = Column(Integer, ForeignKey('pokemon_colors.id'), nullable=False,
        info=dict(description=u"ID of this Pokémon's Pokédex color, as used for a gimmick search function in the games."))
    pokemon_shape_id = Column(Integer, ForeignKey('pokemon_shapes.id'), nullable=False,
        info=dict(description=u"ID of this Pokémon's body shape, as used for a gimmick search function in the games."))
    habitat_id = Column(Integer, ForeignKey('pokemon_habitats.id'), nullable=True,
        info=dict(description=u"ID of this Pokémon's habitat, as used for a gimmick search function in the games."))
    gender_rate = Column(Integer, nullable=False,
        info=dict(description=u"The chance of this Pokémon being female, in eighths; or -1 for genderless"))
    capture_rate = Column(Integer, nullable=False,
        info=dict(description=u"The base capture rate; up to 255"))
    base_experience = Column(Integer, nullable=False,
        info=dict(description=u"The base EXP gained when defeating this Pokémon"))  # XXX: Is this correct?
    base_happiness = Column(Integer, nullable=False,
        info=dict(description=u"The tameness when caught by a normal ball"))
    is_baby = Column(Boolean, nullable=False,
        info=dict(description=u"True iff the Pokémon is a baby, i.e. a lowest-stage Pokémon that cannot breed but whose evolved form can."))
    hatch_counter = Column(Integer, nullable=False,
        info=dict(description=u"Initial hatch counter: one must walk 255 × (hatch_counter + 1) steps before this Pokémon's egg hatches, unless utilizing bonuses like Flame Body's"))
    has_gender_differences = Column(Boolean, nullable=False,
        info=dict(description=u"Set iff the species exhibits enough sexual dimorphism to have separate sets of sprites in Gen IV and beyond."))
    order = Column(Integer, nullable=False, index=True,
        info=dict(description=u"Order for sorting. Almost national order, except families and forms are grouped together."))

    ### Stuff to handle alternate Pokémon forms

    @property
    def form(self):
        u"""Returns the Pokémon's form, using its default form as fallback."""

        return self.unique_form or self.default_form

    @property
    def is_base_form(self):
        u"""Returns True iff the Pokémon is the base form for its species,
        e.g. Land Shaymin.
        """

        return self.unique_form is None or self.unique_form.is_default

    @property
    def form_name(self):
        u"""Returns the Pokémon's form name if it represents a particular form
        and that form has a name, or None otherwise.
        """

        # If self.unique_form is None, the short-circuit "and" will go ahead
        # and return that.  Otherwise, it'll return the form's name, which may
        # also be None.
        return self.unique_form and self.unique_form.name

    @property
    def full_name(self):
        u"""Returns the Pokémon's name, including its form if applicable."""

        if self.form_name:
            return u'{0} {1}'.format(self.form_name, self.name)
        else:
            return self.name

    @property
    def normal_form(self):
        u"""Returns the normal form for this Pokémon; i.e., this will return
        regular Deoxys when called on any Deoxys form.
        """

        if self.unique_form:
            return self.unique_form.form_base_pokemon
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

create_translation_table('pokemon_names', Pokemon, 'names',
    relation_lazy='joined',
    name = Column(Unicode(20), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True, ripped=True)),
    species = Column(Unicode(16), nullable=False,
        info=dict(description=u'The short flavor text, such as "Seed" or "Lizard"; usually affixed with the word "Pokémon"',
        official=True, format='plaintext')),
)
create_translation_table('pokemon_flavor_summaries', Pokemon, 'flavor_summaries',
    flavor_summary = Column(Unicode(512), nullable=True,
        info=dict(description=u"Text containing facts from all flavor texts, for languages without official game translations", official=False, format='plaintext', ripped=True)),
)

class PokemonAbility(TableBase):
    u"""Maps an ability to a Pokémon that can have it
    """
    __tablename__ = 'pokemon_abilities'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False,
        info=dict(description=u"ID of the ability"))
    # XXX having both a method and a slot is kind of gross.  "slot" is a
    # misnomer, anyway: duplicate abilities don't appear in slot 2.
    # Probably should replace that with "order".
    is_dream = Column(Boolean, nullable=False, index=True,
        info=dict(description=u"Whether this is a Dream World ability"))
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ability slot, i.e. 1 or 2 for gen. IV"))

class PokemonColor(TableBase):
    u"""The "Pokédex color" of a Pokémon species. Usually based on the Pokémon's color.
    """
    __tablename__ = 'pokemon_colors'
    __singlename__ = 'pokemon_color'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    identifier = Column(Unicode(6), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))

create_translation_table('pokemon_color_names', PokemonColor, 'names',
    relation_lazy='joined',
    name = Column(Unicode(6), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class PokemonDexNumber(TableBase):
    u"""The number of a Pokémon in a particular Pokédex (e.g. Jigglypuff is #138 in Hoenn's 'dex)
    """
    __tablename__ = 'pokemon_dex_numbers'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokédex"))
    pokedex_number = Column(Integer, nullable=False,
        info=dict(description=u"Number of the Pokémon in that the Pokédex"))

class PokemonEggGroup(TableBase):
    u"""Maps an Egg group to a Pokémon; each Pokémon belongs to one or two egg groups
    """
    __tablename__ = 'pokemon_egg_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    egg_group_id = Column(Integer, ForeignKey('egg_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the egg group"))

class PokemonEvolution(TableBase):
    u"""A required action ("trigger") and the conditions under which the trigger
    must occur to cause a Pokémon to evolve.

    Any condition may be null if it does not apply for a particular Pokémon.
    """
    __tablename__ = 'pokemon_evolution'
    from_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False,
        info=dict(description=u"The ID of the pre-evolution Pokémon."))
    to_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the post-evolution Pokémon."))
    evolution_trigger_id = Column(Integer, ForeignKey('evolution_triggers.id'), nullable=False,
        info=dict(description=u"The ID of the evolution trigger."))
    trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        info=dict(description=u"The ID of the item that must be used on the Pokémon."))
    minimum_level = Column(Integer, nullable=True,
        info=dict(description=u"The minimum level for the Pokémon."))
    gender = Column(Enum('male', 'female', name='pokemon_evolution_gender'), nullable=True,
        info=dict(description=u"The Pokémon's required gender, or None if gender doesn't matter"))
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True,
        info=dict(description=u"The ID of the location the evolution must be triggered at."))
    held_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        info=dict(description=u"The ID of the item the Pokémon must hold."))
    time_of_day = Column(Enum('day', 'night', name='pokemon_evolution_time_of_day'), nullable=True,
        info=dict(description=u"The required time of day."))
    known_move_id = Column(Integer, ForeignKey('moves.id'), nullable=True,
        info=dict(description=u"The ID of the move the Pokémon must know."))
    minimum_happiness = Column(Integer, nullable=True,
        info=dict(description=u"The minimum happiness value the Pokémon must have."))
    minimum_beauty = Column(Integer, nullable=True,
        info=dict(description=u"The minimum Beauty value the Pokémon must have."))
    relative_physical_stats = Column(Integer, nullable=True,
        info=dict(description=u"The required relation between the Pokémon's Attack and Defense stats, as sgn(atk-def)."))
    party_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=True,
        info=dict(description=u"The ID of the Pokémon that must be present in the party."))
    trade_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=True,
        info=dict(description=u"The ID of the Pokémon for which this Pokémon must be traded."))

class PokemonFlavorText(TableBase):
    u"""In-game Pokédex descrption of a Pokémon.
    """
    __tablename__ = 'pokemon_flavor_text'
    summary_column = Pokemon.flavor_summaries_table, 'flavor_summary'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the version that has this flavor text"))
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description="The language"))
    flavor_text = Column(Unicode(255), nullable=False,
        info=dict(description=u"The flavor text", official=True, format='gametext'))

class PokemonForm(TableBase):
    u"""An individual form of a Pokémon.

    Pokémon that do not have separate forms are still given a single row to
    represent their single form.
    """
    __tablename__ = 'pokemon_forms'
    __singlename__ = 'pokemon_form'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u'A unique ID for this form.'))
    identifier = Column(Unicode(16), nullable=True,
        info=dict(description=u"An identifier", format='identifier'))
    form_base_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False,
        info=dict(description=u'The ID of the base Pokémon for this form.'))
    unique_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), autoincrement=False,
        info=dict(description=u'The ID of a Pokémon that represents specifically this form, for Pokémon with functionally-different forms like Wormadam.'))
    introduced_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), autoincrement=False,
        info=dict(description=u'The ID of the version group in which this form first appeared.'))
    is_default = Column(Boolean, nullable=False,
        info=dict(description=u'Set for exactly one form used as the default for each species.'))
    order = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u'The order in which forms should be sorted.  Multiple forms may have equal order, in which case they should fall back on sorting by name.'))

    @property
    def pokemon(self):
        u"""Returns the Pokémon for this form, using the form base as fallback.
        """

        return self.unique_pokemon or self.form_base_pokemon

    @property
    def full_name(self):
        u"""Returns the full name of this form, e.g. "Plant Cloak"."""

        if not self.name:
            return None
        elif self.form_group and self.form_group.term:
            return u'{0} {1}'.format(self.name, self.form_group.term)
        else:
            return self.name

    @property
    def pokemon_name(self):
        u"""Returns the name of this Pokémon with this form, e.g. "Plant
        Burmy".
        """

        if self.name:
            return u'{0} {1}'.format(self.name, self.form_base_pokemon.name)
        else:
            return self.form_base_pokemon.name

create_translation_table('pokemon_form_names', PokemonForm, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class PokemonFormGroup(TableBase):
    u"""Information about a Pokémon's forms as a group."""
    __tablename__ = 'pokemon_form_groups'
    __singlename__ = 'pokemon_form_group'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the base form Pokémon"))
    is_battle_only = Column(Boolean, nullable=False,
        info=dict(description=u"Set iff the forms only change in battle"))
# FIXME remooove
PokemonFormGroup.id = PokemonFormGroup.pokemon_id

create_translation_table('pokemon_form_group_prose', PokemonFormGroup, 'prose',
    term = Column(Unicode(16), nullable=True,
        info=dict(description=u"The term for this Pokémon's forms, e.g. \"Cloak\" for Burmy or \"Forme\" for Deoxys.", official=True, format='plaintext')),
    description = Column(markdown.MarkdownColumn(1024), nullable=False,
        info=dict(description=u"Description of how the forms work", format='markdown')),
)

class PokemonFormPokeathlonStat(TableBase):
    u"""A Pokémon form's performance in one Pokéathlon stat."""
    __tablename__ = 'pokemon_form_pokeathlon_stats'
    pokemon_form_id = Column(Integer, ForeignKey('pokemon_forms.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u'The ID of the Pokémon form.'))
    pokeathlon_stat_id = Column(Integer, ForeignKey('pokeathlon_stats.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u'The ID of the Pokéathlon stat.'))
    minimum_stat = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u'The minimum value for this stat for this Pokémon form.'))
    base_stat = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u'The default value for this stat for this Pokémon form.'))
    maximum_stat = Column(Integer, nullable=False, autoincrement=False,
        info=dict(description=u'The maximum value for this stat for this Pokémon form.'))

class PokemonGameIndex(TableBase):
    u"""The number of a Pokémon a game uses internally
    """
    __tablename__ = 'pokemon_game_indices'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description=u"Database ID of the Pokémon"))
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False,
        info=dict(description=u"Database ID of the generation"))
    game_index = Column(Integer, nullable=False,
        info=dict(description=u"Internal ID the generation's games use for the Pokémon"))

class PokemonHabitat(TableBase):
    u"""The habitat of a Pokémon, as given in the FireRed/LeafGreen version Pokédex
    """
    __tablename__ = 'pokemon_habitats'
    __singlename__ = 'pokemon_habitat'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))

create_translation_table('pokemon_habitat_names', PokemonHabitat, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class PokemonItem(TableBase):
    u"""Record of an item a Pokémon can hold in the wild
    """
    __tablename__ = 'pokemon_items'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the version this applies to"))
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the item"))
    rarity = Column(Integer, nullable=False,
        info=dict(description=u"Chance of the Pokémon holding the item, in percent"))

class PokemonMove(TableBase):
    u"""Record of a move a Pokémon can learn
    """
    __tablename__ = 'pokemon_moves'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, index=True,
        info=dict(description=u"ID of the Pokémon"))
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
    __singlename__ = 'pokemon_move_method'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    identifier = Column(Unicode(64), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))

create_translation_table('pokemon_move_method_prose', PokemonMoveMethod, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(64), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    description = Column(Unicode(255), nullable=False,
        info=dict(description=u"A detailed description of how the method works", format='plaintext')),
)

class PokemonShape(TableBase):
    u"""The shape of a Pokémon's body, as used in generation IV Pokédexes.
    """
    __tablename__ = 'pokemon_shapes'
    __singlename__ = 'pokemon_shape'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    identifier = Column(Unicode(24), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))

create_translation_table('pokemon_shape_prose', PokemonShape, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(24), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=False)),
    awesome_name = Column(Unicode(16), nullable=False,
        info=dict(description=u"A splendiferous name of the body shape", format='plaintext')),
)

class PokemonStat(TableBase):
    u"""A stat value of a Pokémon
    """
    __tablename__ = 'pokemon_stats'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the stat"))
    base_stat = Column(Integer, nullable=False,
        info=dict(description=u"The base stat"))
    effort = Column(Integer, nullable=False,
        info=dict(description=u"The effort increase in this stat gained when this Pokémon is defeated"))

class PokemonType(TableBase):
    u"""Maps a type to a Pokémon. Each Pokémon has 1 or 2 types.
    """
    __tablename__ = 'pokemon_types'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"ID of the Pokémon"))
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        info=dict(description=u"ID of the type"))
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The type's slot, 1 or 2, used to sort types if there are two of them"))

class Region(TableBase):
    u"""Major areas of the world: Kanto, Johto, etc.
    """
    __tablename__ = 'regions'
    __singlename__ = 'region'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))

create_translation_table('region_names', Region, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class Stat(TableBase):
    u"""A Stat, such as Attack or Speed
    """
    __tablename__ = 'stats'
    __singlename__ = 'stat'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=True,
        info=dict(description=u"For offensive and defensive stats, the damage this stat relates to; otherwise None (the NULL value)"))
    identifier = Column(Unicode(16), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))
    is_battle_only = Column(Boolean, nullable=False,
        info=dict(description=u"Whether this stat only exists within a battle"))

create_translation_table('stat_names', Stat, 'names',
    relation_lazy='joined',
    name = Column(Unicode(16), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class StatHint(TableBase):
    u"""Flavor text for genes that appears in a Pokémon's summary.  Sometimes
    called "characteristics".
    """
    __tablename__ = 'stat_hints'
    __singlename__ = 'stat_hint'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A numeric ID"))
    stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False,
        info=dict(description=u"ID of the highest stat"))
    gene_mod_5 = Column(Integer, nullable=False, index=True,
        info=dict(description=u"Value of the highest stat modulo 5"))

create_translation_table('stat_hint_names', StatHint, 'names',
    relation_lazy='joined',
    message = Column(Unicode(24), nullable=False, index=True,
        info=dict(description=u"The text displayed", official=True, format='plaintext')),
)

class SuperContestCombo(TableBase):
    u"""Combo of two moves in a Super Contest.
    """
    __tablename__ = 'super_contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the first move in the combo."))
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the second and last move."))

class SuperContestEffect(TableBase):
    u"""An effect a move can have when used in the Super Contest
    """
    __tablename__ = 'super_contest_effects'
    __singlename__ = 'super_contest_effect'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"This effect's unique ID."))
    appeal = Column(SmallInteger, nullable=False,
        info=dict(description=u"The number of hearts the user gains."))

create_translation_table('super_contest_effect_prose', SuperContestEffect, 'prose',
    flavor_text = Column(Unicode(64), nullable=False,
        info=dict(description=u"A description of the effect.", format='plaintext', official=True)),
)

class Type(TableBase):
    u"""Any of the elemental types Pokémon and moves can have."""
    __tablename__ = 'types'
    __singlename__ = 'type'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A unique ID for this type."))
    identifier = Column(Unicode(12), nullable=False,
        info=dict(description=u"An identifier", format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description=u"The ID of the generation this type first appeared in."))
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=True,
        info=dict(description=u"The ID of the damage class this type's moves had before Generation IV, null if not applicable (e.g. ???)."))

create_translation_table('type_names', Type, 'names',
    relation_lazy='joined',
    name = Column(Unicode(12), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class TypeEfficacy(TableBase):
    u"""The damage multiplier used when a move of a particular type damages a
    Pokémon of a particular other type.
    """
    __tablename__ = 'type_efficacy'
    damage_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the damaging type."))
    target_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the defending Pokémon's type."))
    damage_factor = Column(Integer, nullable=False,
        info=dict(description=u"The multiplier, as a percentage of damage inflicted."))

class Version(TableBase):
    u"""An individual main-series Pokémon game."""
    __tablename__ = 'versions'
    __singlename__ = 'version'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"A unique ID for this version."))
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        info=dict(description=u"The ID of the version group this game belongs to."))
    identifier = Column(Unicode(32), nullable=False,
        info=dict(description=u'And identifier', format='identifier'))

create_translation_table('version_names', Version, 'names',
    relation_lazy='joined',
    name = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class VersionGroup(TableBase):
    u"""A group of versions, containing either two paired versions (such as Red
    and Blue) or a single game (such as Yellow.)
    """
    __tablename__ = 'version_groups'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"This version group's unique ID."))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        info=dict(description=u"The ID of the generation the games in this group belong to."))
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), nullable=False,
        info=dict(description=u"The ID of the regional Pokédex used in this version group."))

class VersionGroupRegion(TableBase):
    u"""Maps a version group to a region that appears in it."""
    __tablename__ = 'version_group_regions'
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the version group."))
    region_id = Column(Integer, ForeignKey('regions.id'), primary_key=True, nullable=False, autoincrement=False,
        info=dict(description=u"The ID of the region."))

### Relations down here, to avoid ordering problems
Ability.changelog = relation(AbilityChangelog,
    order_by=AbilityChangelog.changed_in_version_group_id.desc(),
    backref='ability',
)
Ability.flavor_text = relation(AbilityFlavorText, order_by=AbilityFlavorText.version_group_id, backref='ability')
Ability.generation = relation(Generation, backref='abilities')

AbilityChangelog.changed_in = relation(VersionGroup, backref='ability_changelog')

AbilityFlavorText.version_group = relation(VersionGroup)
AbilityFlavorText.language = relation(Language)

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
EncounterSlot.version_group = relation(VersionGroup)

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
Item.machines = relation(Machine, order_by=Machine.version_group_id.asc())
Item.category = relation(ItemCategory)
Item.pocket = association_proxy('category', 'pocket')

ItemCategory.items = relation(Item, order_by=Item.identifier)
ItemCategory.pocket = relation(ItemPocket)

ItemFlavorText.version_group = relation(VersionGroup)
ItemFlavorText.language = relation(Language)

ItemGameIndex.item = relation(Item, backref='game_indices')
ItemGameIndex.generation = relation(Generation)

ItemPocket.categories = relation(ItemCategory, order_by=ItemCategory.identifier)

Location.region = relation(Region, backref='locations')

LocationArea.location = relation(Location, backref='areas')

LocationGameIndex.location = relation(Location, backref='game_indices')
LocationGameIndex.generation = relation(Generation)

Machine.item = relation(Item)
Machine.version_group = relation(VersionGroup)

Move.changelog = relation(MoveChangelog,
    order_by=MoveChangelog.changed_in_version_group_id.desc(),
    backref='move',
)
Move.contest_effect = relation(ContestEffect, backref='moves')
Move.contest_combo_next = association_proxy('contest_combo_first', 'second')
Move.contest_combo_prev = association_proxy('contest_combo_second', 'first')
Move.contest_type = relation(ContestType, backref='moves')
Move.damage_class = relation(MoveDamageClass, backref='moves')
Move.flags = association_proxy('move_flags', 'flag')
Move.flavor_text = relation(MoveFlavorText, order_by=MoveFlavorText.version_group_id, backref='move')
Move.generation = relation(Generation, backref='moves')
Move.machines = relation(Machine, backref='move')
Move.meta = relation(MoveMeta, uselist=False, backref='move')
Move.meta_stat_changes = relation(MoveMetaStatChange)
Move.move_effect = relation(MoveEffect, backref='moves')
Move.move_flags = relation(MoveFlag, backref='move')
Move.super_contest_effect = relation(SuperContestEffect, backref='moves')
Move.super_contest_combo_next = association_proxy('super_contest_combo_first', 'second')
Move.super_contest_combo_prev = association_proxy('super_contest_combo_second', 'first')
Move.target = relation(MoveTarget, backref='moves')
Move.type = relation(Type, backref='moves')

Move.effect = markdown.MoveEffectProperty('effect')
Move.effect_map = markdown.MoveEffectProperty('effect_map')
Move.short_effect = markdown.MoveEffectProperty('short_effect')
Move.short_effect_map = markdown.MoveEffectProperty('short_effect_map')

MoveChangelog.changed_in = relation(VersionGroup, backref='move_changelog')
MoveChangelog.move_effect = relation(MoveEffect, backref='move_changelog')
MoveChangelog.type = relation(Type, backref='move_changelog')

MoveChangelog.effect = markdown.MoveEffectProperty('effect')
MoveChangelog.effect_map = markdown.MoveEffectProperty('effect_map')
MoveChangelog.short_effect = markdown.MoveEffectProperty('short_effect')
MoveChangelog.short_effect_map = markdown.MoveEffectProperty('short_effect_map')

MoveEffect.category_map = relation(MoveEffectCategoryMap)
MoveEffect.categories = association_proxy('category_map', 'category')
MoveEffect.changelog = relation(MoveEffectChangelog,
    order_by=MoveEffectChangelog.changed_in_version_group_id.desc(),
    backref='move_effect',
)
MoveEffectCategoryMap.category = relation(MoveEffectCategory)

MoveEffectChangelog.changed_in = relation(VersionGroup, backref='move_effect_changelog')

MoveFlag.flag = relation(MoveFlagType)

MoveFlavorText.version_group = relation(VersionGroup)
MoveFlavorText.language = relation(Language)

MoveMeta.category = relation(MoveMetaCategory, backref='move_meta')
MoveMeta.ailment = relation(MoveMetaAilment, backref='move_meta')

MoveMetaStatChange.stat = relation(Stat, backref='move_meta_stat_changes')

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

NaturePokeathlonStat.pokeathlon_stat = relation(PokeathlonStat, backref='nature_effects')

Pokedex.region = relation(Region, backref='pokedexes')
Pokedex.version_groups = relation(VersionGroup, order_by=VersionGroup.id, backref='pokedex')

Pokemon.all_abilities = relation(Ability,
    secondary=PokemonAbility.__table__,
    order_by=PokemonAbility.slot,
    backref=backref('all_pokemon',
        order_by=Pokemon.order,
    ),
)
Pokemon.abilities = relation(Ability,
    secondary=PokemonAbility.__table__,
    primaryjoin=and_(
        Pokemon.id == PokemonAbility.pokemon_id,
        PokemonAbility.is_dream == False,
    ),
    order_by=PokemonAbility.slot,
    backref=backref('pokemon',
        order_by=Pokemon.order,
    ),
)
Pokemon.dream_ability = relation(Ability,
    secondary=PokemonAbility.__table__,
    primaryjoin=and_(
        Pokemon.id == PokemonAbility.pokemon_id,
        PokemonAbility.is_dream == True,
    ),
    uselist=False,
    backref=backref('dream_pokemon',
        order_by=Pokemon.order,
    ),
)
Pokemon.pokemon_color = relation(PokemonColor, backref='pokemon')
Pokemon.color = association_proxy('pokemon_color', 'name')
Pokemon.dex_numbers = relation(PokemonDexNumber, order_by=PokemonDexNumber.pokedex_id.asc(), backref='pokemon')
Pokemon.egg_groups = relation(EggGroup, secondary=PokemonEggGroup.__table__,
                                        order_by=PokemonEggGroup.egg_group_id,
                                        backref=backref('pokemon', order_by=Pokemon.order))
Pokemon.evolution_chain = relation(EvolutionChain, backref=backref('pokemon', order_by=Pokemon.order))
Pokemon.child_pokemon = relation(Pokemon,
    primaryjoin=Pokemon.id==PokemonEvolution.from_pokemon_id,
    secondary=PokemonEvolution.__table__,
    secondaryjoin=PokemonEvolution.to_pokemon_id==Pokemon.id,
    backref=backref('parent_pokemon', uselist=False),
)
Pokemon.flavor_text = relation(PokemonFlavorText, order_by=PokemonFlavorText.version_id.asc(), backref='pokemon')
Pokemon.forms = relation(PokemonForm, primaryjoin=Pokemon.id==PokemonForm.form_base_pokemon_id,
                         order_by=(PokemonForm.order.asc(), PokemonForm.identifier.asc()))
Pokemon.default_form = relation(PokemonForm,
    primaryjoin=and_(Pokemon.id==PokemonForm.form_base_pokemon_id, PokemonForm.is_default==True),
    uselist=False,
)
Pokemon.pokemon_habitat = relation(PokemonHabitat, backref='pokemon')
Pokemon.habitat = association_proxy('pokemon_habitat', 'name')
Pokemon.items = relation(PokemonItem, backref='pokemon')
Pokemon.generation = relation(Generation, backref='pokemon')
Pokemon.shape = relation(PokemonShape, backref='pokemon')
Pokemon.stats = relation(PokemonStat, backref='pokemon', order_by=PokemonStat.stat_id.asc())
Pokemon.types = relation(Type,
    secondary=PokemonType.__table__,
    order_by=PokemonType.slot.asc(),
    backref=backref('pokemon', order_by=Pokemon.order),
)

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
PokemonEvolution.trade_pokemon = relation(Pokemon,
    primaryjoin=PokemonEvolution.trade_pokemon_id==Pokemon.id,
)

PokemonFlavorText.version = relation(Version)
PokemonFlavorText.language = relation(Language)

PokemonForm.form_base_pokemon = relation(Pokemon, primaryjoin=PokemonForm.form_base_pokemon_id==Pokemon.id)
PokemonForm.unique_pokemon = relation(Pokemon, backref=backref('unique_form', uselist=False),
                                      primaryjoin=PokemonForm.unique_pokemon_id==Pokemon.id)
PokemonForm.version_group = relation(VersionGroup)
PokemonForm.form_group = association_proxy('form_base_pokemon', 'form_group')
PokemonForm.pokeathlon_stats = relation(PokemonFormPokeathlonStat,
                                        order_by=PokemonFormPokeathlonStat.pokeathlon_stat_id,
                                        backref='pokemon_form')

PokemonFormGroup.pokemon = relation(Pokemon, backref=backref('form_group',
                                                             uselist=False))

PokemonFormPokeathlonStat.pokeathlon_stat = relation(PokeathlonStat)

PokemonItem.item = relation(Item, backref='pokemon')
PokemonItem.version = relation(Version)

PokemonMove.pokemon = relation(Pokemon, backref='pokemon_moves')
PokemonMove.version_group = relation(VersionGroup)
PokemonMove.machine = relation(Machine, backref='pokemon_moves',
                               primaryjoin=and_(Machine.version_group_id==PokemonMove.version_group_id,
                                                Machine.move_id==PokemonMove.move_id),
                                foreign_keys=[Machine.version_group_id, Machine.move_id],
                                uselist=False)
PokemonMove.move = relation(Move, backref='pokemon_moves')
PokemonMove.method = relation(PokemonMoveMethod)

PokemonStat.stat = relation(Stat)

# This is technically a has-many; Generation.main_region_id -> Region.id
Region.generation = relation(Generation, uselist=False)
Region.version_group_regions = relation(VersionGroupRegion, backref='region',
                                        order_by='VersionGroupRegion.version_group_id')
Region.version_groups = association_proxy('version_group_regions', 'version_group')

Stat.damage_class = relation(MoveDamageClass, backref='stats')

StatHint.stat = relation(Stat, backref='hints')

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

Version.generation = association_proxy('version_group', 'generation')

VersionGroup.versions = relation(Version, order_by=Version.id, backref='version_group')
VersionGroup.generation = relation(Generation, backref='version_groups')
VersionGroup.version_group_regions = relation(VersionGroupRegion, backref='version_group')
VersionGroup.regions = association_proxy('version_group_regions', 'region')
