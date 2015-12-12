#!/usr/bin/env python3
# weigh/main.py

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
from PySide.QtCore import Slot
from PySide.QtGui import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextCursor,
    QTextEdit,
    QWidget,
    QVBoxLayout,
)

from weigh.db import ensure_migration_is_latest, get_database_session
from weigh.debug_qt import enableSignalDebuggingSimply
from weigh.balance import BalanceController
from weigh.gui import MasterConfigWindow, StyledQGroupBox
from weigh.models import MasterConfig
from weigh.rfid import RfidController
from weigh.task import WeightWhiskerTask
from weigh.whisker_qt import WhiskerOwner


# =============================================================================
# Qt signal debugging
# =============================================================================

DEBUG_SIGNALS = False

if DEBUG_SIGNALS:
    enableSignalDebuggingSimply()


# =============================================================================
# Main GUI window
# =============================================================================

class BaseWindow(QMainWindow):
    # Don't inherit from QDialog, which has an additional Escape-to-close
    # function that's harder to trap. Use QWidget or QMainWindow.
    NAME = "main"

    def __init__(self):
        super().__init__()
        self.exit_pending = False

        # ---------------------------------------------------------------------
        # Internals
        # ---------------------------------------------------------------------
        self.session = get_database_session()
        self.config = MasterConfig.get_singleton(self.session)
        self.rfid_list = []
        self.balance_list = []
        self.whisker_task = None
        self.whisker_owner = None

        # ---------------------------------------------------------------------
        # GUI
        # ---------------------------------------------------------------------
        self.setWindowTitle('Starfeeder: RFID/balance controller for Whisker')
        self.setMinimumWidth(400)

        config_group = StyledQGroupBox("Configure")
        config_layout = QHBoxLayout()
        self.configure_button = QPushButton('&Configure')
        self.configure_button.clicked.connect(self.configure)
        config_layout.addWidget(self.configure_button)
        config_layout.addStretch(1)
        config_group.setLayout(config_layout)

        run_group = StyledQGroupBox("Run")
        run_layout = QHBoxLayout()
        self.start_button = QPushButton('St&art/reset everything')
        self.start_button.clicked.connect(self.start)
        self.stop_button = QPushButton('Sto&p everything')
        self.stop_button.clicked.connect(self.stop)
        run_layout.addWidget(self.start_button)
        run_layout.addWidget(self.stop_button)
        run_layout.addStretch(1)
        run_group.setLayout(run_layout)

        test_group = StyledQGroupBox("Test")
        test_layout = QHBoxLayout()
        self.reset_rfids_button = QPushButton('Reset RFIDs')
        self.reset_rfids_button.clicked.connect(self.reset_rfid_devices)
        self.ping_balance_button = QPushButton('Ping &balances')
        self.ping_balance_button.clicked.connect(self.ping_balance)
        self.ping_whisker_button = QPushButton('&Ping Whisker')
        self.ping_whisker_button.clicked.connect(self.ping_whisker)
        report_status_button = QPushButton('&Report status')
        report_status_button.clicked.connect(self.report_status)
        test_layout.addWidget(self.reset_rfids_button)
        test_layout.addWidget(self.ping_balance_button)
        test_layout.addWidget(self.ping_whisker_button)
        test_layout.addWidget(report_status_button)
        test_layout.addStretch(1)
        test_group.setLayout(test_layout)

        # For nested layouts: (1) create everything, (2) lay out
        log_group = StyledQGroupBox("Log")
        log_layout_1 = QVBoxLayout()
        log_layout_2 = QHBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QTextEdit.NoWrap)
        font = self.log.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        log_clear_button = QPushButton('Clear log')
        log_clear_button.clicked.connect(self.log.clear)
        log_copy_button = QPushButton('Copy to clipboard')
        log_copy_button.clicked.connect(self.copy_whole_log)
        log_layout_2.addWidget(log_clear_button)
        log_layout_2.addWidget(log_copy_button)
        log_layout_2.addStretch(1)
        log_layout_1.addWidget(self.log)
        log_layout_1.addLayout(log_layout_2)
        log_group.setLayout(log_layout_1)

        # You can't use the layout as the parent of the widget.
        # But you don't need to specify a parent when you use addWidget; it
        # works that out for you.
        # http://doc.qt.io/qt-4.8/layout.html#tips-for-using-layouts
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(config_group)
        main_layout.addWidget(run_group)
        main_layout.addWidget(test_group)
        main_layout.addWidget(log_group)

        self.set_button_states()

    # -------------------------------------------------------------------------
    # Exiting
    # -------------------------------------------------------------------------

    def closeEvent(self, event):
        """Trap exit."""
        quit_msg = "Are you sure you want to exit?"
        reply = QMessageBox.question(self, 'Really exit?',  quit_msg,
                                     QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            event.ignore()
            return
        # If subthreads aren't shut down, we get a segfault when we quit.
        # However, right now, signals aren't being processed because we're in
        # the GUI message loop. So we need to defer the call if subthreads are
        # running
        if not self.anything_running():
            event.accept()
            return
        # Now stop everything
        logger.warn("Waiting for threads to finish...")
        self.exit_pending = True
        for rfid in self.rfid_list:
            rfid.stop()
        for balance in self.balance_list:
            balance.stop()
        if self.whisker_owner:
            self.whisker_owner.stop()
        # Will get one or more callbacks to something_finished
        event.ignore()

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    @Slot()
    def configure(self):
        dialog = MasterConfigWindow(self.session, self.config, parent=self,
                                    readonly=self.anything_running())
        dialog.edit_in_nested_transaction()
        self.session.commit()

    # -------------------------------------------------------------------------
    # Starting, stopping, thread management
    # -------------------------------------------------------------------------

    @Slot()
    def start(self):
        if self.anything_running():
            QMessageBox.about(self, "Can't start",
                              "Can't start: already running.")
            return

        # ---------------------------------------------------------------------
        # Whisker
        # ---------------------------------------------------------------------
        self.whisker_task = WeightWhiskerTask()
        self.whisker_owner = WhiskerOwner(
            self.whisker_task, self.config.server, parent=self)
        self.whisker_owner.finished.connect(self.something_finished)
        self.whisker_owner.status_sent.connect(self.on_status)
        self.whisker_owner.error_sent.connect(self.on_status)
        # It's OK to connect signals before or after moving them to a different
        # thread: http://stackoverflow.com/questions/20752154
        # We don't want time-critical signals going via the GUI thread, because
        # that might be busy with user input.
        # So we'll use the self.whisker_task as the recipient; see below.

        # ---------------------------------------------------------------------
        # RFIDs
        # ---------------------------------------------------------------------
        self.rfid_list = []
        for rfid_config in self.config.rfid_configs:
            if not rfid_config.enabled:
                continue
            rfid = RfidController(rfid_config, parent=self)
            rfid.status_sent.connect(self.on_status)
            rfid.error_sent.connect(self.on_status)
            rfid.finished.connect(self.something_finished)
            rfid.rfid_received.connect(self.whisker_task.on_rfid)
            self.rfid_list.append(rfid)

        # ---------------------------------------------------------------------
        # Balances
        # ---------------------------------------------------------------------
        self.balance_list = []
        for balance_config in self.config.balance_configs:
            if not balance_config.enabled:
                continue
            if not balance_config.reader:
                continue
            if not balance_config.reader.enabled:
                continue
            balance = BalanceController(balance_config, parent=self)
            balance.status_sent.connect(self.on_status)
            balance.error_sent.connect(self.on_status)
            balance.finished.connect(self.something_finished)
            balance.mass_received.connect(self.whisker_task.on_mass)
            self.balance_list.append(balance)

        # ---------------------------------------------------------------------
        # Start
        # ---------------------------------------------------------------------
        for rfid in self.rfid_list:
            rfid.start()
        for balance in self.balance_list:
            balance.start()
        if self.whisker_owner:
            self.whisker_owner.start()
        self.set_button_states()

    @Slot()
    def stop(self):
        if not self.anything_running():
            QMessageBox.about(self, "Can't stop",
                              "Nothing to stop: not running.")
            return
        self.status("Stopping everything...")
        for rfid in self.rfid_list:
            rfid.stop()
        for balance in self.balance_list:
            balance.stop()
        if self.whisker_owner:
            self.whisker_owner.stop()
        self.set_button_states()

    @Slot()
    def something_finished(self):
        if self.anything_running():
            logger.debug("... thread finished, but others are still running")
            return
        self.status("All tasks and threads stopped")
        if self.exit_pending:
            QApplication.quit()
        self.set_button_states()

    def anything_running(self):
        """Returns a bool."""
        return (
            any(r.is_running() for r in self.rfid_list)
            or any(b.is_running() for b in self.balance_list)
            or (self.whisker_owner is not None
                and self.whisker_owner.is_running())
        )

    # -------------------------------------------------------------------------
    # Testing
    # -------------------------------------------------------------------------

    @Slot()
    def reset_rfid_devices(self):
        for rfid in self.rfid_list:
            rfid.reset()

    @Slot()
    def ping_balance(self):
        for balance in self.balance_list:
            balance.ping()

    @Slot()
    def ping_whisker(self):
        if self.whisker_owner:
            self.whisker_owner.ping()

    @Slot()
    def report_status(self):
        self.status("Requesting status from RFID devices")
        for rfid in self.rfid_list:
            rfid.report_status()
        self.status("Requesting status from balances")
        for balance in self.balance_list:
            balance.report_status()
        if self.whisker_owner:
            self.status("Requesting status from Whisker controller")
            self.whisker_owner.report_status()
            # self.whisker_task.report_status()
        self.status("Status report complete.")

    # -------------------------------------------------------------------------
    # Status log
    # -------------------------------------------------------------------------

    @Slot(str, str)
    def on_status(self, msg, source=""):
        # http://stackoverflow.com/questions/16568451
        if source:
            msg = "[{}] {}".format(source, msg)
        if self.log.toPlainText():
            msg = "\n" + msg
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(msg)
        self.scroll_to_end_of_log()

    def status(self, msg):
        self.on_status(msg, self.NAME)

    def copy_whole_log(self):
        # Ctrl-C will copy the selected parts.
        # log.copy() will copy the selected parts.
        self.log.selectAll()
        self.log.copy()
        self.log.moveCursor(QTextCursor.End)
        self.scroll_to_end_of_log()

    def scroll_to_end_of_log(self):
        vsb = self.log.verticalScrollBar()
        vsb.setValue(vsb.maximum())
        hsb = self.log.horizontalScrollBar()
        hsb.setValue(0)

    # -------------------------------------------------------------------------
    # More GUI
    # -------------------------------------------------------------------------

    def set_button_states(self):
        running = self.anything_running()
        # self.configure_button.setEnabled(not running)
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.reset_rfids_button.setEnabled(running)
        self.ping_balance_button.setEnabled(running)
        self.ping_whisker_button.setEnabled(running)


# =============================================================================
# Main
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="Whisker bird monitor, reading from RFID tag reader and "
        "weighing balance.")
    parser.add_argument(
        "--logfile", default=None,
        help="Filename to append log to")
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")

    args, unparsed_args = parser.parse_known_args()
    qt_args = sys.argv[:1] + unparsed_args

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
    LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
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
    logger.info("Starfeeder: RFID/balance controller for Whisker")
    logger.info("- by Rudolf Cardinal (rudolf@pobox.com)")
    logger.debug("args: {}".format(args))
    logger.debug("unparsed_args: {}".format(unparsed_args))
    logger.info("PySide version: {}".format(PySide.__version__))
    logger.info("QtCore version: {}".format(PySide.QtCore.qVersion()))

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
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
