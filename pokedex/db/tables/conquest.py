# encoding: utf8

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.orm import backref, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.types import Boolean, Integer, Unicode, UnicodeText

from pokedex.db.tables.base import TableBase, create_translation_table
from pokedex.db.tables.core import (
    Move, Type, Ability, PokemonSpecies, Gender, Item)

from pokedex.db import markdown

class ConquestEpisode(TableBase):
    u"""An episode from Pokémon Conquest: one of a bunch of mini-stories
    featuring a particular warrior.

    The main story, "The Legend of Ransei", also counts, even though it's not
    in the episode select menu and there's no way to replay it.
    """
    __tablename__ = 'conquest_episodes'
    __singlename__ = 'episode'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this episode.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this episode.',
        info=dict(format='identifier'))

create_translation_table('conquest_episode_names', ConquestEpisode, 'names',
    relation_lazy='joined',
    name=Column(Unicode(79), nullable=False, index=True,
        doc=u'The name.',
        info=dict(format='plaintext', official=True))
)

class ConquestEpisodeWarrior(TableBase):
    u"""A warrior featured in an episode in Pokémon Conquest.

    This needs its own table because of the player having two episodes and
    there being two players.
    """
    __tablename__ = 'conquest_episode_warriors'
    episode_id = Column(Integer, ForeignKey('conquest_episodes.id'), primary_key=True,
        doc=u'The ID of the episode.')
    warrior_id = Column(Integer, ForeignKey('conquest_warriors.id'), primary_key=True,
        doc=u'The ID of the warrior.')

class ConquestKingdom(TableBase):
    u"""A kingdom in Pokémon Conquest."""
    __tablename__ = 'conquest_kingdoms'
    __singlename__ = 'kingdom'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u"An ID for this kingdom.")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"A readable identifier for this kingdom.",
        info=dict(format='identifier'))
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        doc=u"The type associated with this kingdom in-game.")

create_translation_table('conquest_kingdom_names', ConquestKingdom, 'names',
    relation_lazy='joined',
    name=Column(Unicode(79), nullable=False, index=True,
        doc=u'The name.',
        info=dict(format='plaintext', official=True))
)

class ConquestMaxLink(TableBase):
    u"""The maximum link a warrior rank can reach with a Pokémon in Pokémon Conquest."""
    __tablename__ = 'conquest_max_links'
    warrior_rank_id = Column(Integer, ForeignKey('conquest_warrior_ranks.id'), primary_key=True,
        doc=u"The ID of the warrior rank.")
    pokemon_species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True,
        doc=u'The ID of the Pokémon species.')
    max_link = Column(Integer, nullable=False,
        doc=u'The maximum link percentage this warrior rank and Pokémon can reach.')

class ConquestMoveData(TableBase):
    u"""Data about a move in Pokémon Conquest."""
    __tablename__ = 'conquest_move_data'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, autoincrement=False,
        doc=u'The ID of the move.')
    power = Column(Integer, nullable=True,
        doc=u"The move's power, null if it does no damage.")
    accuracy = Column(Integer, nullable=True,
        doc=u"The move's base accuracy, null if it is self-targeted or never misses.")
    effect_chance = Column(Integer, nullable=True,
        doc=u"The chance as a percentage that the move's secondary effect will trigger.")
    effect_id = Column(Integer, ForeignKey('conquest_move_effects.id'), nullable=False,
        doc=u"The ID of the move's effect.")
    range_id = Column(Integer, ForeignKey('conquest_move_ranges.id'), nullable=False,
        doc=u"The ID of the move's range.")
    displacement_id = Column(Integer, ForeignKey('conquest_move_displacements.id'), nullable=True,
        doc=u"The ID of the move's displacement.")

    @property
    def star_rating(self):
        """Return the move's in-game power rating as a number of stars."""
        if not self.power:
            return 0
        else:
            stars = (self.power - 1) // 10
            stars = min(stars, 5)  # i.e. maximum of 5 stars
            stars = max(stars, 1)  # And minimum of 1
            return stars

class ConquestMoveDisplacement(TableBase):
    u"""A way in which a move can cause the user or target to move to a
    different tile.

    If a move displaces its user, the move's range is relative to the user's
    original position.
    """
    __tablename__ = 'conquest_move_displacements'
    __singlename__ = 'move_displacement'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this displacement.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this displacement.',
        info=dict(format='identifier'))
    affects_target = Column(Boolean, nullable=False,
        doc=u'True iff the move displaces its target(s) and not its user.')

