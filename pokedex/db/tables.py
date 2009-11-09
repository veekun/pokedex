# encoding: utf8

from sqlalchemy import Column, ForeignKey, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relation
from sqlalchemy.types import *
from sqlalchemy.databases.mysql import *

from pokedex.db import rst

metadata = MetaData()
TableBase = declarative_base(metadata=metadata)

class Ability(TableBase):
    __tablename__ = 'abilities'
    __singlename__ = 'ability'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(24), nullable=False)
    flavor_text = Column(Unicode(64), nullable=False)
    effect = Column(Unicode(255), nullable=False)

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

class EggGroup(TableBase):
    __tablename__ = 'egg_groups'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)

class Encounter(TableBase):
    """Rows in this table represent encounters with wild Pokémon.

    Within a given area in a given game, encounters are differentiated by the
    slot they are in and a world condition.

    Groups of slots belong to encounter types; these are what the player is
    doing to get an encounter, such as surfing or walking through tall grass.

    Within an encounter type, slots are defined primarily by rarity.  Each slot
    can also be affected by a world condition; for example, the 20% slot for
    walking in tall grass is affected by whether a swarm is in effect in the
    areas.  "There is a swarm" and "there is not a swarm" are conditions, and
    together they make a condition group.  However, since "not a swarm" is a
    base state rather than any sort of new state, it is omitted and instead
    referred to by a NULL.

    A slot (20% walking in grass) and single world condition (NULL, i.e. no
    swarm) are thus enough to define a specific encounter.
    
    Well, okay, almost: each slot actually appears twice.
    """

    __tablename__ = 'encounters'
    id = Column(Integer, primary_key=True, nullable=False)
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False, autoincrement=False)
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), nullable=False, autoincrement=False)
    encounter_type_slot_id = Column(Integer, ForeignKey('encounter_type_slots.id'), nullable=False, autoincrement=False)
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), nullable=True, autoincrement=False)
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False)
    min_level = Column(Integer, nullable=False, autoincrement=False)
    max_level = Column(Integer, nullable=False, autoincrement=False)

class EncounterCondition(TableBase):
    """Rows in this table represent something different about the world that
    can affect what Pokémon are encountered.
    """

    __tablename__ = 'encounter_conditions'
    id = Column(Integer, primary_key=True, nullable=False)
    encounter_condition_group_id = Column(Integer, ForeignKey('encounter_condition_groups.id'), primary_key=False, nullable=False, autoincrement=False)
    name = Column(Unicode(64), nullable=False)

class EncounterConditionGroup(TableBase):
    """Rows in this table represent a group of mutually exclusive conditions,
    such as morning/day/night.  "Conditions" that are part of the default state
    of the world, such as "not during a swarm" or "not using the PokéRadar",
    are not included in this table and are referred to by NULLs in other
    tables.
    """

    __tablename__ = 'encounter_condition_groups'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(64), nullable=False)

class EncounterType(TableBase):
    """Rows in this table represent ways the player can enter a wild encounter;
    i.e. surfing, fishing, or walking through tall grass.
    """

    __tablename__ = 'encounter_types'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(64), nullable=False)

class EncounterTypeSlot(TableBase):
    """Rows in this table represent an abstract "slot" within an encounter
    type, associated with both a condition group and a rarity.

    Note that there are two encounters per slot, so the rarities will only add
    up to 50.
    """

    __tablename__ = 'encounter_type_slots'
    id = Column(Integer, primary_key=True, nullable=False)
    encounter_type_id = Column(Integer, ForeignKey('encounter_types.id'), primary_key=False, nullable=False, autoincrement=False)
    encounter_condition_group_id = Column(Integer, ForeignKey('encounter_condition_groups.id'), primary_key=False, nullable=True, autoincrement=False)
    rarity = Column(Integer, nullable=False, autoincrement=False)

class EvolutionChain(TableBase):
    __tablename__ = 'evolution_chains'
    id = Column(Integer, primary_key=True, nullable=False)
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), nullable=False)
    steps_to_hatch = Column(Integer, nullable=False)
    baby_trigger_item = Column(Unicode(12))

class EvolutionMethod(TableBase):
    __tablename__ = 'evolution_methods'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(64), nullable=False)
    description = Column(Unicode(255), nullable=False)

class Generation(TableBase):
    __tablename__ = 'generations'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)
    main_region = Column(Unicode(16), nullable=False)

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

class Language(TableBase):
    __tablename__ = 'languages'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)

