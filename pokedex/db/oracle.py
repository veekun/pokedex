from pokedex.db import metadata

### Helper functions for oracle
def rewrite_long_table_names():
    """Modifies the table names to disenvowel long table names.
    Takes the metadata from memory or uses the imported one.

    Returns a dictionary matching short names -> long names.
    """

    # Load table names from metadata
    t_names = metadata.tables.keys()

    table_names = list(t_names)
    table_objs = [metadata.tables[name] for name in table_names]

    # Prepare a dictionary to match old<->new names
    dictionary = {}

    # Shorten table names, Oracle limits table and column names to 30 chars
    for table in table_objs:
        table._orginal_name = table.name[:]
        dictionary[table.name]=table._orginal_name
        if len(table._orginal_name) > 30:
            for letter in ['a', 'e', 'i', 'o', 'u', 'y']:
                table.name=table.name.replace(letter,'')
            dictionary[table.name]=table._orginal_name
    return dictionary


def restore_long_table_names(metadata,dictionary):
    """Modifies the table names to restore the long-naming.

    `metadata`
        The metadata to restore.

    `dictionary`
        The dictionary matching short name -> long name.
    """
    for table in metadata.tables.values():
        table.name = dictionary[table.name]
