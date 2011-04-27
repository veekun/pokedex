# Encoding: UTF-8

"""Moves/transforms values in CSVs in an ad-hoc way, based mainly on column name

Auto-creates identifiers from names
Auto-creates names from identifiers
Copies IDs for foreign keys
Creates autoincrement-style IDs when missing
Sets text language to 9 (en), except when it sets to 1 (jp)

And looks good doing it!

This is an unmaintained one-shot script, only included in the repo for
reference.
"""

import csv
import re
import os
from StringIO import StringIO
from collections import namedtuple, defaultdict

from sqlalchemy.orm import class_mapper

from pokedex.db import tables, load

english_id = 9
japanese_id = 1

bw_version_group_id = 11

dir = load.get_default_csv_dir()

def tuple_key(tup):
    """Return a sort key for mixed int/string tuples.

    Strings sort first.
    """
    def generator():
        for item in tup:
            try:
                yield (1, int(item))
            except ValueError:
                yield (0, item)
    return tuple(generator())

class MakeFieldFuncs:
    """Various ways to get a new value from the old one"""
    @staticmethod
    def copy(field_name, source, **kwargs):
        """Plain copy"""
        return source[field_name]

    @staticmethod
    def main(field_name, source, **kwargs):
        """Populate aux table from the main table"""
        return source[field_name]

    @staticmethod
    def Main(field_name, source, **kwargs):
        """Capitalize"""
        return source[field_name].capitalize()

    @staticmethod
    def ident(source, **kwargs):
        """Craft an identifier from the 'identifier' or 'name' column"""
        return name2ident(source.get('identifier', source.get('name')))

    @staticmethod
    def Name(source, **kwargs):
        """Capitalize the name (or identifier) column"""
        name = source.get('name', source.get('identifier', None))
        name = ' '.join(word.capitalize() for word in name.split(' '))
        return name

    @staticmethod
    def f_id(source, **kwargs):
        """Capitalize the identifier column"""
        return source['identifier'].capitalize()

    @staticmethod
    def name(source, **kwargs):
        """Get the original name"""
        return source['name']

    @staticmethod
    def newid(i, source, **kwargs):
        """Assign a new "auto-incremented" id"""
        source['id'] = i  # hack to make srcid work
        return i

    @staticmethod
    def en(source, **kwargs):
        """Assign the value for English -- unless it's Japanese"""
        if source.get('version_group_id', None) == str(bw_version_group_id):
            return japanese_id
        return english_id

    @staticmethod
    def srcid(source, field_name, **kwargs):
        """The original table's id"""
        try:
            return source['id']
        except KeyError:
            if field_name == 'pokemon_form_group_id':
                # This one reuses another table's ID
                return source['pokemon_id']
            else:
                raise

def name2ident(name):
    ident = name.decode('utf-8').lower()
    ident = ident.replace(u'+', ' plus ')
    ident = re.sub(u'[ _–]+', u'-', ident)
    ident = re.sub(u'[\'./;’(),:]', u'', ident)
    ident = ident.replace(u'é', 'e')
    ident = ident.replace(u'♀', '-f')
    ident = ident.replace(u'♂', '-m')
    if ident in ('???', '????'):
        ident = 'unknown'
    elif ident == '!':
        ident = 'exclamation'
    elif ident == '?':
        ident = 'question'
    for c in ident:
        assert c in "abcdefghijklmnopqrstuvwxyz0123456789-", repr(ident)
    return ident


FieldSpec = namedtuple('FieldSpec', 'out name func')

