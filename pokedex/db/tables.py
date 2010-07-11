# encoding: utf8

from sqlalchemy import Column, ForeignKey, MetaData, Table
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
    __tablename__ = 'abilities'
    __singlename__ = 'ability'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(24), nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False)
    effect = Column(markdown.MarkdownColumn(5120), nullable=False)
    short_effect = Column(markdown.MarkdownColumn(255), nullable=False)

class AbilityFlavorText(TableBase):
    __tablename__ = 'ability_flavor_text'
    ability_id = Column(Integer, ForeignKey('abilities.id'), primary_key=True, nullable=False, autoincrement=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    flavor_text = Column(Unicode(64), nullable=False)

class AbilityName(TableBase):
    __tablename__ = 'ability_names'
    ability_id = Column(Integer, ForeignKey('abilities.id'), primary_key=True, nullable=False, autoincrement=False)
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=False)

class Berry(TableBase):
    __tablename__ = 'berries'
    id = Column(Integer, primary_key=True, nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    firmness_id = Column(Integer, ForeignKey('berry_firmness.id'), nullable=False)
    natural_gift_power = Column(Integer, nullable=True)
    natural_gift_type_id = Column(Integer, ForeignKey('types.id'), nullable=True)
    size = Column(Integer, nullable=False)
    max_harvest = Column(Integer, nullable=False)
    growth_time = Column(Integer, nullable=False)
    soil_dryness = Column(Integer, nullable=False)
    smoothness = Column(Integer, nullable=False)

class BerryFirmness(TableBase):
    __tablename__ = 'berry_firmness'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(10), nullable=False)

class BerryFlavor(TableBase):
    __tablename__ = 'berry_flavors'
    berry_id = Column(Integer, ForeignKey('berries.id'), primary_key=True, nullable=False, autoincrement=False)
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), primary_key=True, nullable=False, autoincrement=False)
    flavor = Column(Integer, nullable=False)

class ContestCombo(TableBase):
    __tablename__ = 'contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)

class ContestEffect(TableBase):
    __tablename__ = 'contest_effects'
    id = Column(Integer, primary_key=True, nullable=False)
    appeal = Column(SmallInteger, nullable=False)
    jam = Column(SmallInteger, nullable=False)
    flavor_text = Column(Unicode(64), nullable=False)
    effect = Column(Unicode(255), nullable=False)

class ContestType(TableBase):
    __tablename__ = 'contest_types'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(6), nullable=False)
    flavor = Column(Unicode(6), nullable=False)
    color = Column(Unicode(6), nullable=False)

class EggGroup(TableBase):
    __tablename__ = 'egg_groups'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)

