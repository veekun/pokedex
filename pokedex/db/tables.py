from sqlalchemy import Column, ForeignKey, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relation
from sqlalchemy.types import *
from sqlalchemy.databases.mysql import *

metadata = MetaData()
TableBase = declarative_base(metadata=metadata)

class Ability(TableBase):
    __tablename__ = 'abilities'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(24), nullable=False)
    flavor_text = Column(Unicode(64), nullable=False)
    effect = Column(Unicode(255), nullable=False)

class ContestEffect(TableBase):
    __tablename__ = 'contest_effects'
    id = Column(Integer, primary_key=True, nullable=False)
    appeal = Column(SmallInteger, nullable=False)
    jam = Column(SmallInteger, nullable=False)
    flavor = Column(Unicode(255), nullable=False)
    effect = Column(Unicode(255), nullable=False)

class EggGroup(TableBase):
    __tablename__ = 'egg_groups'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)

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
    __tablename__ = 'growth_rates'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)
    formula = Column(Unicode(255), nullable=False)

class Language(TableBase):
    __tablename__ = 'languages'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(16), nullable=False)

class MoveEffect(TableBase):
    __tablename__ = 'move_effects'
    id = Column(Integer, primary_key=True, nullable=False)
    priority = Column(SmallInteger, nullable=False)
    short_effect = Column(Unicode(128), nullable=False)
    effect = Column(Unicode(255), nullable=False)

class MoveTarget(TableBase):
    __tablename__ = 'move_targets'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(32), nullable=False)
    description = Column(Unicode(128), nullable=False)

class Move(TableBase):
    __tablename__ = 'moves'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(12), nullable=False)
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False)
    power = Column(SmallInteger)
    pp = Column(SmallInteger, nullable=False)
    accuracy = Column(SmallInteger)
    target_id = Column(Integer, ForeignKey('move_targets.id'), nullable=False)
    category = Column(Unicode(8), nullable=False)
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=False)
    effect_chance = Column(Integer)
    contest_type = Column(Unicode(8), nullable=False)
    contest_effect_id = Column(Integer, ForeignKey('contest_effects.id'), nullable=False)
    super_contest_effect_id = Column(Integer, nullable=False)

class Pokemon(TableBase):
    __tablename__ = 'pokemon'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode(20), nullable=False)
    forme_name = Column(Unicode(16))
    forme_base_pokemon_id = Column(Integer, ForeignKey('pokemon.id'))
    generation_id = Column(Integer, ForeignKey('generations.id'))
    evolution_chain_id = Column(Integer, ForeignKey('evolution_chains.id'), nullable=False)
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
    has_dp_fem_sprite = Column(Boolean, nullable=False)
    has_dp_fem_back_sprite = Column(Boolean, nullable=False)

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

class TypeEfficacy(TableBase):
    __tablename__ = 'type_efficacy'
    damage_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False)
    target_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False)
    damage_factor = Column(Integer, nullable=False)

class Type(TableBase):
    __tablename__ = 'types'
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
EvolutionChain.growth_rate = relation(GrowthRate, backref='evolution_chains')
Pokemon.abilities = relation(Ability, secondary=PokemonAbility.__table__,
                                      order_by=PokemonAbility.slot,
                                      backref='pokemon')
Pokemon.dex_numbers = relation(PokemonDexNumber, backref='pokemon')
Pokemon.egg_groups = relation(EggGroup, secondary=PokemonEggGroup.__table__,
                                        order_by=PokemonEggGroup.egg_group_id,
                                        backref='pokemon')
Pokemon.evolution_chain = relation(EvolutionChain, backref='pokemon')
Pokemon.flavor_text = relation(PokemonFlavorText, backref='pokemon')
Pokemon.foreign_names = relation(PokemonName, backref='pokemon')
Pokemon.generation = relation(Generation, backref='pokemon')
Pokemon.shape = relation(PokemonShape, backref='pokemon')
Pokemon.stats = relation(PokemonStat, backref='pokemon')
Pokemon.types = relation(Type, secondary=PokemonType.__table__)

PokemonDexNumber.generation = relation(Generation)

PokemonFlavorText.version = relation(Version)

PokemonName.language = relation(Language)

PokemonStat.stat = relation(Stat)

Type.damage_efficacies = relation(TypeEfficacy,
                                  primaryjoin=Type.id
                                      ==TypeEfficacy.damage_type_id,
                                  backref='damage_type')
Type.target_efficacies = relation(TypeEfficacy,
                                  primaryjoin=Type.id
                                      ==TypeEfficacy.target_type_id,
                                  backref='target_type')
