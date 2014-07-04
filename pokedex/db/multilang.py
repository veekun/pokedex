from functools import partial

from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from sqlalchemy.orm import Query, aliased, mapper, relationship, synonym
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.orm.session import Session, object_session
from sqlalchemy.schema import Column, ForeignKey, Table
from sqlalchemy.sql.expression import and_, bindparam, select, exists
from sqlalchemy.sql.operators import ColumnOperators
from sqlalchemy.types import Integer

from pokedex.db import markdown

class LocalAssociationProxy(AssociationProxy, ColumnOperators):
    """An association proxy for names in the default language

    Over the regular association_proxy, this provides sorting and filtering
    capabilities, implemented via SQL subqueries.
    """
    def __clause_element__(self):
        q = select([self.remote_attr])
        q = q.where(self.target_class.foreign_id == self.owning_class.id)
        q = q.where(self.target_class.local_language_id == bindparam('_default_language_id'))
        return q

    def operate(self, op, *other, **kwargs):
        q = select([self.remote_attr])
        q = q.where(self.target_class.foreign_id == self.owning_class.id)
        q = q.where(self.target_class.local_language_id == bindparam('_default_language_id'))
        q = q.where(op(self.remote_attr, *other))
        return exists(q)


def _getset_factory_factory(column_name, string_getter):
    """Hello!  I am a factory for creating getset_factory functions for SQLA.
    I exist to avoid the closure-in-a-loop problem.
    """
    def getset_factory(underlying_type, instance):
        def getter(translations):
            if translations is None:
                return None
            text = getattr(translations, column_name)
            if text is None:
                return text
            session = object_session(translations)
            language = translations.local_language
            return string_getter(text, session, language)
        def setter(translations, value):
            # The string must be set on the Translation directly.
            raise AttributeError("Cannot set %s" % column_name)
        return getter, setter
    return getset_factory