class Encounter(TableBase):
    """Rows in this table represent encounters with wild Pokémon.  Bear with
    me, here.

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
    id = Column(Integer, primary_key=True, nullable=False)
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False, autoincrement=False)
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), nullable=False, autoincrement=False)
    encounter_slot_id = Column(Integer, ForeignKey('encounter_slots.id'), nullable=False, autoincrement=False)
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False)
    min_level = Column(Integer, nullable=False, autoincrement=False)
    max_level = Column(Integer, nullable=False, autoincrement=False)

class EncounterCondition(TableBase):
    """Rows in this table represent varying conditions in the game world, such
    as time of day.
    """

    __tablename__ = 'encounter_conditions'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(64), nullable=False)

class EncounterConditionValue(TableBase):
    """Rows in this table represent possible states for a condition; for
    example, the state of 'swarm' could be 'swarm' or 'no swarm'.
    """

    __tablename__ = 'encounter_condition_values'
    id = Column(Integer, primary_key=True, nullable=False)
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), primary_key=False, nullable=False, autoincrement=False)
    name = Column(Unicode(64), nullable=False)
    is_default = Column(Boolean, nullable=False)

class EncounterConditionValueMap(TableBase):
    """Maps encounters to the specific conditions under which they occur."""

    __tablename__ = 'encounter_condition_value_map'
    encounter_id = Column(Integer, ForeignKey('encounters.id'), primary_key=True, nullable=False, autoincrement=False)
    encounter_condition_value_id = Column(Integer, ForeignKey('encounter_condition_values.id'), primary_key=True, nullable=False, autoincrement=False)

class EncounterTerrain(TableBase):
    """Rows in this table represent ways the player can enter a wild encounter,
    e.g., surfing, fishing, or walking through tall grass.
    """

    __tablename__ = 'encounter_terrain'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(64), nullable=False)

class EncounterSlot(TableBase):
    """Rows in this table represent an abstract "slot" within a terrain,
    associated with both some set of conditions and a rarity.

    Note that there are two encounters per slot, so the rarities will only add
    up to 50.
    """

    __tablename__ = 'encounter_slots'
    id = Column(Integer, primary_key=True, nullable=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, autoincrement=False)
    encounter_terrain_id = Column(Integer, ForeignKey('encounter_terrain.id'), primary_key=False, nullable=False, autoincrement=False)
    slot = Column(Integer, nullable=True)
    rarity = Column(Integer, nullable=False)

class EncounterSlotCondition(TableBase):
    """Lists all conditions that affect each slot."""

    __tablename__ = 'encounter_slot_conditions'
    encounter_slot_id = Column(Integer, ForeignKey('encounter_slots.id'), primary_key=True, nullable=False, autoincrement=False)
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), primary_key=True, nullable=False, autoincrement=False)

class EvolutionChain(TableBase):
    __tablename__ = 'evolution_chains'
    id = Column(Integer, primary_key=True, nullable=False)
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), nullable=False)
    baby_trigger_item = Column(Unicode(12))

class EvolutionTrigger(TableBase):
    __tablename__ = 'evolution_triggers'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(16), nullable=False)

class Experience(TableBase):
    __tablename__ = 'experience'
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), primary_key=True, nullable=False)
    level = Column(Integer, primary_key=True, nullable=False, autoincrement=False)
    experience = Column(Integer, nullable=False)

class Generation(TableBase):
    __tablename__ = 'generations'
    id = Column(Integer, primary_key=True, nullable=False)
    main_region_id = Column(Integer, ForeignKey('regions.id'))
    canonical_pokedex_id = Column(Integer, ForeignKey('pokedexes.id'))
    name = Column(Unicode(16), nullable=False)

class GrowthRate(TableBase):
    """`formula` is written in LaTeX math notation."""
    __tablename__ = 'growth_rates'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(20), nullable=False)
    formula = Column(Unicode(500), nullable=False)

class Item(TableBase):
    __tablename__ = 'items'
    __singlename__ = 'item'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)
    category_id = Column(Integer, ForeignKey('item_categories.id'), nullable=False)
    cost = Column(Integer, nullable=False)
    fling_power = Column(Integer, nullable=True)
    fling_effect_id = Column(Integer, ForeignKey('item_fling_effects.id'), nullable=True)
    effect = Column(markdown.MarkdownColumn(5120), nullable=False)

    @property
    def appears_underground(self):
        return any(flag.identifier == u'underground' for flag in self.flags)

class ItemCategory(TableBase):
    __tablename__ = 'item_categories'
    id = Column(Integer, primary_key=True, nullable=False)
    pocket_id = Column(Integer, ForeignKey('item_pockets.id'), nullable=False)
    name = Column(Unicode(16), nullable=False)

class ItemFlag(TableBase):
    __tablename__ = 'item_flags'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(24), nullable=False)
    name = Column(Unicode(64), nullable=False)

class ItemFlagMap(TableBase):
    __tablename__ = 'item_flag_map'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False)
    item_flag_id = Column(Integer, ForeignKey('item_flags.id'), primary_key=True, autoincrement=False, nullable=False)

class ItemFlavorText(TableBase):
    __tablename__ = 'item_flavor_text'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, autoincrement=False, nullable=False)
    flavor_text = Column(Unicode(255), nullable=False)

class ItemFlingEffect(TableBase):
    __tablename__ = 'item_fling_effects'
    id = Column(Integer, primary_key=True, nullable=False)
    effect = Column(Unicode(255), nullable=False)

class ItemInternalID(TableBase):
    __tablename__ = 'item_internal_ids'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False)
    internal_id = Column(Integer, nullable=False)

class ItemName(TableBase):
    __tablename__ = 'item_names'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, nullable=False, autoincrement=False)
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=False)

class ItemPocket(TableBase):
    __tablename__ = 'item_pockets'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(16), nullable=False)
    name = Column(Unicode(16), nullable=False)

class Language(TableBase):
    __tablename__ = 'languages'
    id = Column(Integer, primary_key=True, nullable=False)
    iso639 = Column(Unicode(2), nullable=False)
    iso3166 = Column(Unicode(2), nullable=False)
    name = Column(Unicode(16), nullable=False)

class Location(TableBase):
    __tablename__ = 'locations'
    __singlename__ = 'location'
    id = Column(Integer, primary_key=True, nullable=False)
    region_id = Column(Integer, ForeignKey('regions.id'))
    name = Column(Unicode(64), nullable=False)

class LocationArea(TableBase):
    __tablename__ = 'location_areas'
    id = Column(Integer, primary_key=True, nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    internal_id = Column(Integer, nullable=False)
    name = Column(Unicode(64), nullable=True)

class LocationAreaEncounterRate(TableBase):
    __tablename__ = 'location_area_encounter_rates'
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), primary_key=True, nullable=False, autoincrement=False)
    encounter_terrain_id = Column(Integer, ForeignKey('encounter_terrain.id'), primary_key=True, nullable=False, autoincrement=False)
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, autoincrement=False)
    rate = Column(Integer, nullable=True)

class Machine(TableBase):
    __tablename__ = 'machines'
    machine_number = Column(Integer, primary_key=True, nullable=False, autoincrement=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False)

    @property
    def is_hm(self):
        return self.machine_number >= 100

class MoveBattleStyle(TableBase):
    __tablename__ = 'move_battle_styles'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(8), nullable=False)

class MoveEffectCategory(TableBase):
    __tablename__ = 'move_effect_categories'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(64), nullable=False)
    can_affect_user = Column(Boolean, nullable=False)

class MoveEffectCategoryMap(TableBase):
    __tablename__ = 'move_effect_category_map'
    move_effect_id = Column(Integer, ForeignKey('move_effects.id'), primary_key=True, nullable=False)
    move_effect_category_id = Column(Integer, ForeignKey('move_effect_categories.id'), primary_key=True, nullable=False)
    affects_user = Column(Boolean, primary_key=True, nullable=False)

class MoveDamageClass(TableBase):
    __tablename__ = 'move_damage_classes'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(8), nullable=False)
    description = Column(Unicode(64), nullable=False)

class MoveEffect(TableBase):
    __tablename__ = 'move_effects'
    id = Column(Integer, primary_key=True, nullable=False)
    priority = Column(SmallInteger, nullable=False)
    short_effect = Column(Unicode(256), nullable=False)
    effect = Column(Unicode(5120), nullable=False)

class MoveFlag(TableBase):
    __tablename__ = 'move_flags'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)
    move_flag_type_id = Column(Integer, ForeignKey('move_flag_types.id'), primary_key=True, nullable=False, autoincrement=False)

class MoveFlagType(TableBase):
    __tablename__ = 'move_flag_types'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(16), nullable=False)
    name = Column(Unicode(32), nullable=False)
    description = Column(markdown.MarkdownColumn(128), nullable=False)

class MoveFlavorText(TableBase):
    __tablename__ = 'move_flavor_text'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    flavor_text = Column(Unicode(255), nullable=False)

class MoveName(TableBase):
    __tablename__ = 'move_names'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=False)

class MoveTarget(TableBase):
    __tablename__ = 'move_targets'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(32), nullable=False)
    description = Column(Unicode(128), nullable=False)

class Move(TableBase):
    __tablename__ = 'moves'
    __singlename__ = 'move'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(12), nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False)
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False)
    power = Column(SmallInteger)
    pp = Column(SmallInteger, nullable=False)
    accuracy = Column(SmallInteger)
    target_id = Column(Integer, ForeignKey('move_targets.id'), nullable=False)
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=False)
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=False)
    effect_chance = Column(Integer)
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), nullable=True)
    contest_effect_id = Column(Integer, ForeignKey('contest_effects.id'), nullable=True)
    super_contest_effect_id = Column(Integer, ForeignKey('super_contest_effects.id'), nullable=False)

class Nature(TableBase):
    __tablename__ = 'natures'
    __singlename__ = 'nature'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(8), nullable=False)
    decreased_stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False)
    increased_stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False)
    hates_flavor_id = Column(Integer, ForeignKey('contest_types.id'), nullable=False)
    likes_flavor_id = Column(Integer, ForeignKey('contest_types.id'), nullable=False)

class NatureBattleStylePreference(TableBase):
    __tablename__ = 'nature_battle_style_preferences'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False)
    move_battle_style_id = Column(Integer, ForeignKey('move_battle_styles.id'), primary_key=True, nullable=False)
    low_hp_preference = Column(Integer, nullable=False)
    high_hp_preference = Column(Integer, nullable=False)

class NatureName(TableBase):
    __tablename__ = 'nature_names'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False, autoincrement=False)
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(8), nullable=False)

class NaturePokeathlonStat(TableBase):
    __tablename__ = 'nature_pokeathlon_stats'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False)
    pokeathlon_stat_id = Column(Integer, ForeignKey('pokeathlon_stats.id'), primary_key=True, nullable=False)
    max_change = Column(Integer, nullable=False)

class PokeathlonStat(TableBase):
    __tablename__ = 'pokeathlon_stats'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(8), nullable=False)

class Pokedex(TableBase):
    __tablename__ = 'pokedexes'
    id = Column(Integer, primary_key=True, nullable=False)
    region_id = Column(Integer, ForeignKey('regions.id'), nullable=True)
    name = Column(Unicode(16), nullable=False)
    description = Column(Unicode(512))

class PokedexVersionGroup(TableBase):
    __tablename__ = 'pokedex_version_groups'
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True, nullable=False, autoincrement=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)

class Pokemon(TableBase):
    """The core to this whole mess.

    Note that I use both 'forme' and 'form' in both code and the database.  I
    only use 'forme' when specifically referring to Pokémon that have multiple
    distinct species as forms—i.e., different stats or movesets.  'Form' is a
    more general term referring to any variation within a species, including
    purely cosmetic forms like Unown.
    """
    __tablename__ = 'pokemon'
    __singlename__ = 'pokemon'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(20), nullable=False)
    forme_name = Column(Unicode(16))
    forme_base_pokemon_id = Column(Integer, ForeignKey('pokemon.id'))
    generation_id = Column(Integer, ForeignKey('generations.id'))
    evolution_chain_id = Column(Integer, ForeignKey('evolution_chains.id'))
    height = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False)
    species = Column(Unicode(16), nullable=False)
    color_id = Column(Integer, ForeignKey('pokemon_colors.id'), nullable=False)
    pokemon_shape_id = Column(Integer, ForeignKey('pokemon_shapes.id'), nullable=False)
    habitat_id = Column(Integer, ForeignKey('pokemon_habitats.id'), nullable=True)
    gender_rate = Column(Integer, nullable=False)
    capture_rate = Column(Integer, nullable=False)
    base_experience = Column(Integer, nullable=False)
    base_happiness = Column(Integer, nullable=False)
    is_baby = Column(Boolean, nullable=False)
    hatch_counter = Column(Integer, nullable=False)
    has_gen4_fem_sprite = Column(Boolean, nullable=False)
    has_gen4_fem_back_sprite = Column(Boolean, nullable=False)

    ### Stuff to handle alternate Pokémon forms

    @property
    def national_id(self):
        """Returns the National Pokédex number for this Pokémon.  Use this
        instead of the id directly; alternate formes may make the id incorrect.
        """

        if self.forme_base_pokemon_id:
            return self.forme_base_pokemon_id
        return self.id

    @property
    def full_name(self):
        """Returns the name of this Pokémon, including its Forme, if any."""

        if self.forme_name:
            return "%s %s" % (self.forme_name.title(), self.name)
        return self.name

    @property
    def normal_form(self):
        """Returns the normal form for this Pokémon; i.e., this will return
        regular Deoxys when called on any Deoxys form.
        """

        if self.forme_base_pokemon:
            return self.forme_base_pokemon

        return self

    ### Not forms!

    def stat(self, stat_name):
        """Returns a PokemonStat record for the given stat name (or Stat row
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
    __tablename__ = 'pokemon_abilities'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False)
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False)

