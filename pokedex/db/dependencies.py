import sqlalchemy.sql.visitors as visitors

from pokedex.db.tables import metadata

# stolen from sqlalchemy.sql.util.sort_tables
def compute_dependencies(tables):
    """Construct a reverse dependency graph for the given tables.

    Returns a dict which maps a table to the list of tables which depend on it.
    """
    tables = list(tables)
    graph = {}
    def visit_foreign_key(fkey):
        if fkey.use_alter:
            return
        parent_table = fkey.column.table
        if parent_table in tables:
            child_table = fkey.parent.table
            if parent_table is not child_table:
                graph.setdefault(parent_table, []).append(child_table)

    for table in tables:
        visitors.traverse(table,
                          {'schema_visitor': True},
                          {'foreign_key': visit_foreign_key})

        graph.setdefault(table, []).extend(table._extra_dependencies)

    return graph

#: The dependency graph for pokedex.db.tables
_pokedex_graph = compute_dependencies(metadata.tables.values())

def find_dependent_tables(tables, graph=None):
    """Recursively find all tables which depend on the given tables.

    The returned set does not include the original tables.
    """
    if graph is None:
        graph = _pokedex_graph
    tables = list(tables)
    dependents = set()
    def add_dependents_of(table):
        for dependent_table in graph.get(table, []):
            if dependent_table not in dependents:
                dependents.add(dependent_table)
                add_dependents_of(dependent_table)

    for table in tables:
        add_dependents_of(table)

    dependents -= set(tables)

    return dependents
