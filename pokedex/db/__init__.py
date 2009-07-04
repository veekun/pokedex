from sqlalchemy import MetaData, Table, create_engine, orm

from .tables import metadata

def connect(uri, **kwargs):
    """Connects to the requested URI.  Returns a session object.

    Calling this function also binds the metadata object to the created engine.
    """

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
    engine = create_engine(uri)
    conn = engine.connect()
    metadata.bind = engine

    session_args = dict(autoflush=True, autocommit=False, bind=engine)
    session_args.update(kwargs)
    sm = orm.sessionmaker(**session_args)
    session = orm.scoped_session(sm)

    return session
