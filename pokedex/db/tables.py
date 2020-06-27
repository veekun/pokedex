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
# XXX: Check if "gametext" is set correctly everywhere

from functools import partial
import six

from sqlalchemy import Column, ForeignKey, MetaData, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import and_
from sqlalchemy.types import Boolean, Enum, Integer, SmallInteger, Unicode, UnicodeText

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

        pk = u', '.join(six.text_type(getattr(self, column.name))
            for column in pk_constraint.columns)
        try:
            return u"<%s object (%s): %s>" % (typename, pk, self.identifier)
        except AttributeError:
            return u"<%s object (%s)>" % (typename, pk)

    def __str__(self):
        if six.PY2:
            return six.text_type(self).encode('utf8')
        else:
            return type(self).__unicode__(self)

    def __repr__(self):
        return str(self)

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
    u"""A language the Pokémon games have been translated into."""
    __tablename__ = 'languages'
    __singlename__ = 'language'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    iso639 = Column(Unicode(79), nullable=False,
        doc=u"The two-letter code of the language. Note that it is not unique.",
        info=dict(format='identifier'))
    iso3166 = Column(Unicode(79), nullable=False,
        doc=u"The two-letter code of the country where this language is spoken. Note that it is not unique.",
        info=dict(format='identifier'))
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    official = Column(Boolean, nullable=False, index=True,
        doc=u"True iff games are produced in the language.")
    order = Column(Integer, nullable=True,
        doc=u"Order for sorting in foreign name lists.")

create_translation_table = partial(multilang.create_translation_table, language_class=Language)

create_translation_table('language_names', Language, 'names',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

### The actual tables

class Ability(TableBase):
    u"""An ability a Pokémon can have, such as Static or Pressure.

    IDs below 10000 match the internal ID in the games.
    IDs above 10000 are reserved for Conquest-only abilities.
    """
    __tablename__ = 'abilities'
    __singlename__ = 'ability'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        doc=u"The ID of the generation this ability was introduced in")
    is_main_series = Column(Boolean, nullable=False, index=True,
        doc=u"True iff the ability exists in the main series.")

create_translation_table('ability_names', Ability, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True, ripped=True)),
)
create_translation_table('ability_prose', Ability, 'prose',
    short_effect = Column(UnicodeText, nullable=True,
        doc=u"A short summary of this ability's effect",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
    effect = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of this ability's effect",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
)

class AbilityChangelog(TableBase):
    """History of changes to abilities across main game versions."""
    __tablename__ = 'ability_changelog'
    __singlename__ = 'ability_changelog'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"This change's unique ID")
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False,
        doc=u"The ID of the ability that changed")
    changed_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        doc=u"The ID of the version group in which the ability changed")

create_translation_table('ability_changelog_prose', AbilityChangelog, 'prose',
    effect = Column(UnicodeText, nullable=False,
        doc=u"A description of the old behavior",
        info=dict(format='markdown', string_getter=markdown.MarkdownString))
)

class AbilityFlavorText(TableBase):
    u"""In-game flavor text of an ability."""
    __tablename__ = 'ability_flavor_text'
    ability_id = Column(Integer, ForeignKey('abilities.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the ability")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the version group this flavor text is taken from")
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False,
        doc=u"The language")
    flavor_text = Column(UnicodeText, nullable=False,
        doc=u"The actual flavor text",
        info=dict(official=True, format='gametext'))

class Berry(TableBase):
    u"""A Berry, consumable item that grows on trees.

    For data common to all items, such as the name, see the corresponding item entry.

    ID matches the in-game berry number.
    """
    __tablename__ = 'berries'
    id = Column(Integer, primary_key=True, nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False,
        doc=u"The ID of the item that represents this Berry")
    firmness_id = Column(Integer, ForeignKey('berry_firmness.id'), nullable=False,
        doc=u"The ID of this Berry's firmness category")
    natural_gift_power = Column(Integer, nullable=True,
        doc=u"Natural Gift's power when used with this Berry")
    natural_gift_type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        doc=u"The ID of the Type that Natural Gift has when used with this Berry")
    size = Column(Integer, nullable=False,
        doc=u"The size of this Berry, in millimeters")
    max_harvest = Column(Integer, nullable=False,
        doc=u"The maximum number of these berries that can grow on one tree in Generation IV")
    growth_time = Column(Integer, nullable=False,
        doc=u"Time it takes the tree to grow one stage, in hours.  Berry trees go through four of these growth stages before they can be picked.")
    soil_dryness = Column(Integer, nullable=False,
        doc=u"The speed at which this Berry dries out the soil as it grows.  A higher rate means the soil dries more quickly.")
    smoothness = Column(Integer, nullable=False,
        doc=u"The smoothness of this Berry, used in making Pokéblocks or Poffins")

class BerryFirmness(TableBase):
    u"""A Berry firmness, such as "hard" or "very soft". """
    __tablename__ = 'berry_firmness'
    __singlename__ = 'berry_firmness'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this firmness")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('berry_firmness_names', BerryFirmness, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class BerryFlavor(TableBase):
    u"""A Berry flavor level."""
    __tablename__ = 'berry_flavors'
    berry_id = Column(Integer, ForeignKey('berries.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the berry")
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the flavor")
    flavor = Column(Integer, nullable=False,
        doc=u"The level of the flavor in the berry")

class Characteristic(TableBase):
    u"""Flavor text hinting at genes that appears in a Pokémon's summary."""
    __tablename__ = 'characteristics'
    __singlename__ = 'characteristic'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False,
        doc=u"ID of the stat with the highest gene")
    gene_mod_5 = Column(Integer, nullable=False, index=True,
        doc=u"Value of the highest gene modulo 5")

create_translation_table('characteristic_text', Characteristic, 'text',
    relation_lazy='joined',
    message = Column(Unicode(79), nullable=False, index=True,
        doc=u"The text displayed",
        info=dict(official=True, format='plaintext')),
)

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

class ContestCombo(TableBase):
    u"""Combo of two moves in a Contest."""
    __tablename__ = 'contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the first move in the combo")
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the second and final move in the combo")

class ContestEffect(TableBase):
    u"""Effect of a move when used in a Contest."""
    __tablename__ = 'contest_effects'
    __singlename__ = 'contest_effect'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this effect")
    appeal = Column(SmallInteger, nullable=False,
        doc=u"The base number of hearts the user of this move gets")
    jam = Column(SmallInteger, nullable=False,
        doc=u"The base number of hearts the user's opponent loses")

create_translation_table('contest_effect_prose', ContestEffect, 'prose',
    flavor_text = Column(UnicodeText, nullable=True,
        doc=u"The in-game description of this effect",
        info=dict(official=True, format='gametext')),
    effect = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of the effect",
        info=dict(format='plaintext')),
)

class ContestType(TableBase):
    u"""A Contest type, such as "cool" or "smart", and their associated Berry flavors and Pokéblock colors.
    """
    __tablename__ = 'contest_types'
    __singlename__ = 'contest_type'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this Contest type")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('contest_type_names', ContestType, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
    flavor = Column(UnicodeText, nullable=True,
        doc=u"The name of the corresponding Berry flavor",
        info=dict(official=True, format='plaintext')),
    color = Column(UnicodeText, nullable=True,
        doc=u"The name of the corresponding Pokéblock color",
        info=dict(official=True, format='plaintext')),
)

class EggGroup(TableBase):
    u"""An Egg group. Usually, two Pokémon can breed if they share an Egg Group.

    Exceptions:

    Pokémon in the No Eggs group cannot breed.

    Pokemon in the Ditto group can breed with any pokemon
    except those in the Ditto or No Eggs groups.

    ID matches to the internal ID used in the games.
    """
    __tablename__ = 'egg_groups'
    __singlename__ = 'egg_group'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier.",
        info=dict(format='identifier'))

create_translation_table('egg_group_prose', EggGroup, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class Encounter(TableBase):
    u"""Encounters with wild Pokémon.

    Bear with me, here.

    Within a given area in a given game, encounters are differentiated by the
    "slot" they are in and the state of the game world.

    What the player is doing to get an encounter, such as surfing or walking
    through tall grass, is called a method.  Each method has its own set of
    encounter slots.

    Within a method, slots are defined primarily by rarity.  Each slot can
    also be affected by world conditions; for example, the 20% slot for walking
    in tall grass is affected by whether a swarm is in effect in that area.
    "Is there a swarm?" is a condition; "there is a swarm" and "there is not a
    swarm" are the possible values of this condition.

    A slot (20% walking in grass) and any appropriate world conditions (no
    swarm) are thus enough to define a specific encounter.
    """

    __tablename__ = 'encounters'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this encounter")
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False, autoincrement=False,
        doc=u"The ID of the version this applies to")
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), nullable=False, autoincrement=False,
        doc=u"The ID of the location of this encounter")
    encounter_slot_id = Column(Integer, ForeignKey('encounter_slots.id'), nullable=False, autoincrement=False,
        doc=u"The ID of the encounter slot, which determines method and rarity")
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False,
        doc=u"The ID of the encountered Pokémon")
    min_level = Column(Integer, nullable=False, autoincrement=False,
        doc=u"The minimum level of the encountered Pokémon")
    max_level = Column(Integer, nullable=False, autoincrement=False,
        doc=u"The maximum level of the encountered Pokémon")

class EncounterCondition(TableBase):
    u"""A condition in the game world that affects Pokémon encounters, such as time of day."""

    __tablename__ = 'encounter_conditions'
    __singlename__ = 'encounter_condition'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this condition")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('encounter_condition_prose', EncounterCondition, 'prose',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class EncounterConditionValue(TableBase):
    u"""A possible state for a condition.

    For example, the state of 'swarm' could be 'swarm' or 'no swarm'.
    """

    __tablename__ = 'encounter_condition_values'
    __singlename__ = 'encounter_condition_value'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    encounter_condition_id = Column(Integer, ForeignKey('encounter_conditions.id'), primary_key=False, nullable=False, autoincrement=False,
        doc=u"The ID of the encounter condition this is a value of")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    is_default = Column(Boolean, nullable=False,
        doc=u'Set if this value is the default state for the condition')

