# encoding: utf8

import pytest

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import class_mapper, joinedload, sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base

from pokedex.db import tables, markdown
from pokedex.db.multilang import MultilangScopedSession, MultilangSession, \
    create_translation_table

parametrize = pytest.mark.parametrize

@parametrize('varname', [attr for attr in dir(tables) if not attr.startswith('_')])
def test_variable_names(varname):
    """We want pokedex.db.tables to export tables using the class name"""
    table = getattr(tables, varname)
    try:
        if not issubclass(table, tables.TableBase) or table is tables.TableBase:
            return
    except TypeError:
        return
    classname = table.__name__
    if classname and varname[0].isupper():
        assert varname == classname, '%s refers to %s' % (varname, classname)

@parametrize('table', tables.mapped_classes)
def test_variable_names_2(table):
    """We also want all of the tables exported"""
    assert getattr(tables, table.__name__) is table

def test_class_order():
    """The declarative classes should be defined in alphabetical order.
    Except for Language which should be first.
    """
    class_names = [table.__name__ for table in tables.mapped_classes]
    def key(name):
        return name != 'Language', name
    print [(a,b) for (a,b) in zip(class_names, sorted(class_names, key=key)) if a!=b]
    assert class_names == sorted(class_names, key=key)

def test_i18n_table_creation():
    """Creates and manipulates a magical i18n table, completely independent of
    the existing schema and data.  Makes sure that the expected behavior of the
    various proxies and columns works.
    """
    Base = declarative_base()
    engine = create_engine("sqlite:///:memory:", echo=True)

    Base.metadata.bind = engine

    # Need this for the foreign keys to work!
    class Language(Base):
        __tablename__ = 'languages'
        id = Column(Integer, primary_key=True, nullable=False)
        identifier = Column(String(2), nullable=False, unique=True)

    class Foo(Base):
        __tablename__ = 'foos'
        __singlename__ = 'foo'
        id = Column(Integer, primary_key=True, nullable=False)
        translation_classes = []

    FooText = create_translation_table('foo_text', Foo, 'texts',
        language_class=Language,
        name = Column(String(100)),
    )

    # OK, create all the tables and gimme a session
    Base.metadata.create_all()
    sm = sessionmaker(class_=MultilangSession)
    sess = MultilangScopedSession(sm)

    # Create some languages and foos to bind together
    lang_en = Language(identifier='en')
    sess.add(lang_en)
    lang_jp = Language(identifier='jp')
    sess.add(lang_jp)
    lang_ru = Language(identifier='ru')
    sess.add(lang_ru)

    foo = Foo()
    sess.add(foo)

    # Commit so the above get primary keys filled in, then give the
    # session the language id
    sess.commit()
    # Note that this won't apply to sessions created in other threads, but that
    # ought not be a problem!
    sess.default_language_id = lang_en.id

    # Give our foo some names, as directly as possible
    foo_text = FooText()
    foo_text.foreign_id = foo.id
    foo_text.local_language_id = lang_en.id
    foo_text.name = 'english'
    sess.add(foo_text)

    foo_text = FooText()
    foo_text.foo_id = foo.id
    foo_text.local_language_id = lang_jp.id
    foo_text.name = 'nihongo'
    sess.add(foo_text)

    # Commit!  This will expire all of the above.
    sess.commit()

    ### Test 1: re-fetch foo and check its attributes
    foo = sess.query(Foo).params(_default_language='en').one()

    # Dictionary of language identifiers => names
    assert foo.name_map[lang_en] == 'english'
    assert foo.name_map[lang_jp] == 'nihongo'

    # Default language, currently English
    assert foo.name == 'english'

    sess.expire_all()

    ### Test 2: querying by default language name should work
    foo = sess.query(Foo).filter_by(name='english').one()

    assert foo.name == 'english'

    sess.expire_all()

    ### Test 3: joinedload on the default name should appear to work
    # THIS SHOULD WORK SOMEDAY
    #    .options(joinedload(Foo.name)) \
    foo = sess.query(Foo) \
        .options(joinedload(Foo.texts_local)) \
        .one()

    assert foo.name == 'english'

    sess.expire_all()

    ### Test 4: joinedload on all the names should appear to work
    # THIS SHOULD ALSO WORK SOMEDAY
    #    .options(joinedload(Foo.name_map)) \
    foo = sess.query(Foo) \
        .options(joinedload(Foo.texts)) \
        .one()

    assert foo.name_map[lang_en] == 'english'
    assert foo.name_map[lang_jp] == 'nihongo'

    sess.expire_all()

    ### Test 5: Mutating the dict collection should work
    foo = sess.query(Foo).one()

    foo.name_map[lang_en] = 'different english'
    foo.name_map[lang_ru] = 'new russian'

    sess.commit()

    assert foo.name_map[lang_en] == 'different english'
    assert foo.name_map[lang_ru] == 'new russian'

classes = []
for cls in tables.mapped_classes:
    classes.append(cls)
    classes += cls.translation_classes
@parametrize('cls', classes)
def test_texts(cls):
    """Check DB schema for integrity of text columns & translations.

    Mostly protects against copy/paste oversights and rebase hiccups.
    If there's a reason to relax the tests, do it
    """
    if hasattr(cls, 'local_language') or hasattr(cls, 'language'):
        good_formats = 'markdown plaintext gametext'.split()
        assert_text = '%s is language-specific'
    else:
        good_formats = 'identifier latex'.split()
        assert_text = '%s is not language-specific'
    columns = sorted(cls.__table__.c, key=lambda c: c.name)
    text_columns = []
    for column in columns:
        format = column.info.get('format', None)
        if format is not None:
            if format not in good_formats:
                pytest.fail(assert_text % column)
            if (format != 'identifier') and (column.name == 'identifier'):
                pytest.fail('%s: identifier column name/type mismatch' % column)
            if column.info.get('official', None) and format not in 'gametext plaintext':
                pytest.fail('%s: official text with bad format' % column)
            text_columns.append(column)
        else:
            if isinstance(column.type, tables.Unicode):
                pytest.fail('%s: text column without format' % column)
        if column.name == 'name' and format != 'plaintext':
            pytest.fail('%s: non-plaintext name' % column)
        # No mention of English in the description
        if column.doc and u'English' in column.doc:
            pytest.fail("%s: description mentions English" % column)
    # If there's more than one text column in a translation table,
    # they have to be nullable, to support missing translations
    if hasattr(cls, 'local_language') and len(text_columns) > 1:
        for column in text_columns:
            assert column.nullable

@parametrize('table', tables.mapped_classes)
def test_identifiers_with_names(table):
    """Test that named tables have identifiers
    """
    for translation_class in table.translation_classes:
        if hasattr(translation_class, 'name'):
            assert hasattr(table, 'identifier'), table