def main():
    for table in sorted(tables.all_tables(), key=lambda t: t.__name__):
        datafilename = dir + '/' + table.__tablename__ + '.csv'
        classname = table.__name__
        if hasattr(table, 'object_table'):
            # This is an auxilliary table; it'll be processed with the main one
            continue
        else:
            print "%s: %s" % (classname, table.__tablename__)
        with open(datafilename) as datafile:
            datacsv = csv.reader(datafile, lineterminator='\n')
            orig_fields = datacsv.next()
            columns = class_mapper(table).c
            new_fields = []
            main_out = []
            outputs = {datafilename: main_out}
            name_out = None
            srcfiles = [datafilename]
            # Set new_fields to a list of FieldSpec object, one for each field we want in the csv
            for column in columns:
                name = column.name
                if name == 'identifier':
                    new_fields.append(FieldSpec(datafilename, column.name, MakeFieldFuncs.ident))
                elif name in orig_fields:
                    new_fields.append(FieldSpec(datafilename, column.name, MakeFieldFuncs.copy))
                elif name == 'id':
                    new_fields.append(FieldSpec(datafilename, column.name, MakeFieldFuncs.newid))
                elif name == 'language_id':
                    new_fields.insert(2, FieldSpec(datafilename, column.name, MakeFieldFuncs.en))
                else:
                    raise AssertionError(name)
            # Remember headers
            headers = {datafilename: list(field.name for field in new_fields)}
            # Pretty prnt :)
            for field in new_fields:
                print '    [{0.func.func_name:5}] {0.name}'.format(field)
            # Do pretty much the same for aux tables
            aux_tables = []
            for attrname in 'text_table prose_table'.split():
                aux_table = getattr(table, attrname, None)
                if aux_table:
                    aux_datafilename = dir + '/' + aux_table.__tablename__ + '.csv'
                    print "  %s: %s" % (aux_table.__name__, aux_table.__tablename__)
                    srcfiles.append(datafilename)
                    aux_tables.append(aux_table)
                    columns = class_mapper(aux_table).c
                    aux_out = []
                    outputs[aux_datafilename] = aux_out
                    aux_fields = []
                    for column in columns:
                        name = column.name
                        if name == 'language_id':
                            aux_fields.insert(1, FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.en))
                        elif name == 'name' and table.__name__ == 'ItemFlag':
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.f_id))
                        elif name == 'description' and table.__name__ == 'ItemFlag':
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.name))
                        elif name in orig_fields and name == 'name' and table.__name__ in 'PokemonColor ContestType BerryFirmness'.split():
                            # Capitalize these names
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.Name))
                        elif name in orig_fields and name in 'color flavor'.split() and table.__name__ == 'ContestType':
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.Main))
                        elif name in orig_fields:
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.main))
                        elif name == table.__singlename__ + '_id':
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.srcid))
                        elif name == 'name':
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.Name))
                        elif name == 'lang_id':
                            aux_fields.append(FieldSpec(aux_datafilename, column.name, MakeFieldFuncs.srcid))
                        else:
                            print orig_fields
                            raise AssertionError(name)
                        if name == 'name':
                            # If this table contains the name, remember that
                            name_fields = aux_fields
                            name_out = aux_out
                    # Sort aux tables nicely
                    def key(f):
                        if f.func == MakeFieldFuncs.srcid:
                            return 0
                        elif f.name == 'language_id':
                            return 1
                        elif f.name == 'name':
                            return 2
                        else:
                            return 10
                    aux_fields.sort(key=key)
                    new_fields += aux_fields
                    headers[aux_datafilename] = list(field.name for field in aux_fields)
                    # Pretty print :)
                    for field in aux_fields:
                        print '    [{0.func.func_name:5}] {0.name}'.format(field)
            # Do nothing if the table's the same
            if all(field.func == MakeFieldFuncs.copy for field in new_fields):
                print u'  → skipping'
                continue
            # Otherwise read the file
            # outputs will be a (filename -> list of rows) dict
            print u'  → reading'
            for autoincrement_id, src_row in enumerate(datacsv, start=1):
                row = dict(zip(orig_fields, src_row))
                new_rows = defaultdict(list)
                for field in new_fields:
                    new_rows[field.out].append(field.func(
                            source=row,
                            field_name=field.name,
                            i=autoincrement_id,
                        ))
                for name, row in new_rows.items():
                    outputs[name].append(row)
        # If there was a _names table, read that and append it to the
        # aux table that has names
        try:
            name_datafilename = dir + '/' + table.__singlename__ + '_names.csv'
            name_file = open(name_datafilename)
        except (AttributeError, IOError):
            pass
        else:
            print u'  → reading foreign names'
            with name_file:
                namecsv = csv.reader(name_file, lineterminator='\n')
                src_fields = namecsv.next()
                obj_id_fieldname = table.__singlename__ + '_id'
                assert src_fields == [obj_id_fieldname, 'language_id', 'name']
                for name_row in namecsv:
                    name_dict = dict(zip(src_fields, name_row))
                    row = []
                    for field in name_fields:
                        row.append(name_dict.get(field.name, ''))
                    name_out.append(row)
            os.unlink(name_datafilename)
        # For all out files, write a header & sorted rows
        print u'  → writing'
        for filename, rows in outputs.items():
            with open(filename, 'w') as outfile:
                outcsv = csv.writer(outfile, lineterminator='\n')
                outcsv.writerow(headers[filename])
                rows.sort(key=tuple_key)
                for row in rows:
                    outcsv.writerow(row)

if __name__ == '__main__':
    main()
