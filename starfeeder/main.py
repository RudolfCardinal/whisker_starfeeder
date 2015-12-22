#!/usr/bin/env python
# starfeeder/main.py

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

"""

REFERENCES cited in code:
[1] E-mail to Rudolf Cardinal from Søren Ellegaard, 9 Dec 2014.
[2] E-mail to Rudolf Cardinal from Søren Ellegaard, 10 Dec 2014.
[3] "RFID Reader.docx" in [1]; main reference for the RFID tag reader.
[4] "ba_ad105_e_2.pdf" in [1]; main reference for the balance.
[5] "RFID and LOAD CELL DEVICES - SE_20141209.pptx" in [1].
[6] E-mail to Rudolf Cardinal from Matthew Weinie, 8 Dec 2015.

"""

import argparse
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import sys

import PySide
from PySide.QtGui import QApplication

from starfeeder.constants import DB_URL_ENV_VAR, LOG_FORMAT, LOG_DATEFMT
from starfeeder.db import (
    ensure_migration_is_latest,
    get_database_url,
    upgrade_database,
)
from starfeeder.debug_qt import enable_signal_debugging_simply
from starfeeder.gui import BaseWindow
from starfeeder.version import VERSION


# =============================================================================
# Qt signal debugging
# =============================================================================

DEBUG_SIGNALS = False

if DEBUG_SIGNALS:
    enable_signal_debugging_simply()


# =============================================================================
# Main
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="Starfeeder v{}. Whisker bird monitor, reading from RFID "
        "tag readers and weighing balances.".format(VERSION))
    # ... allow_abbrev=False requires Python 3.5
    parser.add_argument("--logfile", default=None,
                        help="Filename to append log to")
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument('--upgrade-database', action="store_true",
                        help="Upgrade database (determined from SQLAlchemy"
                        " URL, read from {} environment variable) to current"
                        " version".format(DB_URL_ENV_VAR))

    # We could allow extra Qt arguments:
    # args, unparsed_args = parser.parse_known_args()
    # Or not:
    args = parser.parse_args()
    unparsed_args = []

    qt_args = sys.argv[:1] + unparsed_args

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=loglevel)
    if args.logfile:
        fh = logging.FileHandler(args.logfile)
        # default file mode is 'a' for append
        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
        fh.setFormatter(formatter)
        # Send everything to this handler:
        for name, obj in logging.Logger.manager.loggerDict.iteritems():
            obj.addHandler(fh)

    # -------------------------------------------------------------------------
    # Info
    # -------------------------------------------------------------------------
    logger.info(
        "Starfeeder v{}: RFID/balance controller for Whisker, "
        "by Rudolf Cardinal (rudolf@pobox.com)".format(VERSION))
    logger.debug("args: {}".format(args))
    logger.debug("qt_args: {}".format(qt_args))
    logger.debug("PySide version: {}".format(PySide.__version__))
    logger.debug("QtCore version: {}".format(PySide.QtCore.qVersion()))
    if getattr(sys, 'frozen', False):
        logger.debug("Running inside a PyInstaller bundle")

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url = get_database_url()
    logger.debug("Using database URL: {}".format(database_url))
    if args.upgrade_database:
        sys.exit(upgrade_database())
    ensure_migration_is_latest()

    # -------------------------------------------------------------------------
    # Messing around
    # -------------------------------------------------------------------------
    # w = Weight(rfid="my_rfid", weight_mg=123456)
    # session.add(w)
    # print(w)
    # session.commit()
    # print(w)

    # -------------------------------------------------------------------------
    # Action
    # -------------------------------------------------------------------------
    qt_app = QApplication(qt_args)
    win = BaseWindow()
    win.show()
    sys.exit(qt_app.exec_())


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
