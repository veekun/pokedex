# Encoding: UTF-8

import pytest
parametrize = pytest.mark.parametrize

from sqlalchemy.orm.exc import NoResultFound

from pokedex.db import tables, connect, util, markdown

@pytest.fixture(scope="module")
def session(request):
    uri = request.config.getvalue("engine")
    return connect(uri)

def test_filter(session):
    q = session.query(tables.PokemonSpecies).filter(
            tables.PokemonSpecies.name == u"Marowak")
    assert q.one().identifier == 'marowak'

def test_languages(session):
    q = session.query(tables.PokemonSpecies).filter(
            tables.PokemonSpecies.name == u"Mightyena")
    pkmn = q.one()
    for lang, name in (
            ('en', u'Mightyena'),
            ('ja', u'グラエナ'),
            ('roomaji', u'Guraena'),
            ('fr', u'Grahyèna'),
        ):
        language = session.query(tables.Language).filter_by(
                identifier=lang).one()
        assert pkmn.name_map[language] == name

def test_bad_lang(session):
    with pytest.raises(KeyError):
        q = session.query(tables.PokemonSpecies).filter(
                tables.PokemonSpecies.name == u"Mightyena")
        pkmn = q.one()
        pkmn.names["identifier of a language that doesn't exist"]

def test_mutating(session):
    item = session.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    language = session.query(tables.Language).filter_by(
            identifier=u"de").one()
    item.name_map[language] = u"foo"
    assert item.name_map[language] == "foo"
    item.name_map[language] = u"xyzzy"
    assert item.name_map[language] == "xyzzy"

def test_mutating_default(session):
    item = session.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    item.name = u"foo"
    assert item.name == "foo"

def test_string_mapping(session):
    item = session.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    assert len(item.name_map) == len(item.names)
    for lang in item.names:
        assert item.name_map[lang] == item.names[lang].name
        assert lang in item.name_map
    assert "language that doesn't exist" not in item.name_map
    assert tables.Language() not in item.name_map

def test_new_language(session):
    item = session.query(tables.Item).filter_by(
            identifier=u"jade-orb").one()
    language = tables.Language()
    language.id = -1
    language.identifier = u'test'
    language.iso639 = language.iso3166 = u'--'
    language.official = False
    session.add(language)
    item.name_map[language] = u"foo"
    assert item.name_map[language] == "foo"
    assert language in item.name_map
    item.name_map[language] = u"xyzzy"
    assert item.name_map[language] == "xyzzy"

def test_markdown(session):
    move = session.query(tables.Move).filter_by(
            identifier=u"thunderbolt").one()
    language = session.query(tables.Language).filter_by(
            identifier=u"en").one()
    assert '10%' in move.effect.as_text()
    assert '10%' in move.effect_map[language].as_text()
    assert '10%' in move.effect.as_html()
    assert '10%' in move.effect_map[language].as_html()
    assert '10%' in unicode(move.effect)
    assert '10%' in unicode(move.effect_map[language])
    assert '10%' in move.effect.__html__()
    assert '10%' in move.effect_map[language].__html__()

def test_markdown_string(session):
    en = util.get(session, tables.Language, 'en')
    md = markdown.MarkdownString('[]{move:thunderbolt} [paralyzes]{mechanic:paralysis} []{form:sky shaymin}. []{pokemon:mewthree} does not exist.', session, en)
    assert unicode(md) == 'Thunderbolt paralyzes Sky Shaymin. mewthree does not exist.'
    assert md.as_html() == '<p><span>Thunderbolt</span> <span>paralyzes</span> <span>Sky Shaymin</span>. <span>mewthree</span> does not exist.</p>'

    class ObjectTestExtension(markdown.PokedexLinkExtension):
        def object_url(self, category, obj):
            if isinstance(obj, tables.PokemonForm):
                return "%s/%s %s" % (category, obj.form_identifier,
                        obj.species.identifier)
            else:
                return "%s/%s" % (category, obj.identifier)

    class IdentifierTestExtension(markdown.PokedexLinkExtension):
        def identifier_url(self, category, ident):
            return "%s/%s" % (category, ident)

    assert md.as_html(extension=ObjectTestExtension(session)) == (
            '<p><a href="move/thunderbolt">Thunderbolt</a> <span>paralyzes</span> <a href="form/sky shaymin">Sky Shaymin</a>. <span>mewthree</span> does not exist.</p>')
    assert md.as_html(extension=IdentifierTestExtension(session)) == (
            '<p><a href="move/thunderbolt">Thunderbolt</a> <a href="mechanic/paralysis">paralyzes</a> <a href="form/sky shaymin">Sky Shaymin</a>. <a href="pokemon/mewthree">mewthree</a> does not exist.</p>')

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

@pytest.mark.slow
@parametrize(
    ('parent_class', 'translation_class', 'column_name'),
    list(markdown_column_params())
)
def test_markdown_values(session, parent_class, translation_class, column_name):
    """Implementation for the above"""
    query = session.query(parent_class)
    if translation_class:
        query = query.join(translation_class)


    class TestExtension(markdown.PokedexLinkExtension):
        def object_url(self, category, obj):
            "Swallow good links"
            return 'ok'

        def identifier_url(self, category, ident):
            "Only allow mechanic links here (good links handled in object_url)"
            # Note: 'key' is a closed variable that gets set in the loop below
            assert category == 'mechanic', (
                    '%s: unknown link target: {%s:%s}' %
                    (key, category, ident))

    test_extension = TestExtension(session)

    for item in query:
        for language, md_text in getattr(item, column_name + '_map').items():

            if md_text is None:
                continue

            key = u"Markdown in {0} #{1}'s {2} (lang={3})".format(
                    parent_class.__name__, item.id, column_name, language.identifier)

            text = md_text.as_html(extension=test_extension)

            error_message = u"{0} leaves syntax cruft:\n{1}"
            error_message = error_message.format(key, text)

            assert not any(char in text for char in '[]{}'), error_message