class PokemonColor(TableBase):
    __tablename__ = 'pokemon_colors'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(6), nullable=False)

class PokemonDexNumber(TableBase):
    __tablename__ = 'pokemon_dex_numbers'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True, nullable=False, autoincrement=False)
    pokedex_number = Column(Integer, nullable=False)

class PokemonEggGroup(TableBase):
    __tablename__ = 'pokemon_egg_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    egg_group_id = Column(Integer, ForeignKey('egg_groups.id'), primary_key=True, nullable=False, autoincrement=False)

class PokemonEvolution(TableBase):
    __tablename__ = 'pokemon_evolution'
    from_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False)
    to_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    evolution_trigger_id = Column(Integer, ForeignKey('evolution_triggers.id'), nullable=False)
    trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True)
    minimum_level = Column(Integer, nullable=True)
    gender = Column(Enum('male', 'female', name='pokemon_evolution_gender'), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    held_item_id = Column(Integer, ForeignKey('items.id'), nullable=True)
    time_of_day = Column(Enum('morning', 'day', 'night', name='pokemon_evolution_time_of_day'), nullable=True)
    known_move_id = Column(Integer, ForeignKey('moves.id'), nullable=True)
    minimum_happiness = Column(Integer, nullable=True)
    minimum_beauty = Column(Integer, nullable=True)
    relative_physical_stats = Column(Integer, nullable=True)
    party_pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=True)