create_translation_table('encounter_condition_value_prose', EncounterConditionValue, 'prose',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class EncounterConditionValueMap(TableBase):
    u"""Maps encounters to the specific conditions under which they occur."""
    __tablename__ = 'encounter_condition_value_map'
    encounter_id = Column(Integer, ForeignKey('encounters.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the encounter")
    encounter_condition_value_id = Column(Integer, ForeignKey('encounter_condition_values.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the encounter condition value")

class EncounterMethod(TableBase):
    u"""A way the player can enter a wild encounter.

    For example, surfing, fishing, or walking through tall grass.
    """

    __tablename__ = 'encounter_methods'
    __singlename__ = 'encounter_method'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for the method")
    identifier = Column(Unicode(79), nullable=False, unique=True,
        doc=u"An identifier",
        info=dict(format='identifier'))
    order = Column(Integer, unique=True, nullable=False,
        doc=u"A good column for sorting on")

create_translation_table('encounter_method_prose', EncounterMethod, 'prose',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class EncounterSlot(TableBase):
    u"""An abstract "slot" within a method, associated with both some set of conditions and a rarity.

    "slot" has a very specific meaning:
    If during gameplay you know sufficient details about the current game state,
    you can predict which slot (and therefore which pokemon) will spawn.

    There are currently two reasons that "slot" might be empty:
    1) The slot corresponds to a gift pokemon.
    2) Red/Blue's Super Rod slots, which don't correspond to in-game slots.
       See https://github.com/veekun/pokedex/issues/166#issuecomment-220101455
    """

    __tablename__ = 'encounter_slots'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this slot")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, autoincrement=False,
        doc=u"The ID of the version group this slot is in")
    encounter_method_id = Column(Integer, ForeignKey('encounter_methods.id'), primary_key=False, nullable=False, autoincrement=False,
        doc=u"The ID of the method")
    slot = Column(Integer, nullable=True,
        doc=u"This slot's order for the location and method")
    rarity = Column(Integer, nullable=True,
        doc=u"The chance of the encounter as a percentage")

class EvolutionChain(TableBase):
    u"""A family of Pokémon that are linked by evolution."""
    __tablename__ = 'evolution_chains'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    baby_trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        doc=u"Item that a parent must hold while breeding to produce a baby")

class EvolutionTrigger(TableBase):
    u"""An evolution type, such as "level" or "trade". """
    __tablename__ = 'evolution_triggers'
    __singlename__ = 'evolution_trigger'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('evolution_trigger_prose', EvolutionTrigger, 'prose',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class Experience(TableBase):
    u"""EXP needed for a certain level with a certain growth rate."""
    __tablename__ = 'experience'
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), primary_key=True, nullable=False,
        doc=u"ID of the growth rate")
    level = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"The level")
    experience = Column(Integer, nullable=False,
        doc=u"The number of EXP points needed to get to that level")

class Gender(TableBase):
    u"""A gender."""
    __tablename__ = 'genders'
    __singlename__ = 'gender'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
        doc=u'An ID for this gender.')
    identifier = Column(Unicode(79), nullable=False,
        doc=u'A readable identifier for this gender.',
        info=dict(format='identifier'))

class Generation(TableBase):
    u"""A Generation of the Pokémon franchise."""
    __tablename__ = 'generations'
    __singlename__ = 'generation'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    main_region_id = Column(Integer, ForeignKey('regions.id'), nullable=False,
        doc=u"ID of the region this generation's main games take place in")
    identifier = Column(Unicode(79), nullable=False,
        doc=u'An identifier',
        info=dict(format='identifier'))

create_translation_table('generation_names', Generation, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class GrowthRate(TableBase):
    u"""Growth rate of a Pokémon, i.e. the EXP → level function. """
    __tablename__ = 'growth_rates'
    __singlename__ = 'growth_rate'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    formula = Column(UnicodeText, nullable=False,
        doc=u"The formula",
        info=dict(format='latex'))

create_translation_table('growth_rate_prose', GrowthRate, 'prose',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class Item(TableBase):
    u"""An Item from the games, like "Poké Ball" or "Bicycle".

    IDs do not mean anything; see ItemGameIndex for the IDs used in the games.
    """
    __tablename__ = 'items'
    __singlename__ = 'item'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    category_id = Column(Integer, ForeignKey('item_categories.id'), nullable=False,
        doc=u"ID of a category this item belongs to")
    cost = Column(Integer, nullable=False,
        doc=u"Cost of the item when bought. Items sell for half this price.")
    fling_power = Column(Integer, nullable=True,
        doc=u"Power of the move Fling when used with this item.")
    fling_effect_id = Column(Integer, ForeignKey('item_fling_effects.id'), nullable=True,
        doc=u"ID of the fling-effect of the move Fling when used with this item. Note that these are different from move effects.")

    @property
    def appears_underground(self):
        u"""True if the item appears underground, as specified by the appropriate flag."""
        return any(flag.identifier == u'underground' for flag in self.flags)

create_translation_table('item_names', Item, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True, ripped=True)),
)
create_translation_table('item_prose', Item, 'prose',
    short_effect = Column(UnicodeText, nullable=True,
        doc=u"A short summary of the effect",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
    effect = Column(UnicodeText, nullable=True,
        doc=u"Detailed description of the item's effect.",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
)
create_translation_table('item_flavor_summaries', Item, 'flavor_summaries',
    flavor_summary = Column(UnicodeText, nullable=True,
        doc=u"Text containing facts from all flavor texts, for languages without official game translations",
        info=dict(official=False, format='plaintext', ripped=True)),
)

class ItemCategory(TableBase):
    u"""An item category.  Not official."""
    __tablename__ = 'item_categories'
    __singlename__ = 'item_category'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    pocket_id = Column(Integer, ForeignKey('item_pockets.id'), nullable=False,
        doc=u"ID of the pocket these items go to")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('item_category_prose', ItemCategory, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class ItemFlag(TableBase):
    u"""An item attribute such as "consumable" or "holdable".  Not official. """
    __tablename__ = 'item_flags'
    __singlename__ = 'item_flag'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"Identifier of the flag",
        info=dict(format='identifier'))

create_translation_table('item_flag_prose', ItemFlag, 'prose',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    description = Column(UnicodeText, nullable=True,
        doc=u"Short description of the flag",
        info=dict(format='plaintext')),
)

class ItemFlagMap(TableBase):
    u"""Maps an item flag to its item."""
    __tablename__ = 'item_flag_map'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"The ID of the item")
    item_flag_id = Column(Integer, ForeignKey('item_flags.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"The ID of the item flag")

class ItemFlavorText(TableBase):
    u"""An in-game description of an item."""
    __tablename__ = 'item_flavor_text'
    __singlename__ = 'item_flavor_text'
    summary_column = Item.flavor_summaries_table, 'flavor_summary'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"The ID of the item")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"ID of the version group that sports this text")
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False,
        doc=u"The language")
    flavor_text = Column(UnicodeText, nullable=False,
        doc=u"The flavor text itself",
        info=dict(official=True, format='gametext'))

class ItemFlingEffect(TableBase):
    u"""An effect of the move Fling when used with a specific item."""
    __tablename__ = 'item_fling_effects'
    __singlename__ = 'item_fling_effect'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier of this fling effect",
        info=dict(format='identifier'))

create_translation_table('item_fling_effect_prose', ItemFlingEffect, 'prose',
    effect = Column(UnicodeText, nullable=False,
        doc=u"Description of the effect",
        info=dict(format='plaintext')),
)

class ItemGameIndex(TableBase):
    u"""The internal ID number a game uses for an item."""
    __tablename__ = 'item_game_indices'
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"The database ID of the item")
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"ID of the generation of games")
    game_index = Column(Integer, nullable=False,
        doc=u"Internal ID of the item in the generation")

class ItemPocket(TableBase):
    u"""A pocket that categorizes items.  Semi-offical."""
    __tablename__ = 'item_pockets'
    __singlename__ = 'item_pocket'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier of this pocket",
        info=dict(format='identifier'))

create_translation_table('item_pocket_names', ItemPocket, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class Location(TableBase):
    u"""A place in the Pokémon world."""
    __tablename__ = 'locations'
    __singlename__ = 'location'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    region_id = Column(Integer, ForeignKey('regions.id'),
        doc=u"ID of the region this location is in")
    identifier = Column(Unicode(79), nullable=False, unique=True,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('location_names', Location, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
    subtitle = Column(Unicode(79), nullable=True, index=False,
        doc=u"""A subtitle for the location, if any.
            This may be an alternate name for the locaton, as in the Kalos routes,
            or the name of a subarea of the location, as in Alola.""",
        info=dict(format='plaintext', official=True)),
)

class LocationArea(TableBase):
    u"""A sub-area of a location."""
    __tablename__ = 'location_areas'
    __singlename__ = 'location_area'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False,
        doc=u"ID of the location this area is part of")
    game_index = Column(Integer, nullable=False,
        doc=u"ID the games use for this area")
    identifier = Column(Unicode(79), nullable=True,
        doc=u"An identifier",
        info=dict(format='identifier'))

    __table_args__ = (
        UniqueConstraint(location_id, identifier),
        {},
    )

create_translation_table('location_area_prose', LocationArea, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class LocationAreaEncounterRate(TableBase):
    """The chance of encountering a wild Pokémon in an area.

    In other words, how likely a step in tall grass is to trigger a wild battle.
    The exact meaning of the rate varies across versions but generally higher is
    more likely.
    """
    __tablename__ = 'location_area_encounter_rates'
    location_area_id = Column(Integer, ForeignKey('location_areas.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the area")
    encounter_method_id = Column(Integer, ForeignKey('encounter_methods.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the method")
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, autoincrement=False,
        doc=u"ID of the version")
    rate = Column(Integer, nullable=True,
        doc=u"The base encounter rate")

class LocationGameIndex(TableBase):
    u"""IDs the games use internally for locations."""
    __tablename__ = 'location_game_indices'
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False, primary_key=True,
        doc=u"Database ID of the location")
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False, primary_key=True,
        doc=u"ID of the generation this entry to")
    game_index = Column(Integer, nullable=False, primary_key=True, autoincrement=False,
        doc=u"Internal game ID of the location")

class Machine(TableBase):
    u"""A TM or HM; numbered item that can teach a move to a Pokémon."""
    __tablename__ = 'machines'
    machine_number = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"Number of the machine for TMs, or 100 + the number for HMs")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"Versions this entry applies to")
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False,
        doc=u"ID of the corresponding Item")
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False,
        doc=u"ID of the taught move")

    @property
    def is_hm(self):
        u"""True if this machine is a HM, False if it's a TM."""
        return self.machine_number >= 100

