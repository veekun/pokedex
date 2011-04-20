# encoding: utf8
u"""Implements the markup used for description and effect text in the database.

The language used is a variation of Markdown and Markdown Extra.  There are
docs for each at http://daringfireball.net/projects/markdown/ and
http://michelf.com/projects/php-markdown/extra/ respectively.

Pokédex links are represented with the syntax `[text]{type:identifier}`, e.g.,
`[Eevee]{pokemon:eevee}`.  The actual code that parses these is in
spline-pokedex.
"""
from __future__ import absolute_import

import re

import markdown
import sqlalchemy.types

class MarkdownString(object):
    """Wraps a Markdown string.  Stringifies to the original text, but .as_html
    will return an HTML rendering.

    To make the __html__ property work, you must set this class's
    `default_link_extension` to a PokedexLinkExtension.  Yep, that's gross.
    """

    default_link_extension = None

    def __init__(self, source_text):
        self.source_text = source_text

    def __unicode__(self):
        return self.source_text

    def __str__(self):
        return unicode(self.source_text).encode()

    def __html__(self):
        return self.as_html(extension=self.default_link_extension)

    def as_html(self, session=None, object_url=None, identifier_url=None, language=None, extension=None):
        """Returns the string as HTML.

        Pass in current session, and optionally URL-making functions and the
        language. See PokedexLinkExtension for how they work.

        Alternatively, pass in a PokedexLinkExtension instance.
        """

        if not extension:
            extension = ParametrizedLinkExtension(session, object_url, identifier_url, language)

        md = markdown.Markdown(
            extensions=['extra', extension],
            safe_mode='escape',
            output_format='xhtml1',
        )

        return md.convert(self.source_text)

    def as_text(self, session):
        """Returns the string in a plaintext-friendly form.
        """
        # Since Markdown is pretty readable by itself, we just have to replace
        # the links by their text.
        # XXX: The tables get unaligned
        extension = ParametrizedLinkExtension(session)
        pattern = extension.link_pattern
        regex = '()%s()' % pattern.regex
        def handleMatch(m):
            return pattern.handleMatch(m).text
        return re.sub(regex, handleMatch, self.source_text)

def _markdownify_effect_text(move, effect_text):
    if effect_text is None:
        return effect_text
    effect_text = effect_text.replace(
        u'$effect_chance',
        unicode(move.effect_chance),
    )

    return MarkdownString(effect_text)

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
            newdict[key] = _markdownify_effect_text(obj, newdict[key])
        return newdict

class MarkdownColumn(sqlalchemy.types.TypeDecorator):
    """Generic SQLAlchemy column type for Markdown text.

    Do NOT use this for move effects!  They need to know what move they belong
    to so they can fill in, e.g., effect chances.  Use the MoveEffectProperty
    property class above.
    """
    impl = sqlalchemy.types.Unicode

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if not isinstance(value, basestring):
            # Can't assign, e.g., MarkdownString objects yet
            raise NotImplementedError

        return unicode(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return MarkdownString(value)

class PokedexLinkPattern(markdown.inlinepatterns.Pattern):
    """Matches [label]{category:target}.
    """
    regex = ur'(?x) \[ ([^]]*) \] \{ ([-a-z0-9]+) : ([-a-z0-9]+) \}'

    def __init__(self, extension):
        markdown.inlinepatterns.Pattern.__init__(self, self.regex)
        self.extension = extension

    def handleMatch(self, m):
        from pokedex.db import tables, util
        start, label, category, target, end = m.groups()
        try:
            table = dict(
                    ability=tables.Ability,
                    item=tables.Item,
                    location=tables.Location,
                    move=tables.Move,
                    pokemon=tables.Pokemon,
                    type=tables.Type,
                )[category]
        except KeyError:
            obj = name = target
            url = self.extension.identifier_url(category, obj)
        else:
            session = self.extension.session
            obj = util.get(self.extension.session, table, target)
            url = self.extension.object_url(category, obj)
            if table in [tables.Type]:
                # Type wants to be localized to the same language as the text
                language = self.extension.language
                name = None
                try:
                    name = obj.name_map[language]
                except KeyError:
                    pass
                if not name:
                    name = obj.name
            else:
                name = obj.name
        if url:
            el = self.extension.make_link(category, obj, url, label or name)
        else:
            el = markdown.etree.Element('span')
            el.text = markdown.AtomicString(label or name)
        return el

class PokedexLinkExtension(markdown.Extension):
    """Plugs the [foo]{bar:baz} syntax into the markdown parser.

    Subclases need to set the `session` attribute to the current session,
    and `language` to the language of the strings.

    To get links, subclasses must override object_url and/or identifier_url.
    If these return None, <span>s are used instead of <a>.
    """
    language = None

    def __init__(self):
        markdown.Extension.__init__(self)
        self.link_pattern = PokedexLinkPattern(self)

    def extendMarkdown(self, md, md_globals):
        md.inlinePatterns['pokedex-link'] = self.link_pattern

    def make_link(self, category, obj, url, text):
        """Make an <a> element

        Override this to set custom attributes, e.g. title.
        """
        el = markdown.etree.Element('a')
        el.set('href', url)
        el.text = markdown.AtomicString(text)
        return el

    def identifier_url(self, category, identifier):
        """Return the URL for the given {category:identifier} link

        For ORM objects, object_url is used instead (but may fall back to
        identifier_url).

        Returns None by default, which causes <span> to be used in place of <a>
        """
        return None

    def object_url(self, category, obj):
        """Return the URL for the ORM object obj

        Calls identifier_url by default.
        """
        return self.identifier_url(category, obj.identifier)

class ParametrizedLinkExtension(PokedexLinkExtension):
    def __init__(self, session, object_url=None, identifier_url=None, language=None):
        PokedexLinkExtension.__init__(self)
        self.language = language
        self.session = session
        if object_url:
            self.object_url = object_url
        if identifier_url:
            self.identifier_url = identifier_url