class PokemonFlavorText(TableBase):
    __tablename__ = 'pokemon_flavor_text'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False)
    flavor_text = Column(Unicode(255), nullable=False)

class PokemonFormGroup(TableBase):
    __tablename__ = 'pokemon_form_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    is_battle_only = Column(Boolean, nullable=False)
    description = Column(markdown.MarkdownColumn(1024), nullable=False)

class PokemonFormSprite(TableBase):
    __tablename__ = 'pokemon_form_sprites'
    id = Column(Integer, primary_key=True, nullable=False)
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    introduced_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=True)
    is_default = Column(Boolean, nullable=True)

class PokemonHabitat(TableBase):
    __tablename__ = 'pokemon_habitats'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=False)

class PokemonInternalID(TableBase):
    __tablename__ = 'pokemon_internal_ids'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, autoincrement=False, nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False)
    internal_id = Column(Integer, nullable=False)

class PokemonItem(TableBase):
    __tablename__ = 'pokemon_items'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False)
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, nullable=False, autoincrement=False)
    rarity = Column(Integer, nullable=False)

class PokemonMove(TableBase):
    __tablename__ = 'pokemon_moves'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False, index=True)
    pokemon_move_method_id = Column(Integer, ForeignKey('pokemon_move_methods.id'), primary_key=True, nullable=False, autoincrement=False)
    level = Column(Integer, primary_key=True, nullable=True, autoincrement=False, index=True)
    order = Column(Integer, nullable=True, index=True)

