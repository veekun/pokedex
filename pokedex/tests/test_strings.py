# Encoding: UTF-8

from nose.tools import *

from pokedex.db import tables, connect, util, markdown

class TestStrings(object):
    def setup(self):
        self.connection = connect()

    def teardown(self):
        self.connection.rollback()

    def test_filter(self):
        q = self.connection.query(tables.Pokemon).filter(
                tables.Pokemon.name == u"Marowak")
        assert q.one().identifier == 'marowak'

    def test_languages(self):
        q = self.connection.query(tables.Pokemon).filter(
                tables.Pokemon.name == u"Mightyena")
        pkmn = q.one()
        for lang, name in (
                ('en', u'Mightyena'),
                ('ja', u'グラエナ'),
                ('roomaji', u'Guraena'),
                ('fr', u'Grahyèna'),
            ):
            language = self.connection.query(tables.Language).filter_by(
                    identifier=lang).one()
            assert pkmn.name_map[language] == name

    @raises(KeyError)
    def test_bad_lang(self):
        q = self.connection.query(tables.Pokemon).filter(
                tables.Pokemon.name == u"Mightyena")
        pkmn = q.one()
        pkmn.names["identifier of a language that doesn't exist"]

    def test_mutating(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        language = self.connection.query(tables.Language).filter_by(
                identifier=u"de").one()
        item.name_map[language] = u"foo"
        assert item.name_map[language] == "foo"
        item.name_map[language] = u"xyzzy"
        assert item.name_map[language] == "xyzzy"

    def test_mutating_default(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        item.name = u"foo"
        assert item.name == "foo"

    def test_string_mapping(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        assert len(item.name_map) == len(item.names)
        for lang in item.names:
            assert item.name_map[lang] == item.names[lang].name
            assert lang in item.name_map
        assert "language that doesn't exist" not in item.name_map
        assert tables.Language() not in item.name_map

    def test_new_language(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        language = tables.Language()
        language.id = -1
        language.identifier = u'test'
        language.iso639 = language.iso3166 = u'--'
        language.official = False
        self.connection.add(language)
        item.name_map[language] = u"foo"
        assert item.name_map[language] == "foo"
        assert language in item.name_map
        item.name_map[language] = u"xyzzy"
        assert item.name_map[language] == "xyzzy"

    def test_markdown(self):
        move = self.connection.query(tables.Move).filter_by(
                identifier=u"thunderbolt").one()
        language = self.connection.query(tables.Language).filter_by(
                identifier=u"en").one()
        assert '10%' in move.effect.as_text()
        assert '10%' in move.effect_map[language].as_text()
        assert '10%' in move.effect.as_html()
        assert '10%' in move.effect_map[language].as_html()
        assert '10%' in unicode(move.effect)
        assert '10%' in unicode(move.effect_map[language])
        assert '10%' in move.effect.__html__()
        assert '10%' in move.effect_map[language].__html__()

    def test_markdown_string(self):
        en = util.get(self.connection, tables.Language, 'en')
        md = markdown.MarkdownString('[]{move:thunderbolt} [paralyzes]{mechanic:paralysis}', self.connection, en)
        assert unicode(md) == 'Thunderbolt paralyzes'
        assert md.as_html() == '<p><span>Thunderbolt</span> <span>paralyzes</span></p>'
        assert md.as_html(object_url=lambda category, obj: "%s/%s" % (category, obj.identifier)) == (
                '<p><a href="move/thunderbolt">Thunderbolt</a> <span>paralyzes</span></p>')
        print md.as_html(identifier_url=lambda category, ident: "%s/%s" % (category, ident))
        assert md.as_html(identifier_url=lambda category, ident: "%s/%s" % (category, ident)) == (
                '<p><a href="move/thunderbolt">Thunderbolt</a> <a href="mechanic/paralysis">paralyzes</a></p>')
