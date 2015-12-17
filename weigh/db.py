#!/usr/bin/env python3
# weight/db.py
# Database management functions

from contextlib import contextmanager
import logging
logger = logging.getLogger(__name__)
# from os import path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
# ... don't comment this out; PyInstaller ignores Alembic otherwise.
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

from weigh.alembic_current_revision import ALEMBIC_CURRENT_REVISION
from weigh.lang import OrderedNamespace
from weigh.settings import DATABASE_ENGINE


# =============================================================================
# Find out where Alembic files live
# =============================================================================

# def get_alembic_env_dir():
#     return path.join(path.abspath(path.dirname(__file__)),
#                      "..",
#                      "migrations")


# =============================================================================
# Get database URL for SQLAlchemy
# =============================================================================

def get_database_url():
    return DATABASE_ENGINE['url']


# =============================================================================
# Alembic revision/migration system
# =============================================================================

def get_head_revision_from_alembic(alembic_env_dir):
    script = ScriptDirectory(alembic_env_dir)
    return script.get_current_head()


def get_head_revision_without_alembic():
    return ALEMBIC_CURRENT_REVISION


def get_current_revision(database_url):
    engine = create_engine(database_url)
    conn = engine.connect()
    mig_context = MigrationContext.configure(conn)
    return mig_context.get_current_revision()


def ensure_migration_is_latest():
    # -------------------------------------------------------------------------
    # Where we are
    # -------------------------------------------------------------------------
    # alembic_env_dir = get_alembic_env_dir()
    # logger.debug("alembic_env_dir: {}".format(alembic_env_dir))
    # head_revision = get_head_revision_from_alembic(alembic_env_dir)
    head_revision = get_head_revision_without_alembic()
    logger.info("Intended database version: {}".format(head_revision))
    # -------------------------------------------------------------------------
    # Where we want to be
    # -------------------------------------------------------------------------
    database_url = get_database_url()
    logger.debug("database_url: {}".format(database_url))
    current_revision = get_current_revision(database_url)
    logger.info("Current database version: {}".format(current_revision))
    # -------------------------------------------------------------------------
    # Are we where we want to be?
    # -------------------------------------------------------------------------
    if current_revision != head_revision:
        raise ValueError(
            "Database revision should be {} but is {}; run "
            "update_database_structure.sh to fix".format(head_revision,
                                                         current_revision))


# =============================================================================
# Functions to get database session, etc.
# =============================================================================

def database_is_sqlite():
    database_url = get_database_url()
    return database_url.startswith("sqlite:")


def get_database_engine():
    database_url = get_database_url()
    engine = create_engine(database_url,
                           echo=DATABASE_ENGINE['echo'],
                           connect_args=DATABASE_ENGINE['connect_args'])
    sqlite = database_is_sqlite()
    if not sqlite:
        return engine

    # Hook in events to unbreak SQLite transaction support
    # Detailed in sqlalchemy/dialects/sqlite/pysqlite.py; see
    # "Serializable isolation / Savepoints / Transactional DDL"

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        # disable pysqlite's emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        # emit our own BEGIN
        conn.execute("BEGIN")

    return engine

# -----------------------------------------------------------------------------
# Plain functions: not thread-aware
# -----------------------------------------------------------------------------

# def get_database_session_thread_unaware():
#     engine = get_database_engine()
#     Session = sessionmaker(bind=engine)
#     return Session()
#
#
# @contextmanager
# def session_scope_thread_unaware():
#     # http://docs.sqlalchemy.org/en/latest/orm/session_basics.html#session-faq-whentocreate  # noqa
#     session = get_database_session_thread_unaware()
#     try:
#         yield session
#         session.commit()
#     except:
#         session.rollback()
#         raise
#     finally:
#         session.close()


# -----------------------------------------------------------------------------
# Thread-scoped versions
# -----------------------------------------------------------------------------
# http://docs.sqlalchemy.org/en/latest/orm/contextual.html
# https://writeonly.wordpress.com/2009/07/16/simple-read-only-sqlalchemy-sessions/  # noqa
# http://docs.sqlalchemy.org/en/latest/orm/session_api.html

def noflush_readonly(*args, **kwargs):
    logger.warning("Attempt to flush() a readonly database session blocked")


# def nocommit_readonly(*args, **kwargs):
#     logger.warning("Attempt to commit() a readonly database session blocked")


# def norollback_readonly(*args, **kwargs):
#     logger.warning("Attempt to rollback() a readonly database session blocked")


def get_database_session_thread_scope(readonly=False, autoflush=True):
    if readonly:
        autoflush = False
    engine = get_database_engine()
    session_factory = sessionmaker(bind=engine, autoflush=autoflush)
    Session = scoped_session(session_factory)
    session = Session()
    if readonly:
        session.flush = noflush_readonly
        # session.commit = nocommit_readonly
        # session.rollback = norollback_readonly
    return session


@contextmanager
def session_thread_scope(readonly=False):
    session = get_database_session_thread_scope(readonly)
    try:
        yield session
        if not readonly:
            session.commit()
    except:
        if not readonly:
            session.rollback()
        raise
    finally:
        session.close()


# =============================================================================
# Mixin to:
# - get plain dictionary-like object (with attributes so we can use x.y rather
#   than x['y']) from an SQLAlchemy ORM object
# - make a nice repr() default, maintaining field order
# =============================================================================

class SqlAlchemyAttrDictMixin(object):
    # See http://stackoverflow.com/questions/2537471
    # but more: http://stackoverflow.com/questions/2441796
    def get_attrdict(self):
        """
        Returns what looks like a plain object with the values of the
        SQLAlchemy ORM object.
        """
        columns = self.__table__.columns.keys()
        values = (getattr(self, x) for x in columns)
        zipped = zip(columns, values)
        return OrderedNamespace(zipped)

    def __repr__(self):
        return "<{classname}({kvp})>".format(
            classname=type(self).__name__,
            kvp=", ".join("{}={}".format(k, repr(v))
                          for k, v in self.get_attrdict().items())
        )

    @classmethod
    def from_attrdict(cls, attrdict):
        """
        Builds a new instance of the ORM object from values in an attrdict.
        """
        dictionary = attrdict.__dict__
        return cls(**dictionary)
