# Encoding: UTF-8

u"""Automatic documentation generation for pokédex tables

This adds a "dex-table" directive to Sphinx, which works like "autoclass",
but documents Pokédex mapped classes.
"""
# XXX: This assumes all the tables are in pokedex.db.tables

import functools
import textwrap

from docutils import nodes
from docutils.statemachine import ViewList
from sphinx.util.compat import Directive, make_admonition
from sphinx.locale import _
from sphinx.domains.python import PyClasslike
from sphinx.util.docfields import Field, GroupedField, TypedField
from sphinx.ext.autodoc import ClassLevelDocumenter

from sqlalchemy import types
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.properties import RelationshipProperty
from sqlalchemy.orm import Mapper, configure_mappers
from sqlalchemy.ext.associationproxy import AssociationProxy
from pokedex.db.markdown import MoveEffectPropertyMap, MoveEffectProperty

from pokedex.db import tables, markdown

# Make sure all the backrefs are in place
configure_mappers()


column_to_cls = {}
for cls in tables.mapped_classes:
    for column in cls.__table__.c:
        column_to_cls[column] = cls

class dextabledoc(nodes.Admonition, nodes.Element):
    pass

def visit_todo_node(self, node):
    self.visit_admonition(node)

def depart_todo_node(self, node):
    self.depart_admonition(node)

def column_type_str(column):
    """Extract the type name from a SQLA column
    """
    type_ = column.type
    # We're checking the specific type here: no issubclass
    if type(type_) in (types.Integer, types.SmallInteger):
        return 'int'
    if type(type_) == types.Boolean:
        return 'bool'
    if type(type_) == types.Unicode:
        return u'unicode – %s' % column.info['format']
    if type(type_) == types.UnicodeText:
        return u'unicode – %s' % column.info['format']
    if type(type_) == types.Enum:
        return 'enum: [%s]' % ', '.join(type_.enums)
    if type(type_) == markdown.MarkdownColumn:
        return 'markdown'
    raise ValueError(repr(type_))

common_columns = 'id identifier name'.split()

def column_header(c, class_name=None, transl_name=None, show_type=True,
        relation=None, relation_name=None):
    """Return the column header for the given column"""
    result = []
    if relation_name:
        name = relation_name
    else:
        name = c.name
    if class_name:
        result.append(u'%s.\ **%s**' % (class_name, name))
    else:
        result.append(u'**%s**' % c.name)
    if c.foreign_keys:
        for fk in c.foreign_keys:
            if fk.column in column_to_cls:
                foreign_cls = column_to_cls[fk.column]
                if relation_name and relation_name + '_id' == c.name:
                    result.append(u'(%s →' % c.name)
                elif relation_name:
                    result.append(u'(**%s** →' % c.name)
                else:
                    result.append(u'(→')
                result.append(u':class:`~pokedex.db.tables.%s`.%s)' % (
                        foreign_cls.__name__,
                        fk.column.name
                    ))
                break
    elif show_type:
        result.append(u'(*%s*)' % column_type_str(c))
    if transl_name:
        result.append(u'via *%s*' % transl_name)
    return ' '.join(result)


def with_header(header=None):
    """Decorator that adds a section header if there's a any output

    The decorated function should yield output lines; if there are any the
    header gets added.
    """
    def wrap(func):
        @functools.wraps(func)
        def wrapped(cls, remaining_attrs):
            result = list(func(cls, remaining_attrs))
            if result:
                # Sphinx/ReST doesn't allow "-----" just anywhere :(
                yield u''
                yield u'.. raw:: html'
                yield u''
                yield u'    <hr>'
                yield u''
                if header:
                    yield header + u':'
                    yield u''
                for row in result:
                    yield row
        return wrapped
    return wrap

### Section generation functions

def generate_table_header(cls, remaining_attrs):
    first_line, sep, next_lines = unicode(cls.__doc__).partition(u'\n')
    yield first_line
    for line in textwrap.dedent(next_lines).split('\n'):
        yield line
    yield ''

    yield u'Table name: *%s*' % cls.__tablename__
    try:
        yield u'(single: *%s*)' % cls.__singlename__
    except AttributeError:
        pass
    yield u''

    yield u'Primary key: %s.' % u', '.join(
        u'**%s**' % col.key for col in cls.__table__.primary_key.columns)
    yield u''

def generate_common(cls, remaining_attrs):
    common_col_headers = []
    for c in cls.__table__.c:
        if c.name in common_columns:
            common_col_headers.append(column_header(c, show_type=False))
            remaining_attrs.remove(c.name)
    for translation_class in cls.translation_classes:
        for c in translation_class.__table__.c:
            if c.name in common_columns:
                common_col_headers.append(column_header(c, None,
                        translation_class.__table__.name, show_type=False))
                remaining_attrs.remove(c.name)

    if common_col_headers:
        if len(common_col_headers) > 1:
            common_col_headers[-1] = 'and ' + common_col_headers[-1]
        if len(common_col_headers) > 2:
            separator = u', '
        else:
            separator = u' '
        yield u'Has'
        yield separator.join(common_col_headers) + '.'
        yield u''

@with_header(u'Columns')
def generate_columns(cls, remaining_attrs):
    name = cls.__name__
    for c in [c for c in cls.__table__.c if c.name not in common_columns]:
        remaining_attrs.remove(c.name)
        relation_name = c.name[:-3]
        if c.name.endswith('_id') and relation_name in remaining_attrs:
            relation = getattr(cls, relation_name)
            yield column_header(c, name,
                    relation=relation, relation_name=relation_name)
            remaining_attrs.remove(relation_name)
        else:
            yield column_header(c, name) + ':'
        yield u''
        if c.doc:
            yield u'  ' + unicode(c.doc)
            yield u''

