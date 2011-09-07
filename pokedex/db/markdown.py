# encoding: utf8
u"""Implements the markup used for description and effect text in the database.

The language used is a variation of Markdown and Markdown Extra.  There are
docs for each at http://daringfireball.net/projects/markdown/ and
http://michelf.com/projects/php-markdown/extra/ respectively.

Pokédex links are represented with the syntax `[label]{category:identifier}`,
e.g., `[Eevee]{pokemon:eevee}`. The label can (and should) be left out, in
which case it is replaced by the name of the thing linked to.
"""
from __future__ import absolute_import

import re

import markdown
from sqlalchemy.orm.session import object_session

class MarkdownString(object):
    """Wraps a Markdown string.

    Use unicode() and __html__ for text and HTML representations.
    The as_text() and as_html() functions do the same, but accept optional
    arguments that may affect the rendering.
    The `source_text` property holds the original text.

    init args:
    `source_text`: the text in Markdown syntax
    `session`: A DB session used for looking up linked objects
    `language`: The language the string is in. If None, the session default
        is used.
    """

    default_link_extension = None

    def __init__(self, source_text, session, language):
        self.source_text = source_text
        self.session = session
        self.language = language

    def __unicode__(self):
        return self.as_text()

    def __str__(self):
        return self.as_text().encode()

    def __html__(self):
        return self.as_html()

    def as_html(self, extension_cls=None):
        """Returns the string as HTML.

        Pass a custom `extension_cls` to use your own class to generate links.
        The default (and recommended superclass) is `PokedexLinkExtension`,
        described below.
        """

        if extension_cls is None:
            extension_cls = self.session.markdown_extension_class
        extension = extension_cls(self.session)

        md = markdown.Markdown(
            extensions=['extra', extension],
            safe_mode='escape',
            output_format='xhtml1',
        )

        return md.convert(self.source_text)

    def as_text(self):
        """Returns the string in a plaintext-friendly form.

        Currently there are no tunable parameters
        """
        # Since Markdown is pretty readable by itself, we just have to replace
        # the links by their text.
        # XXX: The tables get unaligned

        link_maker = PokedexLinkExtension(self.session)
        pattern = PokedexLinkPattern(link_maker, self.session, self.language)
        regex = '()%s()' % pattern.regex
        def handleMatch(m):
            return pattern.handleMatch(m).text

        return re.sub(regex, handleMatch, self.source_text)

def _markdownify_effect_text(move, effect_text, language=None):
    session = object_session(move)

    if effect_text is None:
        return effect_text
    effect_text = effect_text.replace(
        u'$effect_chance',
        unicode(move.effect_chance),
    )

    return MarkdownString(effect_text, session, language)

class MoveEffectProperty(object):
    """Property that wraps move effects.  Used like this:

        MoveClass.effect = MoveEffectProperty('effect')

        some_move.effect            # returns a MarkdownString
        some_move.effect.as_html    # returns a chunk of HTML

    This class also performs simple substitution on the effect, replacing
    `$effect_chance` with the move's actual effect chance.

    Use `MoveEffectPropertyMap` for dict-like association proxies.
    """

    def __init__(self, effect_column):
        self.effect_column = effect_column

    def __get__(self, obj, cls):
        prop = getattr(obj.move_effect, self.effect_column)
        return _markdownify_effect_text(obj, prop)

class MoveEffectPropertyMap(MoveEffectProperty):
    """Similar to `MoveEffectProperty`, but works on dict-like association
    proxies.
    """
    def __get__(self, obj, cls):
        prop = getattr(obj.move_effect, self.effect_column)
        newdict = dict(prop)
        for key in newdict:
            newdict[key] = _markdownify_effect_text(obj, newdict[key], key)
        return newdict


class PokedexLinkPattern(markdown.inlinepatterns.Pattern):
    """Matches [label]{category:target}.

    Handles matches using factory
    """
    regex = ur'(?x) \[ ([^]]*) \] \{ ([-a-z0-9]+) : ([-a-z0-9]+) \}'

    def __init__(self, factory, session, string_language=None, game_language=None):
        markdown.inlinepatterns.Pattern.__init__(self, self.regex)
        self.factory = factory
        self.session = session
        self.string_language = string_language
        self.game_language = game_language

    def handleMatch(self, m):
        from pokedex.db import tables, util
        start, label, category, target, end = m.groups()
        try:
            table = dict(
                    ability=tables.Ability,
                    item=tables.Item,
                    location=tables.Location,
                    move=tables.Move,
                    pokemon=tables.PokemonSpecies,
                    type=tables.Type,
                )[category]
        except KeyError:
            obj = name = target
            url = self.factory.identifier_url(category, obj)
        else:
            session = self.session
            obj = util.get(self.session, table, target)
            url = self.factory.object_url(category, obj)
            url = url or self.factory.identifier_url(category, obj.identifier)
            name = None
            # Translations can be incomplete; in which case we want to use a
            # fallback.
            if table in [tables.Type] and self.string_language:
                # Type wants to be localized to the same language as the text
                name = obj.name_map.get(self.string_language)
            if not name and self.game_language:
                name = obj.name_map.get(self.game_language)
            if not name:
                name = obj.name
        if url:
            el = self.factory.make_link(category, obj, url, label or name)
        else:
            el = markdown.etree.Element('span')
            el.text = markdown.AtomicString(label or name)
        return el

class PokedexLinkExtension(markdown.Extension):
    u"""Markdown extension that translates the syntax used in effect text:

    `[label]{category:identifier}` is treated as a link to a Pokédex object,
    where `category` is the table's singular name, and `label` is an optional
    link title that defaults to the object's name in the current language.
    """
    def __init__(self, session):
        self.session = session

    def extendMarkdown(self, md, md_globals):
        pattern = PokedexLinkPattern(self, self.session)
        md.inlinePatterns['pokedex-link'] = pattern

    def make_link(self, category, obj, url, text):
        """Make an <a> element

        Override this to set custom attributes, e.g. title.
        """
        el = markdown.etree.Element('a')
        el.set('href', url)
        el.text = markdown.AtomicString(text)
        return el

    def identifier_url(self, category, identifier):
        """Return the URL for the given {category:identifier} link.  For ORM
        objects, object_url is tried first.

        Returns None by default, which causes <span> to be used in place of
        <a>.
        """
        return None

    def object_url(self, category, obj):
        """Return the URL for the ORM object `obj`.

        Returns None by default, which causes identifier_url to be tried.
        """
        return None