create_translation_table('conquest_move_displacement_prose', ConquestMoveDisplacement, 'prose',
    name = Column(Unicode(79), nullable=True,
        doc=u'A name for the displacement.',
        info=dict(format='plaintext')),
    short_effect = Column(UnicodeText, nullable=True,
        doc=u"A short summary of how the displacement works, to be used in the move's short effect.",
        info=dict(format='markdown')),
    effect = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of how the displacement works, to be used alongside the move's long effect.",
        info=dict(format='markdown')),
)

class ConquestMoveEffect(TableBase):
    u"""An effect moves can have in Pokémon Conquest."""
    __tablename__ = 'conquest_move_effects'
    __singlename__ = 'conquest_move_effect'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this effect.')

create_translation_table('conquest_move_effect_prose', ConquestMoveEffect, 'prose',
    short_effect = Column(UnicodeText, nullable=True,
        doc=u"A short summary of the effect",
        info=dict(format='markdown')),
    effect = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of the effect",
        info=dict(format='markdown')),
)

class ConquestMoveRange(TableBase):
    u"""A set of tiles moves can target in Pokémon Conquest."""
    __tablename__ = 'conquest_move_ranges'
    __singlename__ = 'conquest_move_range'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this range.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this range.',
        info=dict(format='identifier'))
    targets = Column(Integer, nullable=False,
        doc=u'The number of tiles this range targets.')

create_translation_table('conquest_move_range_prose', ConquestMoveRange, 'prose',
    name = Column(Unicode(79), nullable=True,
        doc=u"A short name briefly describing the range",
        info=dict(format='plaintext')),
    description = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of the range",
        info=dict(format='plaintext')),
)

class ConquestPokemonAbility(TableBase):
    u"""An ability a Pokémon species has in Pokémon Conquest."""
    __tablename__ = 'conquest_pokemon_abilities'
    pokemon_species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the Pokémon species with this ability.')
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"The order abilities are listed in.  Upon evolution, if a Pokémon's abilities change, it will receive the one in the same slot.")
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False,
        doc=u'The ID of the ability.')

class ConquestPokemonEvolution(TableBase):
    u"""The conditions under which a Pokémon must successfully complete an
    action to evolve in Pokémon Conquest.

    Any condition may be null if it does not apply for a particular Pokémon.
    """
    __tablename__ = 'conquest_pokemon_evolution'
    evolved_species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, nullable=False,
        doc=u"The ID of the post-evolution species.")
    required_stat_id = Column(Integer, ForeignKey('conquest_stats.id'), nullable=True,
        doc=u"The ID of the stat which minimum_stat applies to.")
    minimum_stat = Column(Integer, nullable=True,
        doc=u"The minimum value the Pokémon must have in a particular stat.")
    minimum_link = Column(Integer, nullable=True,
        doc=u"The minimum link percentage the Pokémon must have with its warrior.")
    kingdom_id = Column(Integer, ForeignKey('conquest_kingdoms.id'), nullable=True,
        doc=u"The ID of the kingdom in which this Pokémon must complete an action after meeting all other requirements.")
    warrior_gender_id = Column(Integer, ForeignKey('genders.id'), nullable=True,
        doc=u"The ID of the gender the Pokémon's warrior must be.")
    item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        doc=u"The ID of the item the Pokémon's warrior must have equipped.")
    recruiting_ko_required = Column(Boolean, nullable=False,
        doc=u"If true, the Pokémon must KO a Pokémon under the right conditions to recruit that Pokémon's warrior.")

class ConquestPokemonMove(TableBase):
    u"""A Pokémon's move in Pokémon Conquest.

    Yes, "move"; each Pokémon has exactly one.
    """
    __tablename__ = 'conquest_pokemon_moves'
    pokemon_species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, autoincrement=False,
        doc=u'The ID of the Pokémon species.')
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False,
        doc=u'The ID of the move.')

class ConquestPokemonStat(TableBase):
    u"""A Pokémon's base stat in Pokémon Conquest.

    The main four base stats in Conquest are derived from level 100 stats in
    the main series (ignoring effort, genes, and natures).  Attack matches
    either Attack or Special Attack, and Defense matches the average of Defense
    and Special Defense.  HP and Speed are the same.
    """
    __tablename__ = 'conquest_pokemon_stats'
    pokemon_species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, autoincrement=False,
        doc=u'The ID of the Pokémon species.')
    conquest_stat_id = Column(Integer, ForeignKey('conquest_stats.id'), primary_key=True, autoincrement=False,
        doc=u'The ID of the stat.')
    base_stat = Column(Integer, nullable=False,
        doc=u'The base stat.')

