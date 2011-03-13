# Encoding: UTF-8

from nose.tools import *

from pokedex.db import tables, connect

class TestStrings(object):
    def setup(self):
        self.connection = connect()

    def teardown(self):
        self.connection.rollback()

    def test_filter(self):
        q = self.connection.query(tables.Pokemon).filter(
                tables.Pokemon.name == u"Marowak")
        assert q.one().identifier == 'marowak'

    def test_gt(self):
        # Assuming that the identifiers are just lowercase names
        q1 = self.connection.query(tables.Pokemon).filter(
                tables.Pokemon.name > u"Xatu").order_by(
                tables.Pokemon.id)
        q2 = self.connection.query(tables.Pokemon).filter(
                tables.Pokemon.identifier > u"xatu").order_by(
                tables.Pokemon.id)
        assert q1.all() == q2.all()

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
            assert pkmn.names[lang] == name

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
        item.names['de'] = u"foo"
        assert item.names['de'] == "foo"
        assert item.names[language] == "foo"
        item.names[language] = u"xyzzy"
        assert item.names['de'] == "xyzzy"
        assert item.names[language] == "xyzzy"

    def test_mutating_default(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        item.name = u"foo"
        assert item.name == "foo"

    def test_string_mapping(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        assert len(item.names) == len(item.texts)
        for lang in item.texts:
            assert item.names[lang] == item.texts[lang].name
            assert item.names[lang] == item.names[lang.identifier]
            assert lang in item.names
            assert lang.identifier in item.names
        assert "language that doesn't exist" not in item.names
        assert tables.Language() not in item.names

    def test_new_language(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        language = tables.Language()
        language.id = -1
        language.identifier = u'test'
        language.iso639 = language.iso3166 = u'--'
        language.official = False
        self.connection.add(language)
        item.names[u'test'] = u"foo"
        assert item.names[language] == "foo"
        assert item.names['test'] == "foo"
        assert 'de' in item.names
        assert language in item.names
        item.names[language] = u"xyzzy"
        assert item.names[language] == "xyzzy"
        assert item.names['test'] == "xyzzy"

    @raises(NotImplementedError)
    def test_delstring(self):
        item = self.connection.query(tables.Item).filter_by(
                identifier=u"jade-orb").one()
        del item.names['en']

    def test_markdown(self):
        move = self.connection.query(tables.Move).filter_by(
                identifier=u"thunderbolt").one()
        assert '10%' in move.effect.as_text
        assert '10%' in move.effects['en'].as_text
