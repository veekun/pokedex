# encoding: utf8
r"""Functionality for handling reStructuredText fields in the database.

This module defines the following extra text roles.  By default, they merely
bold the contents of the tag.  Calling code may redefine them with
`docutils.parsers.rst.roles.register_local_role`.  Docutils role extensions
are, apparently, global.

`ability`
`item`
`move`
`pokemon`
    These all wrap objects of the corresponding type.  They're intended to be
    used to link to these items.

`mechanic`
    This is a general-purpose reference role.  The Web Pokédex uses these to
    link to pages on mechanics.  Amongst the things tagged with this are:
    * Stats, e.g., Attack, Speed
    * Major status effects, e.g., paralysis, freezing
    * Minor status effects not unique to a single move, e.g., confusion
    * Battle mechanics, e.g., "regular damage", "lowers/raises" a stat

`data`
    Depends on context.  Created for move effect chances; some effects contain
    text like "Has a \:data\:\`move.effect_chance\` chance to...".  Here, the
    enclosed text is taken as a reference to a column on the associated move.
    Other contexts may someday invent their own constructs.

    This is actually implemented by adding a `_pokedex_handle_data` attribute
    to the reST document itself, which the `data` role handler attempts to
    call.  This function takes `rawtext` and `text` as arguments and should
    return a reST node.
"""

import cgi

from docutils.frontend import OptionParser
from docutils.io import Output
import docutils.nodes
from docutils.parsers.rst import Parser, roles
import docutils.utils
from docutils.writers.html4css1 import Writer as HTMLWriter
from docutils.writers import UnfilteredWriter

import sqlalchemy.types

### Subclasses of bits of docutils, to munge it into doing what I want
class HTMLFragmentWriter(HTMLWriter):
    """Translates reST to HTML, but only as a fragment.  Enclosing <body>,
    <head>, and <html> tags are omitted.
    """

    def apply_template(self):
        subs = self.interpolation_dict()
        return subs['body']


class TextishTranslator(docutils.nodes.SparseNodeVisitor):
    """A simple translator that tries to return plain text that still captures
    the spirit of the original (basic) formatting.

    This will probably not be useful for anything complicated; it's only meant
    for extremely simple text.
    """

    def __init__(self, document):
        self.document = document
        self.translated = u''

    def visit_Text(self, node):
        """Text is left alone."""
        self.translated += node.astext()

    def depart_paragraph(self, node):
        """Append a blank line after a paragraph, unless it's the last of its
        siblings.
        """
        if not node.parent:
            return

        # Loop over siblings.  If we see a sibling after we see this node, then
        # append the blank line
        seen_node = False
        for sibling in node.parent:
            if sibling is node:
                seen_node = True
                continue

            if seen_node:
                self.translated += u'\n\n'
                return

class TextishWriter(UnfilteredWriter):
    """Translates reST back into plain text, aka more reST.  Difference is that
    custom roles are handled, so you get "50% chance" instead of junk.
    """

    def translate(self):
        visitor = TextishTranslator(self.document)
        self.document.walkabout(visitor)
        self.output = visitor.translated


class UnicodeOutput(Output):
    """reST Unicode output.  The distribution only has a StringOutput, and I
    want me some Unicode.
    """

    def write(self, data):
        """Returns data (a Unicode string) unaltered."""
        return data


### Text roles

def generic_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    node = docutils.nodes.emphasis(rawtext, text, **options)
    return [node], []

roles.register_local_role('ability', generic_role)
roles.register_local_role('item', generic_role)
roles.register_local_role('location', generic_role)
roles.register_local_role('move', generic_role)
roles.register_local_role('type', generic_role)
roles.register_local_role('pokemon', generic_role)
roles.register_local_role('mechanic', generic_role)

def data_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    document = inliner.document
    node = document._pokedex_handle_data(rawtext, text)
    return [node], []

roles.register_local_role('data', data_role)


### Public classes

class RstString(object):
    """Wraps a reStructuredText string.  Stringifies to the original text, but
    may be translated to HTML with .as_html().
    """

    def __init__(self, source_text, document_properties={}):
        """
        `document_properties`
            List of extra properties to attach to the reST document object.
        """
        self.source_text = source_text
        self.document_properties = document_properties
        self._rest_document = None

    def __unicode__(self):
        return self.source_text

    @property
    def rest_document(self):
        """reST parse tree of the source text.

        This property is lazy-loaded.
        """

        # Return it if we have it
        if self._rest_document:
            return self._rest_document

        parser = Parser()
        settings = OptionParser(components=(Parser,HTMLWriter)).get_default_values()
        document = docutils.utils.new_document('pokedex', settings)

        # Add properties (in this case, probably just the data role handler)
        document.__dict__.update(self.document_properties)

        # PARSE
        parser.parse(self.source_text, document)

        self._rest_document = document
        return document

    @property
    def as_html(self):
        """Returns the string as HTML4."""

        document = self.rest_document

        # Check for errors; don't want to leave the default error message cruft
        # in here
        if document.next_node(condition=docutils.nodes.system_message):
            # Boo!  Cruft.
            return u"""
                <p><em>Error in markup!  Raw source is below.</em></p>
                <pre>{0}</pre>
            """.format( cgi.escape(self.source_text) )

        destination = UnicodeOutput()
        writer = HTMLFragmentWriter()
        return writer.write(document, destination)

    @property
    def as_text(self):
        """Returns the string mostly unchanged, save for our custom roles."""

        document = self.rest_document

        destination = UnicodeOutput()
        writer = TextishWriter()
        return writer.write(document, destination)


class MoveEffectProperty(object):
    """Property that wraps a move effect.  Used like this:

        MoveClass.effect = MoveEffectProperty('effect')

        some_move.effect            # returns an RstString
        some_move.effect.as_html    # returns a chunk of HTML

    This class also performs `%` substitution on the effect, replacing
    `%(effect_chance)d` with the move's actual effect chance.  Also this is a
    lie and it doesn't yet.
    """

    def __init__(self, effect_column):
        self.effect_column = effect_column

    def __get__(self, move, move_class):
        # Attach a function for handling the `data` role
        # XXX make this a little more fault-tolerant..  maybe..
        def data_role_func(rawtext, text):
            assert text[0:5] == 'move.'
            newtext = getattr(move, text[5:])
            return docutils.nodes.Text(newtext, rawtext)

        return RstString(getattr(move.move_effect, self.effect_column),
                         document_properties=dict(
                             _pokedex_handle_data=data_role_func))

class RstTextColumn(sqlalchemy.types.TypeDecorator):
    """Generic column type for reST text.

    Do NOT use this for move effects!  They need to know what move they belong
    to so they can fill in, e.g., effect chances.
    """
    impl = sqlalchemy.types.Unicode

    def process_bind_param(self, value, dialect):
        return unicode(value)

    def process_result_value(self, value, dialect):
        return RstString(value)
