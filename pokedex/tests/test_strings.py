# Encoding: UTF-8

from nose.tools import *

from pokedex.db import tables, connect

class TestStrings(object):
    def setup(self):
        self.connection = connect()

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