class Location(TableBase):
    __tablename__ = 'locations'
    __singlename__ = 'location'
    id = Column(Integer, primary_key=True, nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False)
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
    encounter_type_id = Column(Integer, ForeignKey('encounter_types.id'), primary_key=True, nullable=False, autoincrement=False)
    rate = Column(Integer, nullable=True)

class Machine(TableBase):
    __tablename__ = 'machines'
    machine_number = Column(Integer, primary_key=True, nullable=False, autoincrement=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False)

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
    name = Column(Unicode(32), nullable=False)
    description = Column(rst.RstTextColumn(128), nullable=False)

class MoveFlavorText(TableBase):
    __tablename__ = 'move_flavor_text'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, nullable=False, autoincrement=False)
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
    contest_type = Column(Unicode(8), nullable=False)
    contest_effect_id = Column(Integer, ForeignKey('contest_effects.id'), nullable=True)
    super_contest_effect_id = Column(Integer, ForeignKey('super_contest_effects.id'), nullable=False)

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
    evolution_parent_pokemon_id = Column(Integer, ForeignKey('pokemon.id'))
    evolution_method_id = Column(Integer, ForeignKey('evolution_methods.id'))
    evolution_parameter = Column(Unicode(32))
    height = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False)
    species = Column(Unicode(16), nullable=False)
    color = Column(Unicode(6), nullable=False)
    pokemon_shape_id = Column(Integer, ForeignKey('pokemon_shapes.id'), nullable=False)
    habitat = Column(Unicode(16), nullable=False)
    gender_rate = Column(Integer, nullable=False)
    capture_rate = Column(Integer, nullable=False)
    base_experience = Column(Integer, nullable=False)
    base_happiness = Column(Integer, nullable=False)
    gen1_internal_id = Column(Integer)
    is_baby = Column(Boolean, nullable=False)
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
            return "%s %s" % (self.forme_name.capitalize(), self.name)
        return self.name

    @property
    def normal_form(self):
        """Returns the normal form for this Pokémon; i.e., this will return
        regular Deoxys when called on any Deoxys form.
        """

        if self.forme_base_pokemon:
            return self.forme_base_pokemon

        return self

class PokemonAbility(TableBase):
    __tablename__ = 'pokemon_abilities'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False)
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False)

class PokemonDexNumber(TableBase):
    __tablename__ = 'pokemon_dex_numbers'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, nullable=False, autoincrement=False)
    pokedex_number = Column(Integer, nullable=False)

class PokemonEggGroup(TableBase):
    __tablename__ = 'pokemon_egg_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    egg_group_id = Column(Integer, ForeignKey('egg_groups.id'), primary_key=True, nullable=False, autoincrement=False)

class PokemonFlavorText(TableBase):
    __tablename__ = 'pokemon_flavor_text'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False)
    flavor_text = Column(Unicode(255), nullable=False)

class PokemonFormGroup(TableBase):
    __tablename__ = 'pokemon_form_groups'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    description = Column(Unicode(512), nullable=False)

class PokemonFormSprite(TableBase):
    __tablename__ = 'pokemon_form_sprites'
    id = Column(Integer, primary_key=True, nullable=False)
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False)
    introduced_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False)
    name = Column(Unicode(16), nullable=True)

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
    level = Column(Integer, primary_key=True, nullable=True, autoincrement=False)
    order = Column(Integer, nullable=True)

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

class Stat(TableBase):
    __tablename__ = 'stats'
    id = Column(Integer, primary_key=True, nullable=False)
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

class VersionGroup(TableBase):
    __tablename__ = 'version_groups'
    id = Column(Integer, primary_key=True, nullable=False)
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False)

class Version(TableBase):
    __tablename__ = 'versions'
    id = Column(Integer, primary_key=True, nullable=False)
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False)
    name = Column(Unicode(32), nullable=False)


### Relations down here, to avoid ordering problems
ContestCombo.first = relation(Move, primaryjoin=ContestCombo.first_move_id==Move.id,
                                    backref='contest_combo_first')
ContestCombo.second = relation(Move, primaryjoin=ContestCombo.second_move_id==Move.id,
                                     backref='contest_combo_second')

Encounter.pokemon = relation(Pokemon, backref='encounters')
Encounter.version = relation(Version, backref='encounters')
Encounter.location_area = relation(LocationArea, backref='encounters')
Encounter.slot = relation(EncounterTypeSlot, backref='encounters')
Encounter.condition = relation(EncounterCondition, backref='encounters')

EncounterCondition.group = relation(EncounterConditionGroup,
                                    backref='conditions')

