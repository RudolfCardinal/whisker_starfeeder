#!/usr/bin/env python
# starfeeder/db.py
# Database management functions

"""
    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

from contextlib import contextmanager
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import os

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

from starfeeder.constants import ALEMBIC_CONFIG_FILENAME, CURRENT_DIR
from starfeeder.settings import get_database_settings


# =============================================================================
# Get database URL for SQLAlchemy
# =============================================================================

def get_database_url():
    settings = get_database_settings()
    return settings['url']


# =============================================================================
# Alembic revision/migration system
# =============================================================================
# http://stackoverflow.com/questions/24622170/using-alembic-api-from-inside-application-code  # noqa

def get_head_revision_from_alembic():
    """
    Ask Alembic what its head revision is.
    """
    os.chdir(CURRENT_DIR)  # so the directory in the config file works
    config = Config(ALEMBIC_CONFIG_FILENAME)
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def get_current_revision(database_url):
    """
    Ask the database what its current revision is.
    """
    engine = create_engine(database_url)
    conn = engine.connect()
    mig_context = MigrationContext.configure(conn)
    return mig_context.get_current_revision()


def get_current_and_head_revision():
    # -------------------------------------------------------------------------
    # Where we are
    # -------------------------------------------------------------------------
    # head_revision = get_head_revision_without_alembic()
    head_revision = get_head_revision_from_alembic()
    logger.info("Intended database version: {}".format(head_revision))
    # -------------------------------------------------------------------------
    # Where we want to be
    # -------------------------------------------------------------------------
    database_url = get_database_url()
    current_revision = get_current_revision(database_url)
    logger.info("Current database version: {}".format(current_revision))
    # -------------------------------------------------------------------------
    # Are we where we want to be?
    # -------------------------------------------------------------------------
    return (current_revision, head_revision)


def upgrade_database():
    """
    Use Alembic to upgrade our database.

    See http://alembic.readthedocs.org/en/latest/api/runtime.html
    but also, in particular, site-packages/alembic/command.py
    """

    os.chdir(CURRENT_DIR)  # so the directory in the config file works
    config = Config(ALEMBIC_CONFIG_FILENAME)
    script = ScriptDirectory.from_config(config)

    revision = 'head'  # where we want to get to

    def upgrade(rev, context):
        return script._upgrade_revs(revision, rev)

    logger.info(
        "Upgrading database to revision '{}' using Alembic".format(revision))

    with EnvironmentContext(config,
                            script,
                            fn=upgrade,
                            as_sql=False,
                            starting_rev=None,
                            destination_rev=revision,
                            tag=None):
        script.run_env()

    logger.info("Database upgrade completed")


# =============================================================================
# Functions to get database session, etc.
# =============================================================================

def database_is_sqlite():
    database_url = get_database_url()
    return database_url.startswith("sqlite:")


def get_database_engine():
    settings = get_database_settings()
    engine = create_engine(settings['url'],
                           echo=settings['echo'],
                           connect_args=settings['connect_args'])
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
# Plain functions: not thread-aware; generally AVOID these
# -----------------------------------------------------------------------------

def get_database_session_thread_unaware():
    engine = get_database_engine()
    Session = sessionmaker(bind=engine)
    return Session()


@contextmanager
def session_scope_thread_unaware():
    # http://docs.sqlalchemy.org/en/latest/orm/session_basics.html#session-faq-whentocreate  # noqa
    session = get_database_session_thread_unaware()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Thread-scoped versions
# -----------------------------------------------------------------------------
# http://docs.sqlalchemy.org/en/latest/orm/contextual.html
# https://writeonly.wordpress.com/2009/07/16/simple-read-only-sqlalchemy-sessions/  # noqa
# http://docs.sqlalchemy.org/en/latest/orm/session_api.html

def noflush_readonly(*args, **kwargs):
    logger.warning("Attempt to flush a readonly database session blocked")


def get_database_session_thread_scope(readonly=False, autoflush=True):
    if readonly:
        autoflush = False
    engine = get_database_engine()
    session_factory = sessionmaker(bind=engine, autoflush=autoflush)
    Session = scoped_session(session_factory)
    session = Session()
    if readonly:
        session.flush = noflush_readonly
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