class Move(TableBase):
    u"""A Move: technique or attack a Pokémon can learn to use.

    IDs below 10000 match the internal IDs used in the games.
    IDs above 10000 are reserved for Shadow moves from Colosseum and XD."""
    __tablename__ = 'moves'
    __singlename__ = 'move'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        doc=u"ID of the generation this move first appeared in")
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        doc=u"ID of the move's elemental type")
    power = Column(SmallInteger, nullable=True,
        doc=u"Base power of the move, null if it does not have a set base power.")
    pp = Column(SmallInteger, nullable=True,
        doc=u"Base PP (Power Points) of the move, null if not applicable (e.g. Struggle and Shadow moves).")
    accuracy = Column(SmallInteger, nullable=True,
        doc=u"Accuracy of the move; NULL means it never misses")
    priority = Column(SmallInteger, nullable=False,
        doc=u"The move's priority bracket")
    target_id = Column(Integer, ForeignKey('move_targets.id'), nullable=False,
        doc=u"ID of the target (range) of the move")
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=False,
        doc=u"ID of the damage class (physical/special) of the move")
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=False,
        doc=u"ID of the move's effect")
    effect_chance = Column(Integer, nullable=True,
        doc=u"The chance for a secondary effect. What this is a chance of is specified by the move's effect.")
    contest_type_id = Column(Integer, ForeignKey('contest_types.id'), nullable=True,
        doc=u"ID of the move's Contest type (e.g. cool or smart)")
    contest_effect_id = Column(Integer, ForeignKey('contest_effects.id'), nullable=True,
        doc=u"ID of the move's Contest effect")
    super_contest_effect_id = Column(Integer, ForeignKey('super_contest_effects.id'), nullable=True,
        doc=u"ID of the move's Super Contest effect")

create_translation_table('move_names', Move, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True, ripped=True))
)
create_translation_table('move_flavor_summaries', Move, 'flavor_summaries',
    flavor_summary = Column(UnicodeText, nullable=True,
        doc=u"Text containing facts from all flavor texts, for languages without official game translations",
        info=dict(official=False, format='plaintext', ripped=True)),
)

class MoveBattleStyle(TableBase):
    u"""Battle Palace style.

    See NatureBattleStylePreference.
    """
    __tablename__ = 'move_battle_styles'
    __singlename__ = 'move_battle_style'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('move_battle_style_prose', MoveBattleStyle, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class MoveChangelog(TableBase):
    """History of changes to moves across main game versions."""
    __tablename__ = 'move_changelog'
    __singlename__ = 'move_changelog'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False,
        doc=u"ID of the move that changed")
    changed_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False,
        doc=u"ID of the version group in which the move changed")
    type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        doc=u"Prior type of the move, or NULL if unchanged")
    power = Column(SmallInteger, nullable=True,
        doc=u"Prior base power of the move, or NULL if unchanged")
    pp = Column(SmallInteger, nullable=True,
        doc=u"Prior base PP of the move, or NULL if unchanged")
    accuracy = Column(SmallInteger, nullable=True,
        doc=u"Prior accuracy of the move, or NULL if unchanged")
    priority = Column(SmallInteger, nullable=True,
        doc=u"Prior priority of the move, or NULL if unchanged")
    target_id = Column(Integer, ForeignKey('move_targets.id'), nullable=True,
        doc=u"Prior ID of the target, or NULL if unchanged")
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=True,
        doc=u"Prior ID of the effect, or NULL if unchanged")
    effect_chance = Column(Integer, nullable=True,
        doc=u"Prior effect chance, or NULL if unchanged")

class MoveDamageClass(TableBase):
    u"""Any of the damage classes moves can have, i.e. physical, special, or non-damaging."""
    __tablename__ = 'move_damage_classes'
    __singlename__ = 'move_damage_class'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('move_damage_class_prose', MoveDamageClass, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    description = Column(UnicodeText, nullable=True,
        doc=u"A description of the class",
        info=dict(format='plaintext')),
)

class MoveEffect(TableBase):
    u"""An effect of a move."""
    __tablename__ = 'move_effects'
    __singlename__ = 'move_effect'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")

create_translation_table('move_effect_prose', MoveEffect, 'prose',
    short_effect = Column(UnicodeText, nullable=True,
        doc=u"A short summary of the effect",
        info=dict(format='markdown')),
    effect = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of the effect",
        info=dict(format='markdown')),
)

class MoveEffectChangelog(TableBase):
    """History of changes to move effects across main game versions."""
    __tablename__ = 'move_effect_changelog'
    __singlename__ = 'move_effect_changelog'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    effect_id = Column(Integer, ForeignKey('move_effects.id'), nullable=False,
        doc=u"The ID of the effect that changed")
    changed_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        doc=u"The ID of the version group in which the effect changed")

    __table_args__ = (
        UniqueConstraint(effect_id, changed_in_version_group_id),
        {},
    )

create_translation_table('move_effect_changelog_prose', MoveEffectChangelog, 'prose',
    effect = Column(UnicodeText, nullable=False,
        doc=u"A description of the old behavior",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
)

class MoveFlag(TableBase):
    u"""A Move attribute such as "snatchable" or "contact". """
    __tablename__ = 'move_flags'
    __singlename__ = 'move_flag'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"A short identifier for the flag",
        info=dict(format='identifier'))

class MoveFlagMap(TableBase):
    u"""Maps a move flag to a move."""
    __tablename__ = 'move_flag_map'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the move")
    move_flag_id = Column(Integer, ForeignKey('move_flags.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the flag")

create_translation_table('move_flag_prose', MoveFlag, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    description = Column(UnicodeText, nullable=True,
        doc=u"A short description of the flag",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
)

class MoveFlavorText(TableBase):
    u"""In-game description of a move."""
    __tablename__ = 'move_flavor_text'
    summary_column = Move.flavor_summaries_table, 'flavor_summary'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the move")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the version group this text appears in")
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False,
        doc=u"The language")
    flavor_text = Column(UnicodeText, nullable=False,
        doc=u"The flavor text",
        info=dict(official=True, format='gametext'))

class MoveMeta(TableBase):
    u"""Metadata for move effects, sorta-kinda ripped straight from the game."""
    __tablename__ = 'move_meta'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"A numeric ID")
    meta_category_id = Column(Integer, ForeignKey('move_meta_categories.id'), nullable=False,
        doc=u"ID of the move category")
    meta_ailment_id = Column(Integer, ForeignKey('move_meta_ailments.id'), nullable=False,
        doc=u"ID of the caused ailment")
    min_hits = Column(Integer, nullable=True, index=True,
        doc=u"Minimum number of hits per use")
    max_hits = Column(Integer, nullable=True, index=True,
        doc=u"Maximum number of hits per use")
    min_turns = Column(Integer, nullable=True, index=True,
        doc=u"Minimum number of turns the user is forced to use the move")
    max_turns = Column(Integer, nullable=True, index=True,
        doc=u"Maximum number of turns the user is forced to use the move")
    drain = Column(Integer, nullable=False, index=True,
        doc=u"HP drain (if positive) or Recoil damage (if negative), in percent of damage done")
    healing = Column(Integer, nullable=False, index=True,
        doc=u"Healing, in percent of user's max HP")
    crit_rate = Column(Integer, nullable=False, index=True,
        doc=u"Critical hit rate bonus")
    ailment_chance = Column(Integer, nullable=False, index=True,
        doc=u"Chance to cause an ailment, in percent")
    flinch_chance = Column(Integer, nullable=False, index=True,
        doc=u"Chance to cause flinching, in percent")
    stat_chance = Column(Integer, nullable=False, index=True,
        doc=u"Chance to cause a stat change, in percent")

    @hybrid_property
    def recoil(self):
        u"""Recoil damage or HP drain; the opposite of `drain`. """
        return -self.drain

class MoveMetaAilment(TableBase):
    u"""Common status ailments moves can inflict on a single Pokémon, including
    major ailments like paralysis and minor ailments like trapping.
    """
    __tablename__ = 'move_meta_ailments'
    __singlename__ = 'move_meta_ailment'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False, index=True, unique=True,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('move_meta_ailment_names', MoveMetaAilment, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class MoveMetaCategory(TableBase):
    u"""Very general categories that loosely group move effects."""
    __tablename__ = 'move_meta_categories'
    __singlename__ = 'move_meta_category'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False, index=True, unique=True,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('move_meta_category_prose', MoveMetaCategory, 'prose',
    relation_lazy='joined',
    description = Column(UnicodeText, nullable=False,
        doc=u"A description of the category",
        info=dict(format="plaintext", official=False)),
)

class MoveMetaStatChange(TableBase):
    u"""Stat changes moves (may) make."""
    __tablename__ = 'move_meta_stat_changes'
    move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the move")
    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the stat")
    change = Column(Integer, nullable=False, index=True,
        doc=u"Amount of increase/decrease, in stages")

class MoveTarget(TableBase):
    u"""Targeting or "range" of a move, e.g. "Affects all opponents" or "Affects user". """
    __tablename__ = 'move_targets'
    __singlename__ = 'move_target'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('move_target_prose', MoveTarget, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    description = Column(UnicodeText, nullable=True,
        doc=u"A description",
        info=dict(format='plaintext')),
)

class Nature(TableBase):
    u"""A nature a Pokémon can have, such as Calm or Brave."""
    __tablename__ = 'natures'
    __singlename__ = 'nature'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    decreased_stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False,
        doc=u"ID of the stat that this nature decreases by 10% (if decreased_stat_id is the same, the effects cancel out)")
    increased_stat_id = Column(Integer, ForeignKey('stats.id'), nullable=False,
        doc=u"ID of the stat that this nature increases by 10% (if decreased_stat_id is the same, the effects cancel out)")
    hates_flavor_id = Column(Integer, ForeignKey('contest_types.id'), nullable=False,
        doc=u"ID of the Berry flavor the Pokémon hates (if likes_flavor_id is the same, the effects cancel out)")
    likes_flavor_id = Column(Integer, ForeignKey('contest_types.id'), nullable=False,
        doc=u"ID of the Berry flavor the Pokémon likes (if hates_flavor_id is the same, the effects cancel out)")
    game_index = Column(Integer, unique=True, nullable=False,
        doc=u"This nature's internal ID in the games")

    @property
    def is_neutral(self):
        u"""Returns True iff this nature doesn't alter a Pokémon's stats,
        bestow taste preferences, etc.
        """
        return self.increased_stat_id == self.decreased_stat_id

