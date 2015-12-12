#!/usr/bin/env python3
# weight/db.py
# Database management functions

from contextlib import contextmanager
import logging
logger = logging.getLogger(__name__)
from os import path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from weigh.settings import DATABASE_ENGINE


# =============================================================================
# Find out where Alembic files live
# =============================================================================

def get_alembic_env_dir():
    return path.join(path.abspath(path.dirname(__file__)),
                     "..",
                     "migrations")


# =============================================================================
# Get database URL for SQLAlchemy
# =============================================================================

def get_database_url():
    return DATABASE_ENGINE['url']


# =============================================================================
# Alembic revision/migration system
# =============================================================================

def get_head_revision(alembic_env_dir):
    script = ScriptDirectory(alembic_env_dir)
    return script.get_current_head()


def get_current_revision(database_url):
    engine = create_engine(database_url)
    conn = engine.connect()
    mig_context = MigrationContext.configure(conn)
    return mig_context.get_current_revision()


def ensure_migration_is_latest():
    alembic_env_dir = get_alembic_env_dir()
    logger.debug("alembic_env_dir: {}".format(alembic_env_dir))
    database_url = get_database_url()
    logger.debug("database_url: {}".format(database_url))
    head_revision = get_head_revision(alembic_env_dir)
    logger.debug("Alembic head revision: {}".format(head_revision))
    current_revision = get_current_revision(database_url)
    logger.debug("Alembic current revision: {}".format(current_revision))
    if current_revision != head_revision:
        raise ValueError(
            "Alembic revision should be {} but is {}; run "
            "update_database_structure.sh to fix".format(head_revision,
                                                         current_revision))


# =============================================================================
# Function to get database session, etc.
# =============================================================================
# Will be thread-local.

def get_database_engine(sqlite=True):
    database_url = get_database_url()
    engine = create_engine(database_url, echo=DATABASE_ENGINE['echo'])
    if not database_url.startswith("sqlite:"):
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


def get_database_session():
    engine = get_database_engine()
    Session = sessionmaker(bind=engine)
    return Session()


@contextmanager
def session_scope():
    # http://docs.sqlalchemy.org/en/latest/orm/session_basics.html#session-faq-whentocreate  # noqa
    session = get_database_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
