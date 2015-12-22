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
# import subprocess
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
# ... don't comment this out; PyInstaller ignores Alembic otherwise.
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

# from starfeeder.alembic.current_revision import ALEMBIC_CURRENT_REVISION
from starfeeder.settings import DATABASE_ENGINE


# =============================================================================
# Find out where Alembic files live
# =============================================================================

if getattr(sys, 'frozen', False):
    # Running inside a PyInstaller bundle.
    # __file__ will look like: '.../starfeeder/starfeeder/db.pyc'
    # Normally
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    CURRENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
else:
    # Running normally.
    # __file__ will look like: '.../starfeeder/db.py'
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_CONFIG_FILENAME = os.path.join(CURRENT_DIR, 'alembic.ini')


# =============================================================================
# Get database URL for SQLAlchemy
# =============================================================================

def get_database_url():
    return DATABASE_ENGINE['url']


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


# def get_head_revision_without_alembic():
#     """
#     Uses our hacky Python file (written by a shell script) to track the
#     revision. SUPERSEDED; we'll use Alembic directly.
#     """
#     return ALEMBIC_CURRENT_REVISION


def get_current_revision(database_url):
    """
    Ask the database what its current revision is.
    """
    engine = create_engine(database_url)
    conn = engine.connect()
    mig_context = MigrationContext.configure(conn)
    return mig_context.get_current_revision()


def ensure_migration_is_latest():
    """
    Raise an exception if our database is not at the latest revision.
    """
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
    if current_revision != head_revision:
        raise ValueError("""
===============================================================================
Database revision should be {} but is {}.

- If the database version is too low, run starfeeder with the
  "--upgrade-database" parameter (because your database is too old).

- If the database version is too high, upgrade starfeeder (because you're
  trying to use an old starfeeder version with a newer database).
===============================================================================
        """.format(head_revision, current_revision))


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
    logger.warning("Attempt to flush a readonly database session blocked")


# def nocommit_readonly(*args, **kwargs):
#     logger.warning("Attempt to commit a readonly database session blocked")


# def norollback_readonly(*args, **kwargs):
#     logger.warning("Attempt to rollback a readonly database session blocked")


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
