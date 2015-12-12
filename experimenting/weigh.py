#!/usr/bin/env python3
# weigh/weigh.py

import argparse
import logging
logger = logging.getLogger(__name__)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from twisted.internet import reactor

from weigh.alembic_extra import ensure_migration_is_latest
from weigh.settings import (
    DATABASE_ENGINE,
)
from weigh.models import (
    Weight,
)
from weigh.dialogs import MainWindow
from weigh.task import WeighTask


# =============================================================================
# Main
# =============================================================================

def do_something(session):
    w = Weight(rfid="my_rfid", weight_mg=123456)
    session.add(w)

    print(w)
    session.commit()
    print(w)


def main(alembic_env_dir):
    # Arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    args = parser.parse_args()

    # Logging
    LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
    LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=loglevel)

    # Database checks/connection
    database_url = DATABASE_ENGINE['url']
    logger.debug("alembic_env_dir: {}".format(alembic_env_dir))
    ensure_migration_is_latest(alembic_env_dir, database_url)
    engine = create_engine(database_url, echo=DATABASE_ENGINE['echo'])
    Session = sessionmaker(bind=engine)
    session = Session()
    # Base.metadata.create_all(engine)  # replaced by Alembic system

    # Go
    # do_something(session)

    MainWindow(session)  # also sets up Twisted with tkinter

# *** not working: a modal dialog (using grab_set) blocks the Twisted TCP/IP stuff
