# encoding: utf8
from nose.tools import *
import unittest
from sqlalchemy.orm import class_mapper

from pokedex.db import tables, markdown

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
    for table in tables.table_classes:
        assert getattr(tables, table.__name__) is table

def test_texts():
    """Check DB schema for integrity of text columns & translations.

    Mostly protects against copy/paste oversights and rebase hiccups.
    If there's a reason to relax the tests, do it
    """
    for table in sorted(tables.table_classes, key=lambda t: t.__name__):
        if issubclass(table, tables.LanguageSpecific):
            good_formats = 'markdown plaintext gametext'.split()
            assert_text = '%s is language-specific'
        else:
            good_formats = 'identifier latex'.split()
            assert_text = '%s is not language-specific'
        mapper = class_mapper(table)
        for column in sorted(mapper.c, key=lambda c: c.name):
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
    for table in sorted(tables.table_classes, key=lambda t: t.__name__):
        if issubclass(table, tables.Named):
            assert issubclass(table, tables.OfficiallyNamed) or issubclass(table, tables.UnofficiallyNamed), table
            assert hasattr(table, 'identifier'), table
        else:
            assert not hasattr(table, 'identifier'), table
            if not issubclass(table, tables.LanguageSpecific):
                assert not hasattr(table, 'name'), table
