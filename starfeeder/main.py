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
import sys
import traceback

import PySide
from PySide.QtGui import QApplication
from whisker.debug_qt import enable_signal_debugging_simply
from whisker.logging import (
    configure_logger_for_colour,
    copy_root_log_to_file,
)
from whisker.sqlalchemy import (
    get_current_and_head_revision,
    upgrade_database,
)
from whisker.qt import (
    LogWindow,
    run_gui,
)
import whisker.version

from starfeeder.constants import (
    ALEMBIC_BASE_DIR,
    ALEMBIC_CONFIG_FILENAME,
    DATABASE_ENV_VAR_NOT_SPECIFIED,
    DB_URL_ENV_VAR,
    LOG_FORMAT,
    LOG_DATEFMT,
    WINDOW_TITLE,
    WRONG_DATABASE_VERSION_STUB,
)
from starfeeder.gui import (
    BaseWindow,
    NoDatabaseSpecifiedWindow,
    WrongDatabaseVersionWindow,
)
from starfeeder.settings import (
    get_database_url,
    set_database_url,
    set_database_echo,
)
from starfeeder.version import VERSION

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


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
    parser.add_argument('--guilog', action="store_true",
                        help="Show Python log in a GUI window")
    parser.add_argument('--upgrade-database', action="store_true",
                        help="Upgrade database (determined from SQLAlchemy"
                        " URL, read from {} environment variable) to current"
                        " version".format(DB_URL_ENV_VAR))
    parser.add_argument('--gui', '-g', action="store_true",
                        help="GUI mode only")
    parser.add_argument(
        "--dburl", default=None,
        help="Database URL (if not specified, task will look in {} "
        "environment variable).".format(DB_URL_ENV_VAR))
    parser.add_argument('--dbecho', action="store_true",
                        help="Echo SQL to log.")
    parser.add_argument('--debug-qt-signals', action="store_true",
                        help="Debug QT signals.")

    # We could allow extra Qt arguments:
    # args, unparsed_args = parser.parse_known_args()
    # Or not:
    args = parser.parse_args()
    unparsed_args = []

    qt_args = sys.argv[:1] + unparsed_args

    # -------------------------------------------------------------------------
    # Modify settings if we're in a PyInstaller bundle
    # -------------------------------------------------------------------------
    in_bundle = getattr(sys, 'frozen', False)
    if in_bundle:
        args.gui = True
    if not args.gui:
        args.guilog = False

    # -------------------------------------------------------------------------
    # Create QApplication before we create any windows (or Qt will crash)
    # -------------------------------------------------------------------------
    qt_app = QApplication(qt_args)

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=loglevel)
    rootlogger = logging.getLogger()
    rootlogger.setLevel(loglevel)
    configure_logger_for_colour(rootlogger)  # configure root logger
    logging.getLogger('whisker').setLevel(logging.DEBUG if args.verbose >= 2
                                          else logging.INFO)
    if args.logfile:
        copy_root_log_to_file(args.logfile)
    if args.guilog:
        log_window = LogWindow(level=loglevel,
                               window_title=WINDOW_TITLE + " Python log",
                               logger=rootlogger)
        log_window.show()

    # If any exceptions happen up to this point, we're a bit stuffed.
    # But from now on, we can trap anything and see it in the GUI log, if
    # enabled, even if we have no console.

    # noinspection PyBroadException
    try:

        # ---------------------------------------------------------------------
        # Info
        # ---------------------------------------------------------------------
        log.info("Starfeeder v{}: RFID/balance controller for Whisker, "
                 "by Rudolf Cardinal (rudolf@pobox.com)".format(VERSION))
        log.debug("args: {}".format(args))
        log.debug("qt_args: {}".format(qt_args))
        log.debug("PySide version: {}".format(PySide.__version__))
        log.debug("QtCore version: {}".format(PySide.QtCore.qVersion()))
        log.debug("Whisker client version: {}".format(whisker.version.VERSION))
        if in_bundle:
            log.debug("Running inside a PyInstaller bundle")
        if args.gui:
            log.debug("Running in GUI-only mode")
        if args.debug_qt_signals:
            enable_signal_debugging_simply()

        # ---------------------------------------------------------------------
        # Database
        # ---------------------------------------------------------------------
        # Get URL, or complain
        if args.dburl:
            set_database_url(args.dburl)
        if args.dbecho:
            set_database_echo(args.dbecho)
        try:
            database_url = get_database_url()
        except ValueError:
            if args.gui:
                win = NoDatabaseSpecifiedWindow()
                if args.guilog:
                    # noinspection PyUnboundLocalVariable
                    win.exit_kill_log.connect(log_window.exit)
                return run_gui(qt_app, win)
            raise ValueError(DATABASE_ENV_VAR_NOT_SPECIFIED)
        log.debug("Using database URL: {}".format(database_url))

        # Has the user requested a command-line database upgrade?
        if args.upgrade_database:
            sys.exit(upgrade_database(ALEMBIC_CONFIG_FILENAME,
                                      ALEMBIC_BASE_DIR))
        # Is the database at the correct version?
        (current_revision, head_revision) = get_current_and_head_revision(
            database_url,
            ALEMBIC_CONFIG_FILENAME,
            ALEMBIC_BASE_DIR
        )
        if current_revision != head_revision:
            if args.gui:
                win = WrongDatabaseVersionWindow(current_revision,
                                                 head_revision)
                if args.guilog:
                    # noinspection PyUnboundLocalVariable
                    win.exit_kill_log.connect(log_window.exit)
                return run_gui(qt_app, win)
            raise ValueError(WRONG_DATABASE_VERSION_STUB.format(
                head_revision=head_revision,
                current_revision=current_revision))

        # ---------------------------------------------------------------------
        # Run app
        # ---------------------------------------------------------------------
        win = BaseWindow()
        if args.guilog:
            # noinspection PyUnboundLocalVariable
            win.exit_kill_log.connect(log_window.exit)
        return run_gui(qt_app, win)

    except:
        if args.guilog:
            log.critical(traceback.format_exc())
            log_window.set_may_close(True)
            return qt_app.exec_()
        else:
            raise


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    # noinspection PyBroadException
    try:
        sys.exit(main())
    except Exception as e:
        log.critical("Exception caught at top level")
        traceback.print_exc()
        sys.exit(1)