class ConquestStat(TableBase):
    u"""A stat Pokémon have in Pokémon Conquest."""
    __tablename__ = 'conquest_stats'
    __singlename__ = 'conquest_stat'  # To be safe
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this stat.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this stat.',
        info=dict(format='identifier'))
    is_base = Column(Boolean, nullable=False,
        doc=u'True iff this is one of the main stats, calculated for individual Pokémon.')

create_translation_table('conquest_stat_names', ConquestStat, 'names',
    relation_lazy='joined',
    name=Column(Unicode(79), nullable=False, index=True,
        doc=u'The name.',
        info=dict(format='plaintext', official=True))
)

class ConquestTransformationPokemon(TableBase):
    u"""A Pokémon that satisfies a warrior transformation's link condition.

    If a warrior has one or more Pokémon listed here, they only need to raise
    one of them to the required link.
    """
    __tablename__ = 'conquest_transformation_pokemon'
    transformation_id = Column(Integer, ForeignKey('conquest_warrior_transformation.transformed_warrior_rank_id'), primary_key=True,
        doc=u'The ID of the corresponding transformation, in turn a warrior rank ID.')
    pokemon_species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True,
        doc=u'The ID of the Pokémon species.')

class ConquestTransformationWarrior(TableBase):
    u"""A warrior who must be present in the same nation as another warrior for
    the latter to transform into their next rank.

    If a warrior has one or more other warriors listed here, they *all* need to
    gather in the same nation for the transformation to take place.
    """
    __tablename__ = 'conquest_transformation_warriors'
    transformation_id = Column(Integer, ForeignKey('conquest_warrior_transformation.transformed_warrior_rank_id'), primary_key=True,
        doc=u'The ID of the corresponding transformation, in turn a warrior rank ID.')
    present_warrior_id = Column(Integer, ForeignKey('conquest_warriors.id'), primary_key=True,
        doc=u'The ID of the other warrior who must be present.')

class ConquestWarrior(TableBase):
    u"""A warrior in Pokémon Conquest."""
    __tablename__ = 'conquest_warriors'
    __singlename__ = 'warrior'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
        doc=u'An ID for this warrior.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this warrior.',
        info=dict(format='identifier'))
    gender_id = Column(Integer, ForeignKey('genders.id'), nullable=False,
        doc=u"The ID of the warrior's gender.")
    archetype_id = Column(Integer, ForeignKey('conquest_warrior_archetypes.id'), nullable=True,
        doc=u"The ID of this warrior's archetype.  Null for unique warriors.")

create_translation_table('conquest_warrior_names', ConquestWarrior, 'names',
    relation_lazy='joined',
    name=Column(Unicode(79), nullable=False, index=True,
        doc=u'The name.',
        info=dict(format='plaintext', official=True))
)

class ConquestWarriorArchetype(TableBase):
    u"""An archetype that generic warriors in Pokémon Conquest can have.  All
    warriors of a particular archetype share sprites and dialogue.

    Some of these are unused as warriors because they exist only as NPCs.  They
    should still be kept because we have their sprites and may eventually get
    their dialogue.
    """
    __tablename__ = 'conquest_warrior_archetypes'
    __singlename__ = 'archetype'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this archetype.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier describing this archetype.',
        info=dict(format='identifier'))

class ConquestWarriorRank(TableBase):
    u"""A warrior at a particular rank in Pokémon Conquest.

    These are used for whatever changes between ranks, much like Pokémon forms.
    Generic warriors who have only one rank are also represented here, with a
    single row.

    To clarify, each warrior's ranks are individually called "warrior ranks"
    here; for example, "Rank 2 Nobunaga" is an example of a warrior rank, not
    just "Rank 2".
    """
    __tablename__ = 'conquest_warrior_ranks'
    __singlename__ = 'warrior_rank'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this warrior rank.')
    warrior_id = Column(Integer, ForeignKey('conquest_warriors.id'), nullable=False,
        doc=u'The ID of the warrior.')
    rank = Column(Integer, nullable=False,
        doc=u'The rank number.')
    skill_id = Column(Integer, ForeignKey('conquest_warrior_skills.id'), nullable=False,
        doc=u"The ID of this warrior rank's warrior skill.")

    __table_args__ = (
        UniqueConstraint(warrior_id, rank),
        {},
    )