@with_header(u'Internationalized strings')
def generate_strings(cls, remaining_attrs):
    for translation_class in cls.translation_classes:
        for c in translation_class.__table__.c:
            if 'format' in c.info:
                remaining_attrs.discard(c.name)
                remaining_attrs.discard(c.name + '_map')
                if c.name in common_columns:
                    continue
                yield column_header(c, cls.__name__,
                        translation_class.__table__.name)
                yield u''
                if c.doc:
                    yield u'  ' + unicode(c.doc)
                    yield u''

@with_header(u'Relationships')
def generate_relationships(cls, remaining_attrs):
    def isrelationship(prop):
        return isinstance(prop, InstrumentedAttribute) and isinstance(prop.property, RelationshipProperty)

    for attr_name in sorted(remaining_attrs):
        prop = getattr(cls, attr_name)
        if not isrelationship(prop):
            continue
        rel = prop.property
        yield u'%s.\ **%s**' % (cls.__name__, attr_name)
        class_name = u':class:`~pokedex.db.tables.%s`' % rel.mapper.class_.__name__
        if rel.uselist:
            class_name = u'[%s]' % class_name
        yield u'(→ %s)' % class_name
        if rel.doc:
            yield u''
            yield u'  ' + unicode(rel.doc)
        if rel.secondary is not None:
            yield u''
            yield '  Association table: ``%s``' % rel.secondary
        #if rel.primaryjoin is not None:
        #    yield u''
        #    yield '  Join condition: ``%s``' % rel.primaryjoin
        #    if rel.secondaryjoin is not None:
        #        yield '  , ``%s``' % rel.secondaryjoin
        if rel.order_by:
            yield u''
            yield u'  '
            yield '  Ordered by: ' + u', '.join(
                    u'``%s``' % o for o in rel.order_by)
        yield u''
        remaining_attrs.remove(attr_name)

@with_header(u'Association Proxies')
def generate_associationproxies(cls, remaining_attrs):
    for attr_name in sorted(remaining_attrs):
        prop = getattr(cls, attr_name)
        if isinstance(prop, AssociationProxy):
            yield u'%s.\ **%s**:' % (cls.__name__, attr_name)
            yield '``{prop.remote_attr.key}`` of ``self.{prop.local_attr.key}``'.format(
                    prop=prop)
            yield u''
            remaining_attrs.remove(attr_name)


@with_header(u'Undocumented')
def generate_undocumented(cls, remaining_attrs):
    for c in sorted([c for c in remaining_attrs if isinstance(getattr(cls, c),
            (InstrumentedAttribute, AssociationProxy,
                MoveEffectPropertyMap, MoveEffectProperty))]):
        yield u''
        yield u'%s.\ **%s**' % (cls.__name__, c)
        remaining_attrs.remove(c)

@with_header(None)
def generate_other(cls, remaining_attrs):
    for c in sorted(remaining_attrs):
        yield u''
        member = getattr(cls, c)
        if callable(member):
            yield '.. automethod:: %s.%s' % (cls.__name__, c)
        else:
            yield '.. autoattribute:: %s.%s' % (cls.__name__, c)
        yield u''
    remaining_attrs.clear()


class DexTable(PyClasslike):
    """The actual Sphinx documentation generation whatchamacallit
    """
    doc_field_types = [
        TypedField('field', label='Fields',
            typerolename='obj', typenames=('fieldname', 'type')),
        ]

    def get_signature_prefix(self, sig):
        return ''
        #return u'mapped class '

    def run(self):
        section = nodes.section()
        super_result = super(DexTable, self).run()
        title_text = self.names[0][0]
        section += nodes.title(text=title_text)
        section += super_result
        section['ids'] = ['dex-table-%s' % title_text.lower()]
        return [section]

    def before_content(self):
        name = self.names[0][0]
        for cls in tables.mapped_classes:
            if name == cls.__name__:
                break
        else:
            raise ValueError('Table %s not found' % name)
        table = cls.__table__

        remaining_attrs = set(x for x in dir(cls) if not x.startswith('_'))
        remaining_attrs.difference_update(['metadata', 'translation_classes',
                'add_relationships', 'summary_column'])
        for transl_class in cls.translation_classes:
            remaining_attrs.difference_update([
                    transl_class.relation_name,
                    transl_class.relation_name + '_table',
                    transl_class.relation_name + '_local',
                ])

        generated_content = []  # Just a list of lines!

        generated_content.extend(generate_table_header(cls, remaining_attrs))
        generated_content.extend(generate_common(cls, remaining_attrs))
        generated_content.extend(generate_columns(cls, remaining_attrs))
        generated_content.extend(generate_strings(cls, remaining_attrs))
        generated_content.extend(generate_relationships(cls, remaining_attrs))
        generated_content.extend(generate_associationproxies(cls, remaining_attrs))
        generated_content.extend(generate_undocumented(cls, remaining_attrs))
        generated_content.extend(generate_other(cls, remaining_attrs))

        generated_content.append(u'')
        self.content = ViewList(generated_content + list(self.content))
        return super(DexTable, self).before_content()

    def get_index_text(self, modname, name_cls):
        return '%s (mapped class)' % name_cls[0]

def setup(app):
    app.add_directive('dex-table', DexTable)

    # XXX: Specify that this depends on pokedex.db.tables ...?
