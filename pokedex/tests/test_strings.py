# Encoding: UTF-8

import pytest
from sqlalchemy.orm.exc import NoResultFound

from pokedex.tests import positional_params

from pokedex.db import tables, connect, util, markdown

connection = connect()

def test_filter():
    q = connection.query(tables.PokemonSpecies).filter(
            tables.PokemonSpecies.name == u"Marowak")
    assert q.one().identifier == 'marowak'

def test_languages():
    q = connection.query(tables.PokemonSpecies).filter(
            tables.PokemonSpecies.name == u"Mightyena")
    pkmn = q.one()
    for lang, name in (
            ('en', u'Mightyena'),
            ('ja', u'グラエナ'),
            ('roomaji', u'Guraena'),
            ('fr', u'Grahyèna'),
        ):
        language = connection.query(tables.Language).filter_by(
                identifier=lang).one()
        assert pkmn.name_map[language] == name

def test_bad_lang():
    with pytest.raises(KeyError):
        q = connection.query(tables.PokemonSpecies).filter(
                tables.PokemonSpecies.name == u"Mightyena")
        pkmn = q.one()
        pkmn.names["identifier of a language that doesn't exist"]

def test_mutating():
    item = connection.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    language = connection.query(tables.Language).filter_by(
            identifier=u"de").one()
    item.name_map[language] = u"foo"
    assert item.name_map[language] == "foo"
    item.name_map[language] = u"xyzzy"
    assert item.name_map[language] == "xyzzy"

def test_mutating_default():
    item = connection.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    item.name = u"foo"
    assert item.name == "foo"

def test_string_mapping():
    item = connection.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    assert len(item.name_map) == len(item.names)
    for lang in item.names:
        assert item.name_map[lang] == item.names[lang].name
        assert lang in item.name_map
    assert "language that doesn't exist" not in item.name_map
    assert tables.Language() not in item.name_map

def test_new_language():
    item = connection.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    language = tables.Language()
    language.id = -1
    language.identifier = u'test'
    language.iso639 = language.iso3166 = u'--'
    language.official = False
    connection.add(language)
    item.name_map[language] = u"foo"
    assert item.name_map[language] == "foo"
    assert language in item.name_map
    item.name_map[language] = u"xyzzy"
    assert item.name_map[language] == "xyzzy"

def test_markdown():
    move = connection.query(tables.Move).filter_by(
            identifier=u"thunderbolt").one()
    language = connection.query(tables.Language).filter_by(
            identifier=u"en").one()
    assert '10%' in move.effect.as_text()
    assert '10%' in move.effect_map[language].as_text()
    assert '10%' in move.effect.as_html()
    assert '10%' in move.effect_map[language].as_html()
    assert '10%' in unicode(move.effect)
    assert '10%' in unicode(move.effect_map[language])
    assert '10%' in move.effect.__html__()
    assert '10%' in move.effect_map[language].__html__()

def test_markdown_string():
    en = util.get(connection, tables.Language, 'en')
    md = markdown.MarkdownString('[]{move:thunderbolt} [paralyzes]{mechanic:paralysis}', connection, en)
    assert unicode(md) == 'Thunderbolt paralyzes'
    assert md.as_html() == '<p><span>Thunderbolt</span> <span>paralyzes</span></p>'

    class ObjectTestExtension(markdown.PokedexLinkExtension):
        def object_url(self, category, obj):
            return "%s/%s" % (category, obj.identifier)

    class IdentifierTestExtension(markdown.PokedexLinkExtension):
        def identifier_url(self, category, ident):
             return "%s/%s" % (category, ident)

    assert md.as_html(extension_cls=ObjectTestExtension) == (
            '<p><a href="move/thunderbolt">Thunderbolt</a> <span>paralyzes</span></p>')
    assert md.as_html(extension_cls=IdentifierTestExtension) == (
            '<p><a href="move/thunderbolt">Thunderbolt</a> <a href="mechanic/paralysis">paralyzes</a></p>')

def markdown_column_params():
    """Check all markdown values

    Scans the database schema for Markdown columns, runs through every value
    in each, and ensures that it's valid Markdown.
    """

    # Move effects have their own special wrappers.  Explicitly test them separately
    yield tables.Move, None, 'effect'
    yield tables.Move, None, 'short_effect'

    for cls in tables.mapped_classes:
        for translation_cls in cls.translation_classes:
            for column in translation_cls.__table__.c:
                if column.info.get('string_getter') == markdown.MarkdownString:
                    yield cls, translation_cls, column.name

@positional_params(*markdown_column_params())
def test_markdown_values(parent_class, translation_class, column_name):
    """Implementation for the above"""
    query = connection.query(parent_class)
    if translation_class:
        query = query.join(translation_class)
    for item in query:
        for language, markdown in getattr(item, column_name + '_map').items():

            if markdown is None:
                continue

            key = u"Markdown in {0} #{1}'s {2} (lang={3})".format(
                    parent_class.__name__, item.id, column_name, language.identifier)

            try:
                text = markdown.as_text()
            except NoResultFound:
                assert False, u"{0} references something that doesn't exist:\n{1}".format(
                        key, markdown.source_text)
            except AttributeError:
                print markdown
                raise

            error_message = u"{0} leaves syntax cruft:\n{1}"
            error_message = error_message.format(key, text)

            assert not any(char in text for char in '[]{}'), error_message
