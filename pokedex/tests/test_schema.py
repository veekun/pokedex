# encoding: utf8
from nose.tools import *
import unittest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import class_mapper, joinedload, sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base

from pokedex.db import tables, markdown
from pokedex.db.multilang import create_translation_table

def test_variable_names():
    """We want pokedex.db.tables to export tables using the class name"""
    for varname in dir(tables):
        if not varname[0].isupper():
            continue
        table = getattr(tables, varname)
        try:
            if not issubclass(table, tables.TableBase) or table is tables.TableBase:
                continue
        except TypeError:
            continue
        classname = table.__name__
        if classname and varname[0].isupper():
            assert varname == classname, '%s refers to %s' % (varname, classname)
    for table in tables.mapped_classes:
        assert getattr(tables, table.__name__) is table

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

    class FauxSession(Session):
        def execute(self, clause, params=None, *args, **kwargs):
            if not params:
                params = {}
            params.setdefault('_default_language', 'en')
            return super(FauxSession, self).execute(clause, params, *args, **kwargs)

    # OK, create all the tables and gimme a session
    Base.metadata.create_all()
    sess = sessionmaker(engine, class_=FauxSession)()

    # Create some languages and foos to bind together
    lang_en = Language(identifier='en')
    sess.add(lang_en)
    lang_jp = Language(identifier='jp')
    sess.add(lang_jp)
    lang_ru = Language(identifier='ru')
    sess.add(lang_ru)

    foo = Foo()
    sess.add(foo)

    # Commit so the above get primary keys filled in
    sess.commit()

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

def test_texts():
    """Check DB schema for integrity of text columns & translations.

    Mostly protects against copy/paste oversights and rebase hiccups.
    If there's a reason to relax the tests, do it
    """
    classes = []
    for cls in tables.mapped_classes:
        classes.append(cls)
        classes += cls.translation_classes
    for cls in classes:
        if hasattr(cls, 'local_language') or hasattr(cls, 'language'):
            good_formats = 'markdown plaintext gametext'.split()
            assert_text = '%s is language-specific'
        else:
            good_formats = 'identifier latex'.split()
            assert_text = '%s is not language-specific'
        columns = sorted(cls.__table__.c, key=lambda c: c.name)
        for column in columns:
            format = column.info.get('format', None)
            if format is not None:
                if format not in good_formats:
                    raise AssertionError(assert_text % column)
                is_markdown = isinstance(column.type, markdown.MarkdownColumn)
                if is_markdown != (format == 'markdown'):
                    raise AssertionError('%s: markdown format/column type mismatch' % column)
                if (format != 'identifier') and (column.name == 'identifier'):
                    raise AssertionError('%s: identifier column name/type mismatch' % column)
                if column.info.get('official', None) and format not in 'gametext plaintext':
                    raise AssertionError('%s: official text with bad format' % column)
            else:
                if isinstance(column.type, (markdown.MarkdownColumn, tables.Unicode)):
                    raise AssertionError('%s: text column without format' % column)
            if column.name == 'name' and format != 'plaintext':
                raise AssertionError('%s: non-plaintext name' % column)
            # No mention of English in the description
            assert 'English' not in column.info['description'], column

def test_identifiers_with_names():
    """Test that named tables have identifiers, and non-named tables don't

    ...have either names or identifiers.
    """
    for table in sorted(tables.mapped_classes, key=lambda t: t.__name__):
        if hasattr(table, 'name'):
            assert hasattr(table, 'identifier'), table
        else:
            assert not hasattr(table, 'identifier'), table