create_translation_table('nature_names', Nature, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True, ripped=True)),
)

class NatureBattleStylePreference(TableBase):
    u"""Battle Palace move preference.

    Specifies how likely a Pokémon with a specific Nature is to use a move of
    a particular battle style in Battle Palace or Battle Tent.
    """
    __tablename__ = 'nature_battle_style_preferences'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False,
        doc=u"ID of the Pokémon's nature")
    move_battle_style_id = Column(Integer, ForeignKey('move_battle_styles.id'), primary_key=True, nullable=False,
        doc=u"ID of the battle style")
    low_hp_preference = Column(Integer, nullable=False,
        doc=u"Chance of using the move, in percent, if HP is under ½")
    high_hp_preference = Column(Integer, nullable=False,
        doc=u"Chance of using the move, in percent, if HP is over ½")

class NaturePokeathlonStat(TableBase):
    u"""Specifies how a Nature affects a Pokéathlon stat."""
    __tablename__ = 'nature_pokeathlon_stats'
    nature_id = Column(Integer, ForeignKey('natures.id'), primary_key=True, nullable=False,
        doc=u"ID of the nature")
    pokeathlon_stat_id = Column(Integer, ForeignKey('pokeathlon_stats.id'), primary_key=True, nullable=False,
        doc=u"ID of the stat")
    max_change = Column(Integer, nullable=False,
        doc=u"Maximum change")

class PalPark(TableBase):
    u"""Data for the Pal Park mini-game in Generation IV."""

    __tablename__ = 'pal_park'
    __singlename__ = 'pal_park'

    species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True,
        doc=u"The Pokémon species this data pertains to")

    area_id = Column(Integer, ForeignKey('pal_park_areas.id'), nullable=False,
        doc=u"The area in which this Pokémon is found")
    base_score = Column(Integer, nullable=False,
        doc=u"Used in calculating the player's score at the end of a Pal Park run")
    rate = Column(Integer, nullable=False,
        doc=u"Base rate for encountering this Pokémon")

class PalParkArea(TableBase):
    u"""A distinct area of Pal Park in which Pokémon appear."""
    __tablename__ = 'pal_park_areas'
    __singlename__ = 'pal_park_area'

    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('pal_park_area_names', PalParkArea, 'names',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
)

class PokeathlonStat(TableBase):
    u"""A Pokéathlon stat, such as "Stamina" or "Jump". """
    __tablename__ = 'pokeathlon_stats'
    __singlename__ = 'pokeathlon_stat'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('pokeathlon_stat_names', PokeathlonStat, 'names',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class Pokedex(TableBase):
    u"""A collection of Pokémon species ordered in a particular way."""
    __tablename__ = 'pokedexes'
    __singlename__ = 'pokedex'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    region_id = Column(Integer, ForeignKey('regions.id'), nullable=True,
        doc=u"ID of the region this Pokédex is used in, or None if it's global")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    is_main_series = Column(Boolean, nullable=False,
        doc=u'True if this Pokédex appears in the main series.')

create_translation_table('pokedex_prose', Pokedex, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    description = Column(UnicodeText, nullable=True,
        doc=u"A longer description of the Pokédex",
        info=dict(format='plaintext')),
)

class PokedexVersionGroup(TableBase):
    u"""A mapping from Pokédexes to version groups in which they appear as the regional dex."""
    __tablename__ = 'pokedex_version_groups'
    __singlename__ = 'pokedex_version_group'
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True,
        doc=u'The ID of the Pokédex.')
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True,
        doc=u'The ID of the version group.')

class Pokemon(TableBase):
    u"""A Pokémon.  The core to this whole mess.

    This table defines "Pokémon" the same way the games do: a form with
    different types, moves, or other game-changing properties counts as a
    different Pokémon.  For example, this table contains four rows for Deoxys,
    but only one for Unown.

    Non-default forms have IDs above 10000.
    IDs below 10000 match the species_id column, for convenience.
    """
    __tablename__ = 'pokemon'
    __singlename__ = 'pokemon'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u'An identifier, including form iff this row corresponds to a single, named form',
        info=dict(format='identifier'))
    species_id = Column(Integer, ForeignKey('pokemon_species.id'),
        doc=u"ID of the species this Pokémon belongs to")
    height = Column(Integer, nullable=False,
        doc=u"The height of the Pokémon, in tenths of a meter (decimeters)")
    weight = Column(Integer, nullable=False,
        doc=u"The weight of the Pokémon, in tenths of a kilogram (hectograms)")
    base_experience = Column(Integer, nullable=False,
        doc=u"The base EXP gained when defeating this Pokémon")
    order = Column(Integer, nullable=False, index=True,
        doc=u"Order for sorting. Almost national order, except families are grouped together.")
    is_default = Column(Boolean, nullable=False, index=True,
        doc=u'Set for exactly one pokemon used as the default for each species.')

    @property
    def name(self):
        u"""Returns a name for this Pokémon, specifying the form iff it
        represents a specific PokemonForm.
        """
        if any(not form.is_default for form in self.forms):
            return self.species.name
        else:
            return self.default_form.pokemon_name or self.species.name

    def stat(self, stat_identifier):
        u"""Returns a PokemonStat record for the given stat name (or Stat row
        object).  Uses the normal has-many machinery, so all the stats are
        effectively cached.
        """
        if isinstance(stat_identifier, Stat):
            stat_identifier = stat_identifier.identifier

        for pokemon_stat in self.stats:
            if pokemon_stat.stat.identifier == stat_identifier:
                return pokemon_stat

        raise KeyError(u'No stat named %s' % stat_identifier)

    def base_stat(self, stat_identifier, default=0):
        u"""Return this Pokemon's base stat value for the given stat identifier,
        or default if missing.
        """

        if isinstance(stat_identifier, Stat):
            stat_identifier = stat_identifier.identifier

        for pokemon_stat in self.stats:
            if pokemon_stat.stat.identifier == stat_identifier:
                return pokemon_stat.base_stat

        return default

    @property
    def better_damage_class(self):
        u"""Returns the MoveDamageClass that this Pokémon is best suited for,
        based on its attack stats.

        If the attack stats are about equal (within 5), returns None.  The
        value None, not the damage class called 'None'.
        """

        try:
            phys = self.stat(u'attack')
            spec = self.stat(u'special-attack')
        except KeyError:
            return None

        diff = phys.base_stat - spec.base_stat

        if diff > 5:
            return phys.stat.damage_class
        elif diff < -5:
            return spec.stat.damage_class
        else:
            return None

class PokemonAbility(TableBase):
    u"""Maps an ability to a Pokémon that can have it."""
    __tablename__ = 'pokemon_abilities'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokémon")
    ability_id = Column(Integer, ForeignKey('abilities.id'), nullable=False,
        doc=u"ID of the ability")
    # XXX having both a method and a slot is kind of gross.  "slot" is a
    # misnomer, anyway: duplicate abilities don't appear in slot 2.
    # Probably should replace that with "order".
    is_hidden = Column(Boolean, nullable=False, index=True,
        doc=u"Whether this is a hidden ability")
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ability slot, i.e. 1 or 2 for gen. IV")

