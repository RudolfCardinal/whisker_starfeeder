#!/usr/bin/env python
# starfeeder/alembic/env.py

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

from alembic import context
from sqlalchemy import engine_from_config, pool
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
# import os
# import sys


from starfeeder.constants import LOG_FORMAT, LOG_DATEFMT
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                    level=logging.DEBUG)

config = context.config

# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_dir = os.path.abspath(os.path.join(current_dir,
#                                            os.pardir, os.pardir))
# logger.info("Adding to PYTHONPATH: {}".format(project_dir))
# sys.path.append(project_dir)
# logger.debug("sys.path: {}".format(sys.path))

from starfeeder.models import Base
target_metadata = Base.metadata

from starfeeder.settings import DATABASE_ENGINE
config.set_main_option('sqlalchemy.url', DATABASE_ENGINE['url'])


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    # RNC
    context.configure(
        url=url,
        target_metadata=target_metadata,
        render_as_batch=True,  # for SQLite mode; http://stackoverflow.com/questions/30378233  # noqa
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # RNC
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # for SQLite mode; http://stackoverflow.com/questions/30378233  # noqa
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()