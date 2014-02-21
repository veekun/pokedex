from pokedex.db import metadata

### Helper functions for oracle
def rewrite_long_table_names():
    """Disemvowels all table names over thirty characters."""
    # Load tables from metadata
    table_objs = metadata.tables.values()

    # Shorten table names, Oracle limits table and column names to 30 chars
    for table in table_objs:
        table._original_name = table.name

        if len(table.name) > 30:
            for letter in 'aeiouy':
                table.name = table.name.replace(letter, '')

def restore_long_table_names():
    """Modifies the table names to restore the long-naming."""
    for table in metadata.tables.values():
        table.name = table._original_name
        del table._original_name
