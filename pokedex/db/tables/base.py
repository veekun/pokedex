# encoding: utf8

from functools import partial

from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy import Column, MetaData
from sqlalchemy.types import Boolean, Integer, Unicode

from pokedex.db import multilang


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

    def __repr__(self):
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
    u"""A language the Pokémon games have been translated into."""
    __tablename__ = 'languages'
    __singlename__ = 'language'
    id = Column(Integer, primary_key=True, nullable=False,
        doc=u"A numeric ID")
    iso639 = Column(Unicode(79), nullable=False,
        doc=u"The two-letter code of the country where this language is spoken. Note that it is not unique.",
        info=dict(format='identifier'))
    iso3166 = Column(Unicode(79), nullable=False,
        doc=u"The two-letter code of the language. Note that it is not unique.",
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
