from pokedex.db import metadata

### Helper functions for oracle
def rewrite_long_table_names():
    """Modifies the table names to disenvowel long table names.
    """
    t_names = metadata.tables.keys()

    table_names = list(t_names)
    table_objs = [metadata.tables[name] for name in table_names]

    # Prepare a dictionary to match old<->new names
    oradict = {}

    # Shorten table names, Oracle limits table and column names to 30 chars
    for table in table_objs:
        table._orginal_name = table.name[:]
        oradict[table.name]=table._orginal_name
        if len(table._orginal_name) > 30:
            for letter in ['a', 'e', 'i', 'o', 'u', 'y']:
                table.name=table.name.replace(letter,'')
            oradict[table.name]=table._orginal_name
    return oradict


def restore_long_table_names(metadata,oradict):
    """Modifies the table names to restore the long-naming.
    """
    for table in metadata.tables.values():
        table.name = oradict[table.name]
