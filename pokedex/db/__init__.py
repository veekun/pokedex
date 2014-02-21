# encoding: utf-8
import re

from sqlalchemy import engine_from_config, orm

from ..defaults import get_default_db_uri
from .tables import Language, metadata
from .multilang import MultilangSession, MultilangScopedSession

ENGLISH_ID = 9


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
    if uri.startswith('mysql:'):
        # MySQL uses latin1 for connections by default even if the server is
        # otherwise oozing with utf8; charset fixes this
        if 'charset' not in uri:
            uri += '?charset=utf8'

        # Tables should be InnoDB, in the event that we're creating them, and
        # use UTF-8 goddammit!
        for table in metadata.tables.values():
            table.kwargs['mysql_engine'] = 'InnoDB'
            table.kwargs['mysql_charset'] = 'utf8'

    ### Do some fixery for Oracle
    if uri.startswith('oracle:') or uri.startswith('oracle+cx_oracle:'):
        # Oracle requires auto_setinputsizes=False (or at least a special
        # set of exclusions from it, which I don't know)
        if 'auto_setinputsizes' not in uri:
            uri += '?auto_setinputsizes=FALSE'

    ### Connect
    engine_args[engine_prefix + 'url'] = uri
    engine = engine_from_config(engine_args, prefix=engine_prefix)
    conn = engine.connect()
    metadata.bind = engine

    all_session_args = dict(autoflush=True, autocommit=False, bind=engine)
    all_session_args.update(session_args)
    sm = orm.sessionmaker(class_=MultilangSession,
        default_language_id=ENGLISH_ID, **all_session_args)
    session = MultilangScopedSession(sm)

    return session

def identifier_from_name(name):
    """Make a string safe to use as an identifier.

    Valid characters are lowercase alphanumerics and "-". This function may
    raise ValueError if it can't come up with a suitable identifier.

    This function is useful for scripts which add things with names.
    """
    if isinstance(name, str):
        identifier = name.decode('utf-8')
    else:
        identifier = name
    identifier = identifier.lower()
    identifier = identifier.replace(u'+', u' plus ')
    identifier = re.sub(u'[ _–]+', u'-', identifier)
    identifier = re.sub(u"['./;’(),:]", u'', identifier)
    identifier = identifier.replace(u'é', u'e')
    identifier = identifier.replace(u'♀', u'-f')
    identifier = identifier.replace(u'♂', u'-m')
    if identifier in (u'???', u'????'):
        identifier = u'unknown'
    elif identifier == u'!':
        identifier = u'exclamation'
    elif identifier == u'?':
        identifier = u'question'

    if not identifier.replace(u"-", u"").isalnum():
        raise ValueError(identifier)
    return identifier
