# encoding: utf8
u"""Implements the markup used for description and effect text in the database.

The language used is a variation of Markdown and Markdown Extra.  There are
docs for each at http://daringfireball.net/projects/markdown/ and
http://michelf.com/projects/php-markdown/extra/ respectively.

Pokédex links are represented with the extended syntax `[name]{type}`, e.g.,
`[Eevee]{pokemon}`.  The actual code that parses these is in spline-pokedex.
"""
from __future__ import absolute_import

import markdown
import sqlalchemy.types

class MarkdownString(object):
    """Wraps a Markdown string.  Stringifies to the original text, but .as_html
    will return an HTML rendering.

    To add extensions to the rendering (which is necessary for rendering links
    correctly, and which spline-pokedex does), you must append to this class's
    `markdown_extensions` list.  Yep, that's gross.
    """

    markdown_extensions = ['extra']

    def __init__(self, source_text):
        self.source_text = source_text
        self._as_html = None

    def __unicode__(self):
        return self.source_text

    @property
    def as_html(self):
        """Returns the string as HTML4."""

        if self._as_html:
            return self._as_html

        md = markdown.Markdown(
            extensions=self.markdown_extensions,
            safe_mode='escape',
            output_format='xhtml1',
        )

        self._as_html = md.convert(self.source_text)

        return self._as_html

    @property
    def as_text(self):
        """Returns the string in a plaintext-friendly form.

        At the moment, this is just the original source text.
        """
        return self.source_text

def _markdownify_effect_text(move, effect_text):
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