class PokemonMoveMethod(TableBase):
    __tablename__ = 'pokemon_move_methods'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(64), nullable=False)
    description = Column(Unicode(255), nullable=False)

class PokemonName(TableBase):
    __tablename__ = 'pokemon_names'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=False)

class PokemonShape(TableBase):
    __tablename__ = 'pokemon_shapes'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(24), nullable=False)
    awesome_name = Column(Unicode(16), nullable=False)

class PokemonStat(TableBase):
    __tablename__ = 'pokemon_stats'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True, nullable=False, autoincrement=False)
    base_stat = Column(Integer, nullable=False)
    effort = Column(Integer, nullable=False)

class PokemonType(TableBase):
    __tablename__ = 'pokemon_types'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False)
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False)

class Region(TableBase):
    """Major areas of the world: Kanto, Johto, etc."""
    __tablename__ = 'regions'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)

class Stat(TableBase):
    __tablename__ = 'stats'
    id = Column(Integer, primary_key=True, nullable=False)
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=True)
    name = Column(Unicode(16), nullable=False)

class SuperContestCombo(TableBase):
    __tablename__ = 'super_contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)

class SuperContestEffect(TableBase):
    __tablename__ = 'super_contest_effects'
    id = Column(Integer, primary_key=True, nullable=False)
    appeal = Column(SmallInteger, nullable=False)
    flavor_text = Column(Unicode(64), nullable=False)

class TypeEfficacy(TableBase):
    __tablename__ = 'type_efficacy'
    damage_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False)
    target_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False)
    damage_factor = Column(Integer, nullable=False)

class Type(TableBase):
    __tablename__ = 'types'
    __singlename__ = 'type'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(8), nullable=False)
    abbreviation = Column(Unicode(3), nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False)
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=False) ## ??? is none; everything else is physical or special

class VersionGroup(TableBase):
    __tablename__ = 'version_groups'
    id = Column(Integer, primary_key=True, nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False)

class VersionGroupRegion(TableBase):
    __tablename__ = 'version_group_regions'
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False)
    region_id = Column(Integer, ForeignKey('regions.id'), primary_key=True, nullable=False)

class Version(TableBase):
    __tablename__ = 'versions'
    id = Column(Integer, primary_key=True, nullable=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False)
    name = Column(Unicode(32), nullable=False)


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

ItemName.language = relation(Language)

ItemPocket.categories = relation(ItemCategory, order_by=ItemCategory.name)

Location.region = relation(Region, backref='locations')

LocationArea.location = relation(Location, backref='areas')

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
Move.priority = association_proxy('move_effect', 'priority')
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
Pokemon.stats = relation(PokemonStat, backref='pokemon')
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

Version.version_group = relation(VersionGroup, backref='versions')
Version.generation = association_proxy('version_group', 'generation')

VersionGroup.generation = relation(Generation, backref='version_groups')
VersionGroup.version_group_regions = relation(VersionGroupRegion, backref='version_group')
VersionGroup.regions = association_proxy('version_group_regions', 'region')
