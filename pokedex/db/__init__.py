import pkg_resources

from sqlalchemy import MetaData, Table, create_engine, orm

from .tables import metadata

def connect(uri=None, session_args={}, engine_args={}):
    """Connects to the requested URI.  Returns a session object.

    With the URI omitted, attempts to connect to a default SQLite database
    contained within the package directory.

    Calling this function also binds the metadata object to the created engine.
    """

    # Default to a URI within the package, which was hopefully created at some point
    if not uri:
        sqlite_path = pkg_resources.resource_filename('pokedex',
                                                      'data/pokedex.sqlite')
        uri = 'sqlite:///' + sqlite_path

    ### Do some fixery for MySQL
    if uri[0:5] == 'mysql':
        # MySQL uses latin1 for connections by default even if the server is
        # otherwise oozing with utf8; charset fixes this
        if 'charset' not in uri:
            uri += '?charset=utf8'

        # Tables should be InnoDB, in the event that we're creating them, and
        # use UTF-8 goddammit!
        for table in metadata.tables.values():
            table.kwargs['mysql_engine'] = 'InnoDB'
            table.kwargs['mysql_charset'] = 'utf8'

    ### Connect
    engine = create_engine(uri, **engine_args)
    conn = engine.connect()
    metadata.bind = engine

    all_session_args = dict(autoflush=True, autocommit=False, bind=engine)
    all_session_args.update(session_args)
    sm = orm.sessionmaker(**all_session_args)
    session = orm.scoped_session(sm)

    return session