def create_translation_table(_table_name, foreign_class, relation_name,
    language_class, relation_lazy='select', **kwargs):
    """Creates a table that represents some kind of data attached to the given
    foreign class, but translated across several languages.  Returns the new
    table's mapped class.  It won't be declarative, but it will have a
    `__table__` attribute so you can retrieve the Table object.

    `foreign_class` must have a `__singlename__`, currently only used to create
    the name of the foreign key column.

    Also supports the notion of a default language, which is attached to the
    session.  This is English by default, for historical and practical reasons.

    Usage looks like this:

        class Foo(Base): ...

        create_translation_table('foo_bars', Foo, 'bars',
            name = Column(...),
        )

        # Now you can do the following:
        foo.name
        foo.name_map['en']
        foo.foo_bars['en']

        foo.name_map['en'] = "new name"
        del foo.name_map['en']

        q.options(joinedload(Foo.bars_local))
        q.options(joinedload(Foo.bars))

    The following properties are added to the passed class:

    - `(relation_name)`, a relation to the new table.  It uses a dict-based
      collection class, where the keys are language identifiers and the values
      are rows in the created tables.
    - `(relation_name)_local`, a relation to the row in the new table that
      matches the current default language.
    - `(relation_name)_table`, the class created by this function.

    Note that these are distinct relations.  Even though the former necessarily
    includes the latter, SQLAlchemy doesn't treat them as linked; loading one
    will not load the other.  Modifying both within the same transaction has
    undefined behavior.

    For each column provided, the following additional attributes are added to
    Foo:

    - `(column)_map`, an association proxy onto `foo_bars`.
    - `(column)`, an association proxy onto `foo_bars_local`.

    Pardon the naming disparity, but the grammar suffers otherwise.

    Modifying these directly is not likely to be a good idea.

    For Markdown-formatted columns, `(column)_map` and `(column)` will give
    Markdown objects.
    """
    # n.b.: language_class only exists for the sake of tests, which sometimes
    # want to create tables entirely separate from the pokedex metadata

    foreign_key_name = foreign_class.__singlename__ + '_id'

    Translations = type(_table_name, (object,), {
        '_language_identifier': association_proxy('local_language', 'identifier'),
        'relation_name': relation_name,
        '__tablename__': _table_name,
    })

    # Create the table object
    table = Table(_table_name, foreign_class.__table__.metadata,
        Column(foreign_key_name, Integer, ForeignKey(foreign_class.id),
            primary_key=True, nullable=False,
            doc=u"ID of the %s these texts relate to" % foreign_class.__singlename__),
        Column('local_language_id', Integer, ForeignKey(language_class.id),
            primary_key=True, nullable=False,
            doc=u"Language these texts are in"),
    )
    Translations.__table__ = table

    # Add ye columns
    # Column objects have a _creation_order attribute in ascending order; use
    # this to get the (unordered) kwargs sorted correctly
    kwitems = kwargs.items()
    kwitems.sort(key=lambda kv: kv[1]._creation_order)
    for name, column in kwitems:
        column.name = name
        table.append_column(column)

    # Construct ye mapper
    mapper(Translations, table, properties={
        'foreign_id': synonym(foreign_key_name),
        'local_language': relationship(language_class,
            primaryjoin=table.c.local_language_id == language_class.id,
            innerjoin=True),
    })

    # Add full-table relations to the original class
    # Foo.bars_table
    setattr(foreign_class, relation_name + '_table', Translations)
    # Foo.bars
    setattr(foreign_class, relation_name, relationship(Translations,
        primaryjoin=foreign_class.id == Translations.foreign_id,
        collection_class=attribute_mapped_collection('local_language'),
    ))
    # Foo.bars_local
    # This is a bit clever; it uses bindparam() to make the join clause
    # modifiable on the fly.  db sessions know the current language and
    # populate the bindparam.
    # The 'dummy' value is to trick SQLA; without it, SQLA thinks this
    # bindparam is just its own auto-generated clause and everything gets
    # fucked up.
    local_relation_name = relation_name + '_local'
    setattr(foreign_class, local_relation_name, relationship(Translations,
        primaryjoin=and_(
            Translations.foreign_id == foreign_class.id,
            Translations.local_language_id == bindparam('_default_language_id',
                value='dummy', type_=Integer, required=True),
        ),
        foreign_keys=[Translations.foreign_id, Translations.local_language_id],
        uselist=False,
        lazy=relation_lazy,
    ))

    # Add per-column proxies to the original class
    for name, column in kwitems:
        getset_factory = None
        string_getter = column.info.get('string_getter')
        if string_getter:
            getset_factory = _getset_factory_factory(
                column.name, string_getter)

        # Class.(column) -- accessor for the default language's value
        setattr(foreign_class, name,
            LocalAssociationProxy(local_relation_name, name,
                    getset_factory=getset_factory))

        # Class.(column)_map -- accessor for the language dict
        # Need a custom creator since Translations doesn't have an init, and
        # these are passed as *args anyway
        def creator(language, value):
            row = Translations()
            row.local_language = language
            setattr(row, name, value)
            return row
        setattr(foreign_class, name + '_map',
            association_proxy(relation_name, name, creator=creator,
                    getset_factory=getset_factory))

    # Add to the list of translation classes
    foreign_class.translation_classes.append(Translations)

    # Done
    return Translations

class MultilangQuery(Query):
    def __iter__(self):
        if '_default_language_id' not in self._params:
            self._params = self._params.copy()
            self._params['_default_language_id'] = self.session.default_language_id
        return super(MultilangQuery, self).__iter__()

class MultilangSession(Session):
    """A tiny Session subclass that adds support for a default language.

    Needs to be used with `MultilangScopedSession`, below.
    """
    default_language_id = None
    markdown_extension_class = markdown.PokedexLinkExtension

    def __init__(self, *args, **kwargs):
        if 'default_language_id' in kwargs:
            self.default_language_id = kwargs.pop('default_language_id')

        markdown_extension_class = kwargs.pop('markdown_extension_class',
                self.markdown_extension_class)

        self.markdown_extension = markdown_extension_class(self)

        kwargs.setdefault('query_cls', MultilangQuery)

        super(MultilangSession, self).__init__(*args, **kwargs)

class MultilangScopedSession(ScopedSession):
    """Dispatches language selection to the attached Session."""

    @property
    def default_language_id(self):
        """Passes the new default language id through to the current session.
        """
        return self.registry().default_language_id

    @default_language_id.setter
    def default_language_id(self, new):
        self.registry().default_language_id = new

    @property
    def markdown_extension(self):
        return self.registry().markdown_extension
