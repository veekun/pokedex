from sqlalchemy import engine_from_config, orm

from ..defaults import get_default_db_uri
from .tables import Language, metadata
from .multilang import MultilangSession, MultilangScopedSession


def connect(uri=None, session_args={}, engine_args={}, engine_prefix=''):
    """Connects to the requested URI.  Returns a session object.

    With the URI omitted, attempts to connect to a default SQLite database
    contained within the package directory.

    Calling this function also binds the metadata object to the created engine.
    """

    # If we didn't get a uri, fall back to the default
    if uri is None:
        uri = engine_args.get(engine_prefix + 'url', None)
    if uri is None:
        uri = get_default_db_uri()

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
    engine_args[engine_prefix + 'url'] = uri
    engine = engine_from_config(engine_args, prefix=engine_prefix)
    conn = engine.connect()
    metadata.bind = engine

    all_session_args = dict(autoflush=True, autocommit=False, bind=engine)
    all_session_args.update(session_args)
    sm = orm.sessionmaker(class_=MultilangSession, language_class=Language,
        **all_session_args)
    session = MultilangScopedSession(sm)

    # Default to English.  Warning, magic constant, blah blah.  Trying to fetch
    # English here would kinda break on new databases.  TODO still not an ideal
    # solution, I guess.
    session._default_language_id = 9

    return session