class PokemonColor(TableBase):
    u"""The "Pokédex color" of a Pokémon species. Usually based on the Pokémon's color. """
    __tablename__ = 'pokemon_colors'
    __singlename__ = 'pokemon_color'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokémon")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('pokemon_color_names', PokemonColor, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class PokemonDexNumber(TableBase):
    u"""The number of a species in a particular Pokédex (e.g. Jigglypuff is #138 in Hoenn's 'dex)."""
    __tablename__ = 'pokemon_dex_numbers'
    species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the species")
    pokedex_id = Column(Integer, ForeignKey('pokedexes.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokédex")
    pokedex_number = Column(Integer, nullable=False,
        doc=u"Number of the Pokémon in that the Pokédex")

    __table_args__ = (
        UniqueConstraint(pokedex_id, pokedex_number),
        UniqueConstraint(pokedex_id, species_id),
        {},
    )


class PokemonEggGroup(TableBase):
    u"""Maps an Egg group to a species; each species belongs to one or two egg groups."""
    __tablename__ = 'pokemon_egg_groups'
    species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the species")
    egg_group_id = Column(Integer, ForeignKey('egg_groups.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the egg group")

class PokemonEvolution(TableBase):
    u"""A required action ("trigger") and the conditions under which the trigger
    must occur to cause a Pokémon to evolve.

    Any condition may be null if it does not apply for a particular Pokémon.
    """
    __tablename__ = 'pokemon_evolution'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    evolved_species_id = Column(Integer, ForeignKey('pokemon_species.id'), nullable=False,
        doc=u"The ID of the post-evolution species.")
    evolution_trigger_id = Column(Integer, ForeignKey('evolution_triggers.id'), nullable=False,
        doc=u"The ID of the evolution trigger.")
    trigger_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        doc=u"The ID of the item that must be used on the Pokémon.")
    minimum_level = Column(Integer, nullable=True,
        doc=u"The minimum level for the Pokémon.")
    gender_id = Column(Integer, ForeignKey('genders.id'), nullable=True,
        doc=u"The ID of the Pokémon's required gender, or None if gender doesn't matter")
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True,
        doc=u"The ID of the location the evolution must be triggered at.")
    held_item_id = Column(Integer, ForeignKey('items.id'), nullable=True,
        doc=u"The ID of the item the Pokémon must hold.")
    time_of_day = Column(Enum('day', 'night', name='pokemon_evolution_time_of_day'), nullable=True,
        doc=u"The required time of day.")
    known_move_id = Column(Integer, ForeignKey('moves.id'), nullable=True,
        doc=u"The ID of the move the Pokémon must know.")
    known_move_type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        doc=u'The ID of the type the Pokémon must know a move of.')
    minimum_happiness = Column(Integer, nullable=True,
        doc=u"The minimum happiness value the Pokémon must have.")
    minimum_beauty = Column(Integer, nullable=True,
        doc=u"The minimum Beauty value the Pokémon must have.")
    minimum_affection = Column(Integer, nullable=True,
        doc=u'The minimum number of "affection" hearts the Pokémon must have in Pokémon-Amie.')
    relative_physical_stats = Column(Integer, nullable=True,
        doc=u"The required relation between the Pokémon's Attack and Defense stats, as sgn(atk-def).")
    party_species_id = Column(Integer, ForeignKey('pokemon_species.id'), nullable=True,
        doc=u"The ID of the species that must be present in the party.")
    party_type_id = Column(Integer, ForeignKey('types.id'), nullable=True,
        doc=u'The ID of a type that at least one party member must have.')
    trade_species_id = Column(Integer, ForeignKey('pokemon_species.id'), nullable=True,
        doc=u"The ID of the species for which this one must be traded.")
    needs_overworld_rain = Column(Boolean, nullable=False,
        doc=u'True iff it needs to be raining outside of battle.')
    turn_upside_down = Column(Boolean, nullable=False,
        doc=u'True iff the 3DS needs to be turned upside-down as this Pokémon levels up.')

class PokemonForm(TableBase):
    u"""An individual form of a Pokémon.  This includes *every* variant (except
    color differences) of every Pokémon, regardless of how the games treat
    them.  Even Pokémon with no alternate forms have one row in this table, to
    represent their lone "normal" form.

    Forms which are not the default for their species have IDs above 10000.
    IDs below 10000 correspond to ID of the species for convenience,
    but this should not be relied upon.
    To get the species ID of a form, join with the pokemon table.
    """
    __tablename__ = 'pokemon_forms'
    __singlename__ = 'pokemon_form'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u"A unique identifier for this form among all forms of all Pokémon",
        info=dict(format='identifier'))
    form_identifier = Column(Unicode(79), nullable=True,
        doc=u"An identifier of the form, unique among a species. May be None for the default form of the species.",
        info=dict(format='identifier'))
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, autoincrement=False,
        doc=u'The ID of the base Pokémon for this form.')
    introduced_in_version_group_id = Column(Integer, ForeignKey('version_groups.id'), autoincrement=False,
        doc=u'The ID of the version group in which this form first appeared.')
    is_default = Column(Boolean, nullable=False,
        doc=u'Set for exactly one form used as the default for each pokemon (not necessarily species).')
    is_battle_only = Column(Boolean, nullable=False,
        doc=u'Set iff the form can only appear in battle.')
    is_mega = Column(Boolean, nullable=False,
        doc=u'Records whether this form is a Mega Evolution.')
    form_order = Column(Integer, nullable=False, autoincrement=False,
        doc=u"""The order in which forms should be sorted within a species' forms.

            Multiple forms may have equal order, in which case they should fall
            back on sorting by name.  Used in generating `pokemon_forms.order`
            and `pokemon.order`.
            """)
    order = Column(Integer, nullable=False, autoincrement=False,
        doc=u'The order in which forms should be sorted within all forms.  Multiple forms may have equal order, in which case they should fall back on sorting by name.')

    @property
    def name(self):
        """Name of this form: the form_name, if set; otherwise the species name."""
        return self.pokemon_name or self.species.name

create_translation_table('pokemon_form_names', PokemonForm, 'names',
    relation_lazy='joined',
    form_name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The full form name, e.g. 'Sky Forme', for pokémon with different forms",
        info=dict(format='plaintext', official=True)),
    pokemon_name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The full pokémon name, e.g. 'Sky Shaymin', for pokémon with different forms",
        info=dict(format='plaintext', official=True)),
)

class PokemonFormGeneration(TableBase):
    u"""Links Pokémon forms to the generations they exist in."""
    __tablename__ = 'pokemon_form_generations'
    pokemon_form_id = Column(Integer, ForeignKey('pokemon_forms.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the Pokémon form.')
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the generation.')
    game_index = Column(Integer, nullable=False,
        doc=u'The internal ID the games use for this form.')

class PokemonFormPokeathlonStat(TableBase):
    u"""A Pokémon form's performance in one Pokéathlon stat."""
    __tablename__ = 'pokemon_form_pokeathlon_stats'
    pokemon_form_id = Column(Integer, ForeignKey('pokemon_forms.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the Pokémon form.')
    pokeathlon_stat_id = Column(Integer, ForeignKey('pokeathlon_stats.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u'The ID of the Pokéathlon stat.')
    minimum_stat = Column(Integer, nullable=False, autoincrement=False,
        doc=u'The minimum value for this stat for this Pokémon form.')
    base_stat = Column(Integer, nullable=False, autoincrement=False,
        doc=u'The default value for this stat for this Pokémon form.')
    maximum_stat = Column(Integer, nullable=False, autoincrement=False,
        doc=u'The maximum value for this stat for this Pokémon form.')

class PokemonGameIndex(TableBase):
    u"""The number of a Pokémon a game uses internally."""
    __tablename__ = 'pokemon_game_indices'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"Database ID of the Pokémon")
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"Database ID of the version")
    game_index = Column(Integer, nullable=False,
        doc=u"Internal ID the version's games use for the Pokémon")

class PokemonHabitat(TableBase):
    u"""The habitat of a Pokémon, as given in the FireRed/LeafGreen version Pokédex."""
    __tablename__ = 'pokemon_habitats'
    __singlename__ = 'pokemon_habitat'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('pokemon_habitat_names', PokemonHabitat, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class PokemonItem(TableBase):
    u"""Record of an item a Pokémon can hold in the wild."""
    __tablename__ = 'pokemon_items'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokémon")
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the version this applies to")
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the item")
    rarity = Column(Integer, nullable=False,
        doc=u"Chance of the Pokémon holding the item, in percent")

class PokemonMove(TableBase):
    u"""Record of a move a Pokémon can learn."""
    __tablename__ = 'pokemon_moves'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), nullable=False, index=True,
        doc=u"ID of the Pokémon")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False, index=True,
        doc=u"ID of the version group this applies to")
    move_id = Column(Integer, ForeignKey('moves.id'), nullable=False, index=True,
        doc=u"ID of the move")
    pokemon_move_method_id = Column(Integer, ForeignKey('pokemon_move_methods.id'), nullable=False, index=True,
        doc=u"ID of the method this move is learned by")
    level = Column(Integer, nullable=True, index=True, autoincrement=False,
        doc=u"Level the move is learned at, if applicable")
    order = Column(Integer, nullable=True,
        doc=u"The order which moves learned at the same level are learned in")

    __table_args__ = (
        PrimaryKeyConstraint('pokemon_id', 'version_group_id', 'move_id', 'pokemon_move_method_id', 'level'),
        {},
    )

class PokemonMoveMethod(TableBase):
    u"""A method a move can be learned by, such as "Level up" or "Tutor". """
    __tablename__ = 'pokemon_move_methods'
    __singlename__ = 'pokemon_move_method'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('pokemon_move_method_prose', PokemonMoveMethod, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    description = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of how the method works",
        info=dict(format='plaintext')),
)

class PokemonShape(TableBase):
    u"""The shape of a Pokémon's body.  Used for flavor in generation IV and V Pokédexes. """
    __tablename__ = 'pokemon_shapes'
    __singlename__ = 'pokemon_shape'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('pokemon_shape_prose', PokemonShape, 'prose',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=False)),
    awesome_name = Column(Unicode(79), nullable=True,
        doc=u"A splendiferous name of the body shape",
        info=dict(format='plaintext')),
    description = Column(UnicodeText, nullable=True,
        doc=u"A detailed description of the body shape",
        info=dict(format='plaintext')),
)

class PokemonSpecies(TableBase):
    u"""A Pokémon species: the standard 1–151.  Or 649.  Whatever.

    ID matches the National Pokédex number of the species.
    """
    __tablename__ = 'pokemon_species'
    __singlename__ = 'pokemon_species'
    id = Column(Integer, primary_key=True, nullable=False)
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'),
        doc=u"ID of the generation this species first appeared in")
    evolves_from_species_id = Column(Integer, ForeignKey('pokemon_species.id'), nullable=True,
        doc=u"The species from which this one evolves")
    evolution_chain_id = Column(Integer, ForeignKey('evolution_chains.id'),
        doc=u"ID of the species' evolution chain (a.k.a. family)")
    color_id = Column(Integer, ForeignKey('pokemon_colors.id'), nullable=False,
        doc=u"ID of this Pokémon's Pokédex color, as used for a gimmick search function in the games.")
    shape_id = Column(Integer, ForeignKey('pokemon_shapes.id'), nullable=False,
        doc=u"ID of this Pokémon's body shape, as used for a gimmick search function in the games.")
    habitat_id = Column(Integer, ForeignKey('pokemon_habitats.id'), nullable=True,
        doc=u"ID of this Pokémon's habitat, as used for a gimmick search function in the games.")
    gender_rate = Column(Integer, nullable=False,
        doc=u"The chance of this Pokémon being female, in eighths; or -1 for genderless")
    capture_rate = Column(Integer, nullable=False,
        doc=u"The base capture rate; up to 255")
    base_happiness = Column(Integer, nullable=False,
        doc=u"The tameness when caught by a normal ball")
    is_baby = Column(Boolean, nullable=False,
        doc=u"True iff the Pokémon is a baby, i.e. a lowest-stage Pokémon that cannot breed but whose evolved form can.")
    hatch_counter = Column(Integer, nullable=False,
        doc=u"Initial hatch counter: one must walk 255 × (hatch_counter + 1) steps before this Pokémon's egg hatches, unless utilizing bonuses like Flame Body's")
    has_gender_differences = Column(Boolean, nullable=False,
        doc=u"Set iff the species exhibits enough sexual dimorphism to have separate sets of sprites in Gen IV and beyond.")
    growth_rate_id = Column(Integer, ForeignKey('growth_rates.id'), nullable=False,
        doc=u"ID of the growth rate for this family")
    forms_switchable = Column(Boolean, nullable=False,
        doc=u"True iff a particular individual of this species can switch between its different forms.")
    is_legendary = Column(Boolean, nullable=False,
        doc=u'True iff the Pokémon is a legendary Pokémon.')
    is_mythical = Column(Boolean, nullable=False,
        doc=u'True iff the Pokémon is a mythical Pokémon.')
    order = Column(Integer, nullable=False, index=True,
        doc=u'The order in which species should be sorted.  Based on National Dex order, except families are grouped together and sorted by stage.')
    conquest_order = Column(Integer, nullable=True, index=True,
        doc=u'The order in which species should be sorted for Pokémon Conquest-related tables.  Matches gallery order.')