class ConquestWarriorRankStatMap(TableBase):
    u"""Any of a warrior rank's warrior stats in Pokémon Conquest."""
    __tablename__ = 'conquest_warrior_rank_stat_map'
    warrior_rank_id = Column(Integer, ForeignKey('conquest_warrior_ranks.id'), primary_key=True, autoincrement=False,
        doc=u'The ID of the warrior rank.')
    warrior_stat_id = Column(Integer, ForeignKey('conquest_warrior_stats.id'), primary_key=True, autoincrement=False,
        doc=u'The ID of the warrior stat.')
    base_stat = Column(Integer, nullable=False,
        doc=u'The stat.')

class ConquestWarriorSkill(TableBase):
    u"""A warrior skill in Pokémon Conquest."""
    __tablename__ = 'conquest_warrior_skills'
    __singlename__ = 'skill'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
        doc=u'An ID for this skill.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this skill.',
        info=dict(format='identifier'))

create_translation_table('conquest_warrior_skill_names', ConquestWarriorSkill, 'names',
    relation_lazy='joined',
    name=Column(Unicode(79), nullable=False, index=True,
        doc=u'The name.',
        info=dict(format='plaintext', official=True))
)

class ConquestWarriorSpecialty(TableBase):
    u"""A warrior's specialty types in Pokémon Conquest.

    These have no actual effect on gameplay; they just indicate which types of
    Pokémon each warrior generally has strong maximum links with.
    """
    __tablename__ = 'conquest_warrior_specialties'
    warrior_id = Column(Integer, ForeignKey('conquest_warriors.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the warrior.')
    type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the type.')
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"The order in which the warrior's types are listed.")

class ConquestWarriorStat(TableBase):
    u"""A stat that warriors have in Pokémon Conquest."""
    __tablename__ = 'conquest_warrior_stats'
    __singlename__ = 'warrior_stat'
    id = Column(Integer, primary_key=True, autoincrement=True,
        doc=u'An ID for this stat.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this stat.',
        info=dict(format='identifier'))

create_translation_table('conquest_warrior_stat_names', ConquestWarriorStat, 'names',
    relation_lazy='joined',
    name=Column(Unicode(79), nullable=False, index=True,
        doc=u'The name.',
        info=dict(format='plaintext', official=True))
)

class ConquestWarriorTransformation(TableBase):
    u"""The conditions under which a warrior must perform an action in order
    to transform to the next rank.

    Or most of them, anyway.  See also ConquestTransformationPokemon and
    ConquestTransformationWarrior.
    """
    __tablename__ = 'conquest_warrior_transformation'
    transformed_warrior_rank_id = Column(Integer, ForeignKey('conquest_warrior_ranks.id'), primary_key=True,
        doc=u'The ID of the post-transformation warrior rank.')
    is_automatic = Column(Boolean, nullable=False,
        doc=u'True iff the transformation happens automatically in the story with no further requirements.')
    required_link = Column(Integer, nullable=True,
        doc=u'The link percentage the warrior must reach with one of several specific Pokémon, if any.')
    completed_episode_id = Column(Integer, ForeignKey('conquest_episodes.id'), nullable=True,
        doc=u'The ID of the episode the player must have completed, if any.')
    current_episode_id = Column(Integer, ForeignKey('conquest_episodes.id'), nullable=True,
        doc=u'The ID of the episode the player must currently be playing, if any.')
    distant_warrior_id = Column(Integer, ForeignKey('conquest_warriors.id'), nullable=True,
        doc=u'The ID of another warrior who must be in the army, but not in the same kingdom or in any adjacent kingdom.')
    female_warlord_count = Column(Integer, nullable=True,
        doc=u'The number of female warlords who must be in the same nation.')
    pokemon_count = Column(Integer, nullable=True,
        doc=u'The number of Pokémon that must be registered in the gallery.')
    collection_type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        doc=u'The ID of a type all Pokémon of which must be registered in the gallery.')
    warrior_count = Column(Integer, nullable=True,
        doc=u'The number of warriors that must be registered in the gallery.')


### Relationships down here, to avoid dependency ordering problems

ConquestEpisode.warriors = relationship(ConquestWarrior,
    secondary=ConquestEpisodeWarrior.__table__,
    innerjoin=True,
    backref='episodes')

ConquestKingdom.type = relationship(Type,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref=backref('conquest_kingdom', uselist=False))

ConquestMaxLink.pokemon = relationship(PokemonSpecies,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref=backref('conquest_max_links', lazy='dynamic',
                    order_by=ConquestMaxLink.warrior_rank_id))
ConquestMaxLink.warrior_rank = relationship(ConquestWarriorRank,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref=backref('max_links', lazy='dynamic'))
ConquestMaxLink.warrior = association_proxy('warrior_rank', 'warrior')