EncounterTypeSlot.type = relation(EncounterType, backref='slots')

EvolutionChain.growth_rate = relation(GrowthRate, backref='evolution_chains')

Generation.versions = relation(Version, secondary=VersionGroup.__table__)

LocationArea.location = relation(Location, backref='areas')

Machine.version_group = relation(VersionGroup)

Move.contest_effect = relation(ContestEffect, backref='moves')
Move.contest_combo_next = association_proxy('contest_combo_first', 'second')
Move.contest_combo_prev = association_proxy('contest_combo_second', 'first')
Move.damage_class = relation(MoveDamageClass, backref='moves')
Move.flags = association_proxy('move_flags', 'flag')
Move.flavor_text = relation(MoveFlavorText, order_by=MoveFlavorText.generation_id, backref='move')
Move.foreign_names = relation(MoveName, backref='pokemon')
Move.generation = relation(Generation, backref='moves')
Move.machines = relation(Machine, backref='move')
Move.move_effect = relation(MoveEffect, backref='moves')
Move.move_flags = relation(MoveFlag, backref='move')
Move.super_contest_effect = relation(SuperContestEffect, backref='moves')
Move.super_contest_combo_next = association_proxy('super_contest_combo_first', 'second')
Move.super_contest_combo_prev = association_proxy('super_contest_combo_second', 'first')
Move.target = relation(MoveTarget, backref='moves')
Move.type = relation(Type, backref='moves')

Move.effect = rst.MoveEffectProperty('effect')
Move.priority = association_proxy('move_effect', 'priority')
Move.short_effect = rst.MoveEffectProperty('short_effect')

MoveEffect.category_map = relation(MoveEffectCategoryMap)
MoveEffect.categories = association_proxy('category_map', 'category')
MoveEffectCategoryMap.category = relation(MoveEffectCategory)

MoveFlag.flag = relation(MoveFlagType)

MoveFlavorText.generation = relation(Generation)

MoveName.language = relation(Language)

Pokemon.abilities = relation(Ability, secondary=PokemonAbility.__table__,
                                      order_by=PokemonAbility.slot,
                                      backref='pokemon')
Pokemon.formes = relation(Pokemon, primaryjoin=Pokemon.id==Pokemon.forme_base_pokemon_id,
                                               backref=backref('forme_base_pokemon',
                                                               remote_side=[Pokemon.id]))
Pokemon.dex_numbers = relation(PokemonDexNumber, backref='pokemon')
Pokemon.egg_groups = relation(EggGroup, secondary=PokemonEggGroup.__table__,
                                        order_by=PokemonEggGroup.egg_group_id,
                                        backref='pokemon')
Pokemon.evolution_chain = relation(EvolutionChain, backref='pokemon')
Pokemon.evolution_method = relation(EvolutionMethod)
Pokemon.evolution_children = relation(Pokemon, primaryjoin=Pokemon.id==Pokemon.evolution_parent_pokemon_id,
                                               backref=backref('evolution_parent',
                                                               remote_side=[Pokemon.id]))
Pokemon.flavor_text = relation(PokemonFlavorText, order_by=PokemonFlavorText.pokemon_id, backref='pokemon')
Pokemon.foreign_names = relation(PokemonName, backref='pokemon')
Pokemon.items = relation(PokemonItem)
Pokemon.generation = relation(Generation, backref='pokemon')
Pokemon.shape = relation(PokemonShape, backref='pokemon')
Pokemon.stats = relation(PokemonStat, backref='pokemon')
Pokemon.types = relation(Type, secondary=PokemonType.__table__)

PokemonDexNumber.generation = relation(Generation)

PokemonFlavorText.version = relation(Version)

PokemonItem.item = relation(Item, backref='pokemon')
PokemonItem.version = relation(Version)

PokemonFormGroup.pokemon = relation(Pokemon, backref=backref('form_group',
                                                             uselist=False))
PokemonFormSprite.pokemon = relation(Pokemon, backref='form_sprites')
PokemonFormSprite.introduced_in = relation(VersionGroup)

PokemonMove.pokemon = relation(Pokemon, backref='pokemon_moves')
PokemonMove.version_group = relation(VersionGroup)
PokemonMove.move = relation(Move, backref='pokemon_moves')
PokemonMove.method = relation(PokemonMoveMethod)

PokemonName.language = relation(Language)

PokemonStat.stat = relation(Stat)

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

Version.version_group = relation(VersionGroup, backref='versions')
Version.generation = association_proxy('version_group', 'generation')

VersionGroup.generation = relation(Generation, backref='version_groups')