create_translation_table('pokemon_species_names', PokemonSpecies, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=True, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True, ripped=True)),
    genus = Column(UnicodeText, nullable=True,
        doc=u'The short flavor text, such as "Seed" or "Lizard"; usually affixed with the word "Pokémon"',
        info=dict(official=True, format='plaintext')),
)
create_translation_table('pokemon_species_flavor_summaries', PokemonSpecies, 'flavor_summaries',
    flavor_summary = Column(UnicodeText, nullable=True,
        doc=u"Text containing facts from all flavor texts, for languages without official game translations",
        info=dict(official=False, format='plaintext', ripped=True)),
)
create_translation_table('pokemon_species_prose', PokemonSpecies, 'prose',
    form_description = Column(UnicodeText, nullable=True,
        doc=u"Description of how the forms work",
        info=dict(format='markdown', string_getter=markdown.MarkdownString)),
)

class PokemonSpeciesFlavorText(TableBase):
    u"""In-game Pokédex description of a Pokémon."""
    __tablename__ = 'pokemon_species_flavor_text'
    summary_column = PokemonSpecies.flavor_summaries_table, 'flavor_summary'
    species_id = Column(Integer, ForeignKey('pokemon_species.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokémon")
    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the version that has this flavor text")
    language_id = Column(Integer, ForeignKey('languages.id'), primary_key=True, nullable=False,
        doc=u"The language")
    flavor_text = Column(UnicodeText, nullable=False,
        doc=u"The flavor text",
        info=dict(official=True, format='gametext'))

class PokemonStat(TableBase):
    u"""A stat value of a Pokémon."""
    __tablename__ = 'pokemon_stats'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokémon")
    stat_id = Column(Integer, ForeignKey('stats.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the stat")
    base_stat = Column(Integer, nullable=False,
        doc=u"The base stat")
    effort = Column(Integer, nullable=False,
        doc=u"The effort increase in this stat gained when this Pokémon is defeated")

class PokemonType(TableBase):
    u"""Maps a type to a Pokémon. Each Pokémon has 1 or 2 types."""
    __tablename__ = 'pokemon_types'
    pokemon_id = Column(Integer, ForeignKey('pokemon.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"ID of the Pokémon")
    type_id = Column(Integer, ForeignKey('types.id'), nullable=False,
        doc=u"ID of the type")
    slot = Column(Integer, primary_key=True, nullable=False, autoincrement=False,
        doc=u"The type's slot, 1 or 2, used to sort types if there are two of them")

class Region(TableBase):
    u"""Major areas of the world: Kanto, Johto, etc."""
    __tablename__ = 'regions'
    __singlename__ = 'region'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))

create_translation_table('region_names', Region, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class Stat(TableBase):
    u"""A Stat, such as Attack or Speed."""
    __tablename__ = 'stats'
    __singlename__ = 'stat'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=True,
        doc=u"For offensive and defensive stats, the damage this stat relates to; otherwise None (the NULL value)")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    is_battle_only = Column(Boolean, nullable=False,
        doc=u"Whether this stat only exists within a battle")
    game_index = Column(Integer, nullable=True,
        doc=u"The stat order the games use internally for the persistent stats.  NULL for battle-only stats.")

create_translation_table('stat_names', Stat, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class SuperContestCombo(TableBase):
    u"""Combo of two moves in a Super Contest."""
    __tablename__ = 'super_contest_combos'
    first_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the first move in the combo.")
    second_move_id = Column(Integer, ForeignKey('moves.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the second and last move.")

class SuperContestEffect(TableBase):
    u"""An effect a move can have when used in the Super Contest."""
    __tablename__ = 'super_contest_effects'
    __singlename__ = 'super_contest_effect'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"This effect's unique ID.")
    appeal = Column(SmallInteger, nullable=False,
        doc=u"The number of hearts the user gains.")

create_translation_table('super_contest_effect_prose', SuperContestEffect, 'prose',
    flavor_text = Column(UnicodeText, nullable=False,
        doc=u"A description of the effect.",
        info=dict(format='plaintext', official=True)),
)

class Type(TableBase):
    u"""Any of the elemental types Pokémon and moves can have."""
    __tablename__ = 'types'
    __singlename__ = 'type'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this type.")
    identifier = Column(Unicode(79), nullable=False,
        doc=u"An identifier",
        info=dict(format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        doc=u"The ID of the generation this type first appeared in.")
    damage_class_id = Column(Integer, ForeignKey('move_damage_classes.id'), nullable=True,
        doc=u"The ID of the damage class this type's moves had before Generation IV, null if not applicable (e.g. ???).")

create_translation_table('type_names', Type, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class TypeEfficacy(TableBase):
    u"""The damage multiplier used when a move of a particular type damages a
    Pokémon of a particular other type.
    """
    __tablename__ = 'type_efficacy'
    damage_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the damaging move's type.")
    target_type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, nullable=False, autoincrement=False,
        doc=u"The ID of the defending Pokémon's type.")
    damage_factor = Column(Integer, nullable=False,
        doc=u"The multiplier, as a percentage of damage inflicted.")

class TypeGameIndex(TableBase):
    u"""The internal ID number a game uses for a type."""
    __tablename__ = 'type_game_indices'
    type_id = Column(Integer, ForeignKey('types.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"The type")
    generation_id = Column(Integer, ForeignKey('generations.id'), primary_key=True, autoincrement=False, nullable=False,
        doc=u"The generation")
    game_index = Column(Integer, nullable=False,
        doc=u"Internal ID of the type in this generation")

class Version(TableBase):
    u"""An individual main-series Pokémon game."""
    __tablename__ = 'versions'
    __singlename__ = 'version'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A unique ID for this version.")
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), nullable=False,
        doc=u"The ID of the version group this game belongs to.")
    identifier = Column(Unicode(79), nullable=False,
        doc=u'An identifier',
        info=dict(format='identifier'))

create_translation_table('version_names', Version, 'names',
    relation_lazy='joined',
    name = Column(Unicode(79), nullable=False, index=True,
        doc=u"The name",
        info=dict(format='plaintext', official=True)),
)

class VersionGroup(TableBase):
    u"""A group of versions, containing either two paired versions (such as Red
    and Blue) or a single game (such as Yellow).
    """
    __tablename__ = 'version_groups'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"This version group's unique ID.")
    identifier = Column(Unicode(79), nullable=False, unique=True,
        doc=u"This version group's unique textual identifier.",
        info=dict(format='identifier'))
    generation_id = Column(Integer, ForeignKey('generations.id'), nullable=False,
        doc=u"The ID of the generation the games in this group belong to.")
    order = Column(Integer, nullable=True,
        doc=u"Order for sorting. Almost by date of release, except similar versions are grouped together.")

class VersionGroupPokemonMoveMethod(TableBase):
    u"""Maps a version group to a move learn methods it supports.

    "Supporting" means simply that the method appears in the game.
    For example, Breeding didn't exist in Gen.I, so it's not in this table.
    """
    __tablename__ = 'version_group_pokemon_move_methods'
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False,
        doc=u"The ID of the version group.")
    pokemon_move_method_id = Column(Integer, ForeignKey('pokemon_move_methods.id'), primary_key=True, nullable=False,
        doc=u"The ID of the move method.")

class VersionGroupRegion(TableBase):
    u"""Maps a version group to a region that appears in it."""
    __tablename__ = 'version_group_regions'
    version_group_id = Column(Integer, ForeignKey('version_groups.id'), primary_key=True, nullable=False,
        doc=u"The ID of the version group.")
    region_id = Column(Integer, ForeignKey('regions.id'), primary_key=True, nullable=False,
        doc=u"The ID of the region.")


### Relationships down here, to avoid dependency ordering problems

Ability.changelog = relationship(AbilityChangelog,
    order_by=AbilityChangelog.changed_in_version_group_id.desc(),
    backref=backref('ability', innerjoin=True, lazy='joined'))
Ability.flavor_text = relationship(AbilityFlavorText,
    order_by=AbilityFlavorText.version_group_id,
    backref=backref('ability', innerjoin=True, lazy='joined'))
Ability.generation = relationship(Generation,
    innerjoin=True,
    backref='abilities')

AbilityChangelog.changed_in = relationship(VersionGroup,
    innerjoin=True, lazy='joined',
    backref='ability_changelog')

AbilityFlavorText.version_group = relationship(VersionGroup,
    innerjoin=True)
AbilityFlavorText.language = relationship(Language,
    innerjoin=True, lazy='joined')


Berry.berry_firmness = relationship(BerryFirmness,
    innerjoin=True,
    backref='berries')
Berry.firmness = association_proxy('berry_firmness', 'name')
Berry.flavors = relationship(BerryFlavor,
    order_by=BerryFlavor.contest_type_id,
    backref=backref('berry', innerjoin=True))
Berry.natural_gift_type = relationship(Type, innerjoin=True)

BerryFlavor.contest_type = relationship(ContestType, innerjoin=True)


Characteristic.stat = relationship(Stat,
    innerjoin=True,
    backref='characteristics')


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


ContestCombo.first = relationship(Move,
    primaryjoin=ContestCombo.first_move_id==Move.id,
    innerjoin=True, lazy='joined',
    backref='contest_combo_first')
ContestCombo.second = relationship(Move,
    primaryjoin=ContestCombo.second_move_id==Move.id,
    innerjoin=True, lazy='joined',
    backref='contest_combo_second')


Encounter.condition_values = relationship(EncounterConditionValue,
    secondary=EncounterConditionValueMap.__table__)
Encounter.location_area = relationship(LocationArea,
    innerjoin=True, lazy='joined',
    backref='encounters')
Encounter.pokemon = relationship(Pokemon,
    innerjoin=True, lazy='joined',
    backref='encounters')
Encounter.version = relationship(Version,
    innerjoin=True, lazy='joined',
    backref='encounters')
Encounter.slot = relationship(EncounterSlot,
    innerjoin=True, lazy='joined',
    backref='encounters')

EncounterConditionValue.condition = relationship(EncounterCondition,
    innerjoin=True, lazy='joined',
    backref='values')

EncounterSlot.method = relationship(EncounterMethod,
    innerjoin=True, lazy='joined',
    backref='slots')
EncounterSlot.version_group = relationship(VersionGroup, innerjoin=True)


EvolutionChain.baby_trigger_item = relationship(Item,
    backref='evolution_chains')


Experience.growth_rate = relationship(GrowthRate,
    innerjoin=True, lazy='joined',
    backref='experience_table')


Generation.versions = relationship(Version,
    secondary=VersionGroup.__table__,
    innerjoin=True)
Generation.main_region = relationship(Region, innerjoin=True)


GrowthRate.max_experience_obj = relationship(Experience,
    primaryjoin=and_(
        Experience.growth_rate_id == GrowthRate.id,
        Experience.level == 100),
    uselist=False, innerjoin=True)
GrowthRate.max_experience = association_proxy('max_experience_obj', 'experience')


Item.berry = relationship(Berry,
    uselist=False,
    backref='item')
Item.flags = relationship(ItemFlag,
    secondary=ItemFlagMap.__table__)
Item.flavor_text = relationship(ItemFlavorText,
    order_by=ItemFlavorText.version_group_id.asc(),
    backref=backref('item', innerjoin=True, lazy='joined'))
Item.fling_effect = relationship(ItemFlingEffect,
    backref='items')
Item.machines = relationship(Machine,
    order_by=Machine.version_group_id.asc())
Item.category = relationship(ItemCategory,
    innerjoin=True,
    backref=backref('items', order_by=Item.identifier.asc()))
Item.pocket = association_proxy('category', 'pocket')

ItemCategory.pocket = relationship(ItemPocket, innerjoin=True)

ItemFlavorText.version_group = relationship(VersionGroup,
    innerjoin=True, lazy='joined')
ItemFlavorText.language = relationship(Language,
    innerjoin=True, lazy='joined')

ItemGameIndex.item = relationship(Item,
    innerjoin=True, lazy='joined',
    backref='game_indices')
ItemGameIndex.generation = relationship(Generation,
    innerjoin=True, lazy='joined')

ItemPocket.categories = relationship(ItemCategory,
    innerjoin=True,
    order_by=ItemCategory.identifier.asc())


Location.region = relationship(Region,
    innerjoin=True,
    backref='locations')

LocationArea.location = relationship(Location,
    innerjoin=True, lazy='joined',
    backref='areas')

LocationAreaEncounterRate.location_area = relationship(LocationArea,
    innerjoin=True,
    backref='encounter_rates')
LocationAreaEncounterRate.method = relationship(EncounterMethod,
    innerjoin=True)

LocationGameIndex.location = relationship(Location,
    innerjoin=True, lazy='joined',
    backref='game_indices')
LocationGameIndex.generation = relationship(Generation,
    innerjoin=True, lazy='joined')


Machine.item = relationship(Item)
Machine.version_group = relationship(VersionGroup,
    innerjoin=True, lazy='joined')


Move.changelog = relationship(MoveChangelog,
    order_by=MoveChangelog.changed_in_version_group_id.desc(),
    backref=backref('move', innerjoin=True, lazy='joined'))
Move.contest_effect = relationship(ContestEffect,
    backref='moves')
Move.contest_combo_next = association_proxy('contest_combo_first', 'second')
Move.contest_combo_prev = association_proxy('contest_combo_second', 'first')
Move.contest_type = relationship(ContestType,
    backref='moves')
Move.damage_class = relationship(MoveDamageClass,
    innerjoin=True,
    backref='moves')
Move.flags = association_proxy('move_flags', 'flag')
Move.flavor_text = relationship(MoveFlavorText,
    order_by=MoveFlavorText.version_group_id, backref='move')
Move.generation = relationship(Generation,
    innerjoin=True,
    backref='moves')
# XXX should this be a dict mapping version group to number?
Move.machines = relationship(Machine,
    backref='move')
Move.meta = relationship(MoveMeta,
    uselist=False,
    backref='move')
Move.meta_stat_changes = relationship(MoveMetaStatChange)
Move.move_effect = relationship(MoveEffect,
    innerjoin=True,
    backref='moves')
Move.move_flags = relationship(MoveFlagMap,
    backref='move')
Move.super_contest_effect = relationship(SuperContestEffect,
    backref='moves')
Move.super_contest_combo_next = association_proxy('super_contest_combo_first', 'second')
Move.super_contest_combo_prev = association_proxy('super_contest_combo_second', 'first')
Move.target = relationship(MoveTarget,
    innerjoin=True,
    backref='moves')
Move.type = relationship(Type,
    innerjoin=True, lazy='joined',
    backref='moves')

Move.effect = markdown.MoveEffectProperty('effect')
Move.effect_map = markdown.MoveEffectPropertyMap('effect_map')
Move.short_effect = markdown.MoveEffectProperty('short_effect')
Move.short_effect_map = markdown.MoveEffectPropertyMap('short_effect_map')

MoveChangelog.changed_in = relationship(VersionGroup,
    innerjoin=True, lazy='joined',
    backref='move_changelog')
MoveChangelog.move_effect = relationship(MoveEffect,
    backref='move_changelog')
MoveChangelog.target = relationship(MoveTarget,
    backref='move_changelog')
MoveChangelog.type = relationship(Type,
    backref='move_changelog')

MoveChangelog.effect = markdown.MoveEffectProperty('effect')
MoveChangelog.effect_map = markdown.MoveEffectPropertyMap('effect_map')
MoveChangelog.short_effect = markdown.MoveEffectProperty('short_effect')
MoveChangelog.short_effect_map = markdown.MoveEffectPropertyMap('short_effect_map')

MoveEffect.changelog = relationship(MoveEffectChangelog,
    order_by=MoveEffectChangelog.changed_in_version_group_id.desc(),
    backref='move_effect')

MoveEffectChangelog.changed_in = relationship(VersionGroup,
    innerjoin=True, lazy='joined',
    backref='move_effect_changelog')

MoveFlagMap.flag = relationship(MoveFlag, innerjoin=True, lazy='joined')

MoveFlavorText.version_group = relationship(VersionGroup,
    innerjoin=True, lazy='joined')
MoveFlavorText.language = relationship(Language,
    innerjoin=True, lazy='joined')

MoveMeta.category = relationship(MoveMetaCategory,
    innerjoin=True, lazy='joined',
    backref='move_meta')
MoveMeta.ailment = relationship(MoveMetaAilment,
    innerjoin=True, lazy='joined',
    backref='move_meta')

MoveMetaStatChange.stat = relationship(Stat,
    innerjoin=True, lazy='joined',
    backref='move_meta_stat_changes')


Nature.decreased_stat = relationship(Stat,
    primaryjoin=Nature.decreased_stat_id==Stat.id,
    innerjoin=True,
    backref='decreasing_natures')
Nature.increased_stat = relationship(Stat,
    primaryjoin=Nature.increased_stat_id==Stat.id,
    innerjoin=True,
    backref='increasing_natures')
Nature.hates_flavor = relationship(ContestType,
    primaryjoin=Nature.hates_flavor_id==ContestType.id,
    innerjoin=True,
    backref='hating_natures')
Nature.likes_flavor = relationship(ContestType,
    primaryjoin=Nature.likes_flavor_id==ContestType.id,
    innerjoin=True,
    backref='liking_natures')
Nature.battle_style_preferences = relationship(NatureBattleStylePreference,
    order_by=NatureBattleStylePreference.move_battle_style_id.asc(),
    backref='nature')
Nature.pokeathlon_effects = relationship(NaturePokeathlonStat,
    order_by=NaturePokeathlonStat.pokeathlon_stat_id.asc())

NatureBattleStylePreference.battle_style = relationship(MoveBattleStyle,
    innerjoin=True, lazy='joined',
    backref='nature_preferences')

NaturePokeathlonStat.pokeathlon_stat = relationship(PokeathlonStat,
    innerjoin=True, lazy='joined',
    backref='nature_effects')


PalPark.area = relationship(PalParkArea,
    innerjoin=True, lazy='joined')


Pokedex.region = relationship(Region,
    innerjoin=True,
    backref='pokedexes')
Pokedex.version_groups = relationship(VersionGroup,
    secondary=PokedexVersionGroup.__table__,
    innerjoin=True,
    order_by=VersionGroup.order.asc(),
    backref='pokedexes')


Pokemon.all_abilities = relationship(Ability,
    secondary=PokemonAbility.__table__,
    order_by=PokemonAbility.slot.asc(),
    backref=backref('all_pokemon', order_by=Pokemon.order.asc()),
    doc=u"All abilities the Pokémon can have, including the Hidden Ability")
Pokemon.abilities = relationship(Ability,
    secondary=PokemonAbility.__table__,
    primaryjoin=and_(
        Pokemon.id == PokemonAbility.pokemon_id,
        PokemonAbility.is_hidden == False,
    ),
    order_by=PokemonAbility.slot.asc(),
    backref=backref('pokemon', order_by=Pokemon.order.asc()),
    doc=u"Abilities the Pokémon can have in the wild")
Pokemon.hidden_ability = relationship(Ability,
    secondary=PokemonAbility.__table__,
    primaryjoin=and_(
        Pokemon.id == PokemonAbility.pokemon_id,
        PokemonAbility.is_hidden == True,
    ),
    uselist=False,
    backref=backref('hidden_pokemon', order_by=Pokemon.order),
    doc=u"The Pokémon's Hidden Ability")
Pokemon.pokemon_abilities = relationship(PokemonAbility,
    order_by=PokemonAbility.slot.asc(),
    backref=backref('pokemon', order_by=Pokemon.order.asc()),
    doc=u"All abilities the Pokémon can have, as bridge rows")
Pokemon.forms = relationship(PokemonForm,
    primaryjoin=Pokemon.id==PokemonForm.pokemon_id,
    order_by=(PokemonForm.order.asc(), PokemonForm.form_identifier.asc()),
    lazy='joined')
Pokemon.default_form = relationship(PokemonForm,
    primaryjoin=and_(
        Pokemon.id==PokemonForm.pokemon_id,
        PokemonForm.is_default==True),
    uselist=False, lazy='joined',
    doc=u"A representative form of this pokémon")
Pokemon.items = relationship(PokemonItem,
    backref='pokemon',
    order_by=PokemonItem.rarity.desc(),
    doc=u"Info about items this pokémon holds in the wild")
Pokemon.stats = relationship(PokemonStat,
    order_by=PokemonStat.stat_id.asc(),
    backref='pokemon')
Pokemon.species = relationship(PokemonSpecies,
    innerjoin=True,
    backref='pokemon')
Pokemon.types = relationship(Type,
    secondary=PokemonType.__table__,
    innerjoin=True, lazy='joined',
    order_by=PokemonType.slot.asc(),
    backref=backref('pokemon', order_by=Pokemon.order))

PokemonAbility.ability = relationship(Ability,
    innerjoin=True)

PokemonDexNumber.pokedex = relationship(Pokedex,
    innerjoin=True, lazy='joined')

PokemonEvolution.trigger = relationship(EvolutionTrigger,
    innerjoin=True, lazy='joined',
    backref='evolutions')
PokemonEvolution.trigger_item = relationship(Item,
    primaryjoin=PokemonEvolution.trigger_item_id==Item.id,
    backref='triggered_evolutions')
PokemonEvolution.held_item = relationship(Item,
    primaryjoin=PokemonEvolution.held_item_id==Item.id,
    backref='required_for_evolutions')
PokemonEvolution.location = relationship(Location,
    backref='triggered_evolutions')
PokemonEvolution.known_move = relationship(Move,
    backref='triggered_evolutions')
PokemonEvolution.known_move_type = relationship(Type,
    primaryjoin=PokemonEvolution.known_move_type_id==Type.id)
PokemonEvolution.party_species = relationship(PokemonSpecies,
    primaryjoin=PokemonEvolution.party_species_id==PokemonSpecies.id,
    backref='triggered_evolutions')
PokemonEvolution.party_type = relationship(Type,
    primaryjoin=PokemonEvolution.party_type_id==Type.id)
PokemonEvolution.trade_species = relationship(PokemonSpecies,
    primaryjoin=PokemonEvolution.trade_species_id==PokemonSpecies.id)
PokemonEvolution.gender = relationship(Gender,
    backref='required_for_evolutions')

PokemonForm.pokemon = relationship(Pokemon,
    primaryjoin=PokemonForm.pokemon_id==Pokemon.id,
    innerjoin=True, lazy='joined')
PokemonForm.species = association_proxy('pokemon', 'species')
PokemonForm.version_group = relationship(VersionGroup,
    innerjoin=True)
PokemonForm.pokeathlon_stats = relationship(PokemonFormPokeathlonStat,
    order_by=PokemonFormPokeathlonStat.pokeathlon_stat_id,
    backref='pokemon_form')

PokemonFormPokeathlonStat.pokeathlon_stat = relationship(PokeathlonStat,
    innerjoin=True, lazy='joined')

PokemonFormGeneration.form = relationship(PokemonForm,
    backref=backref('pokemon_form_generations',
        order_by=PokemonFormGeneration.generation_id))
PokemonFormGeneration.generation = relationship(Generation,
    backref=backref('pokemon_form_generations',
        order_by=PokemonFormGeneration.game_index))

PokemonItem.item = relationship(Item,
    innerjoin=True, lazy='joined',
    backref='pokemon')
PokemonItem.version = relationship(Version,
    innerjoin=True, lazy='joined')

PokemonMove.pokemon = relationship(Pokemon,
    innerjoin=True, lazy='joined',
    backref='pokemon_moves')
PokemonMove.version_group = relationship(VersionGroup,
    innerjoin=True, lazy='joined',
    backref='pokemon_moves')
PokemonMove.machine = relationship(Machine,
    primaryjoin=and_(
        Machine.version_group_id==PokemonMove.version_group_id,
        Machine.move_id==PokemonMove.move_id),
    foreign_keys=[Machine.version_group_id, Machine.move_id],
    uselist=False,
    backref='pokemon_moves')
PokemonMove.move = relationship(Move,
    innerjoin=True, lazy='joined',
    backref='pokemon_moves')
PokemonMove.method = relationship(PokemonMoveMethod,
    innerjoin=True, lazy='joined')

PokemonStat.stat = relationship(Stat,
    innerjoin=True, lazy='joined')

PokemonSpecies.parent_species = relationship(PokemonSpecies,
    primaryjoin=PokemonSpecies.evolves_from_species_id==PokemonSpecies.id,
    remote_side=[PokemonSpecies.id],
    backref=backref('child_species',
        doc=u"The species to which this one evolves"),
    doc=u"The species from which this one evolves")
PokemonSpecies.evolutions = relationship(PokemonEvolution,
    primaryjoin=PokemonSpecies.id==PokemonEvolution.evolved_species_id,
    backref=backref('evolved_species', innerjoin=True, lazy='joined'))
PokemonSpecies.flavor_text = relationship(PokemonSpeciesFlavorText,
    order_by=PokemonSpeciesFlavorText.version_id.asc(),
    backref='species')
PokemonSpecies.growth_rate = relationship(GrowthRate,
    innerjoin=True,
    backref='evolution_chains')
PokemonSpecies.habitat = relationship(PokemonHabitat,
    backref='species')
PokemonSpecies.color = relationship(PokemonColor,
    innerjoin=True,
    backref='species')
PokemonSpecies.egg_groups = relationship(EggGroup,
    secondary=PokemonEggGroup.__table__,
    order_by=PokemonEggGroup.egg_group_id.asc(),
    backref=backref('species', order_by=PokemonSpecies.order.asc()))
PokemonSpecies.forms = relationship(PokemonForm,
    secondary=Pokemon.__table__,
    primaryjoin=PokemonSpecies.id==Pokemon.species_id,
    secondaryjoin=Pokemon.id==PokemonForm.pokemon_id,
    order_by=(PokemonForm.order.asc(), PokemonForm.form_identifier.asc()))
PokemonSpecies.default_form = relationship(PokemonForm,
    secondary=Pokemon.__table__,
    primaryjoin=and_(PokemonSpecies.id==Pokemon.species_id,
            Pokemon.is_default==True),
    secondaryjoin=and_(Pokemon.id==PokemonForm.pokemon_id,
            PokemonForm.is_default==True),
    uselist=False,
    doc=u"A representative form of this species")
PokemonSpecies.default_pokemon = relationship(Pokemon,
    primaryjoin=and_(
        PokemonSpecies.id==Pokemon.species_id,
        Pokemon.is_default==True),
    uselist=False, lazy='joined')
PokemonSpecies.evolution_chain = relationship(EvolutionChain,
    backref=backref('species', order_by=PokemonSpecies.id.asc()))
PokemonSpecies.dex_numbers = relationship(PokemonDexNumber,
    innerjoin=True,
    order_by=PokemonDexNumber.pokedex_id.asc(),
    backref='species')
PokemonSpecies.generation = relationship(Generation,
    innerjoin=True,
    backref='species')
PokemonSpecies.shape = relationship(PokemonShape,
    innerjoin=True,
    backref='species')
PokemonSpecies.pal_park = relationship(PalPark,
    uselist=False,
    backref='species')

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

PokemonSpeciesFlavorText.version = relationship(Version, innerjoin=True, lazy='joined')
PokemonSpeciesFlavorText.language = relationship(Language, innerjoin=True, lazy='joined')

Region.generation = relationship(Generation, uselist=False)
Region.version_group_regions = relationship(VersionGroupRegion,
    order_by=VersionGroupRegion.version_group_id.asc(),
    backref='region')
Region.version_groups = relationship(VersionGroup,
    secondary=VersionGroupRegion.__table__,
    order_by=VersionGroup.order)


Stat.damage_class = relationship(MoveDamageClass,
    backref='stats')


SuperContestCombo.first = relationship(Move,
    primaryjoin=SuperContestCombo.first_move_id==Move.id,
    innerjoin=True, lazy='joined',
    backref='super_contest_combo_first')
SuperContestCombo.second = relationship(Move,
    primaryjoin=SuperContestCombo.second_move_id==Move.id,
    innerjoin=True, lazy='joined',
    backref='super_contest_combo_second')


Type.damage_efficacies = relationship(TypeEfficacy,
    primaryjoin=Type.id==TypeEfficacy.damage_type_id,
    backref=backref('damage_type', innerjoin=True, lazy='joined'),
    doc=u"Efficacies with this type as the attacking type.")
Type.target_efficacies = relationship(TypeEfficacy,
    primaryjoin=Type.id==TypeEfficacy.target_type_id,
    backref=backref('target_type', innerjoin=True, lazy='joined'),
    doc=u"Efficacies with this type as the defending type.")

Type.generation = relationship(Generation,
    innerjoin=True,
    backref='types')
Type.damage_class = relationship(MoveDamageClass,
    backref='types')

TypeGameIndex.type = relationship(Type,
    innerjoin=True, lazy='joined',
    backref='game_indices')
TypeGameIndex.generation = relationship(Generation,
    innerjoin=True, lazy='joined')


Version.generation = association_proxy('version_group', 'generation')

VersionGroup.versions = relationship(Version,
    innerjoin=True,
    order_by=Version.id,
    backref=backref('version_group', lazy='joined'))
VersionGroup.generation = relationship(Generation,
    innerjoin=True, lazy='joined',
    backref=backref('version_groups', order_by=VersionGroup.order))
VersionGroup.version_group_regions = relationship(VersionGroupRegion,
    backref='version_group')
VersionGroup.regions = association_proxy('version_group_regions', 'region')
VersionGroup.pokemon_move_methods = relationship(PokemonMoveMethod,
    secondary=VersionGroupPokemonMoveMethod.__table__,
    primaryjoin=and_(VersionGroup.id == VersionGroupPokemonMoveMethod.version_group_id),
    secondaryjoin=and_(PokemonMoveMethod.id == VersionGroupPokemonMoveMethod.pokemon_move_method_id),
    backref="version_groups")
VersionGroup.machines = relationship(Machine,
    innerjoin=True,
    order_by=Machine.machine_number)


VersionGroupPokemonMoveMethod.version_group = relationship(VersionGroup,
    backref='version_group_move_methods')
VersionGroupPokemonMoveMethod.pokemon_move_method = relationship(PokemonMoveMethod,
    backref='version_group_move_methods')