ConquestMoveData.move_displacement = relationship(ConquestMoveDisplacement,
    uselist=False,
    backref='move_data')
ConquestMoveData.move = relationship(Move,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref=backref('conquest_data', uselist=False))
ConquestMoveData.move_effect = relationship(ConquestMoveEffect,
    innerjoin=True, lazy='joined',
    backref='move_data')
ConquestMoveData.range = relationship(ConquestMoveRange,
    innerjoin=True, lazy='joined',
    backref='move_data')

ConquestMoveData.effect = markdown.MoveEffectProperty('effect')
ConquestMoveData.effect_map = markdown.MoveEffectPropertyMap('effect_map')
ConquestMoveData.short_effect = markdown.MoveEffectProperty('short_effect')
ConquestMoveData.short_effect_map = markdown.MoveEffectPropertyMap('short_effect_map')
ConquestMoveData.displacement = markdown.MoveEffectProperty('effect', relationship='move_displacement')

ConquestPokemonEvolution.gender = relationship(Gender,
    backref='conquest_evolutions')
ConquestPokemonEvolution.item = relationship(Item,
    backref='conquest_evolutions')
ConquestPokemonEvolution.kingdom = relationship(ConquestKingdom,
    backref='evolutions')
ConquestPokemonEvolution.stat = relationship(ConquestStat,
    backref='evolutions')

ConquestPokemonStat.pokemon = relationship(PokemonSpecies,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref='conquest_stats')
ConquestPokemonStat.stat = relationship(ConquestStat,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref='pokemon_stats')

ConquestWarrior.archetype = relationship(ConquestWarriorArchetype,
    uselist=False,
    backref=backref('warriors'))
ConquestWarrior.ranks = relationship(ConquestWarriorRank,
    order_by=ConquestWarriorRank.rank,
    innerjoin=True,
    backref=backref('warrior', uselist=False))
ConquestWarrior.types = relationship(Type,
    secondary=ConquestWarriorSpecialty.__table__,
    order_by=ConquestWarriorSpecialty.slot,
    innerjoin=True,
    backref='conquest_warriors')

ConquestWarriorRank.skill = relationship(ConquestWarriorSkill,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref=backref('warrior_ranks', order_by=ConquestWarriorRank.id))
ConquestWarriorRank.stats = relationship(ConquestWarriorRankStatMap,
    innerjoin=True,
    order_by=ConquestWarriorRankStatMap.warrior_stat_id,
    backref=backref('warrior_rank', uselist=False, innerjoin=True, lazy='joined'))

ConquestWarriorRankStatMap.stat = relationship(ConquestWarriorStat,
    innerjoin=True, lazy='joined',
    uselist=False,
    backref='stat_map')

ConquestWarriorTransformation.completed_episode = relationship(ConquestEpisode,
    primaryjoin=ConquestWarriorTransformation.completed_episode_id==ConquestEpisode.id,
    uselist=False)
ConquestWarriorTransformation.current_episode = relationship(ConquestEpisode,
    primaryjoin=ConquestWarriorTransformation.current_episode_id==ConquestEpisode.id,
    uselist=False)
ConquestWarriorTransformation.distant_warrior = relationship(ConquestWarrior,
    uselist=False)
ConquestWarriorTransformation.pokemon = relationship(PokemonSpecies,
    secondary=ConquestTransformationPokemon.__table__,
    order_by=PokemonSpecies.conquest_order)
ConquestWarriorTransformation.present_warriors = relationship(ConquestWarrior,
    secondary=ConquestTransformationWarrior.__table__,
    order_by=ConquestWarrior.id)
ConquestWarriorTransformation.type = relationship(Type,
    uselist=False)
ConquestWarriorTransformation.warrior_rank = relationship(ConquestWarriorRank,
    uselist=False,
    innerjoin=True, lazy='joined',
    backref=backref('transformation', uselist=False, innerjoin=True))


PokemonSpecies.conquest_abilities = relationship(Ability,
    secondary=ConquestPokemonAbility.__table__,
    order_by=ConquestPokemonAbility.slot,
    backref=backref('conquest_pokemon', order_by=PokemonSpecies.conquest_order,
                    innerjoin=True))
PokemonSpecies.conquest_move = relationship(Move,
    secondary=ConquestPokemonMove.__table__,
    uselist=False,
    backref=backref('conquest_pokemon', order_by=PokemonSpecies.conquest_order))
PokemonSpecies.conquest_evolution = relationship(ConquestPokemonEvolution,
    uselist=False,
    backref=backref('evolved_species', innerjoin=True, lazy='joined', uselist=False))
