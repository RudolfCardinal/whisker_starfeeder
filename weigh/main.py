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
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextCursor,
    QTextEdit,
    QWidget,
    QVBoxLayout,
)

from weigh.constants import GUI_MASS_FORMAT, GUI_TIME_FORMAT
from weigh.db import (
    database_is_sqlite,
    ensure_migration_is_latest,
    session_thread_scope,
)
from weigh.debug_qt import enableSignalDebuggingSimply
from weigh.balance import BalanceOwner
from weigh.gui import (
    ALIGNMENT,
    CalibrateBalancesWindow,
    MasterConfigWindow,
    StyledQGroupBox,
)
from weigh.models import MasterConfig, BalanceConfig
from weigh.qt import exit_on_exception
from weigh.rfid import RfidOwner
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
        self.calibrate_balances_button = QPushButton(
            '&Tare/calibrate balances')
        self.calibrate_balances_button.clicked.connect(self.calibrate_balances)
        config_layout.addWidget(self.configure_button)
        config_layout.addWidget(self.calibrate_balances_button)
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

        test_group = StyledQGroupBox("Testing and information")
        test_layout = QHBoxLayout()
        self.reset_rfids_button = QPushButton('Reset RFIDs')
        self.reset_rfids_button.clicked.connect(self.reset_rfid_devices)
        self.ping_balances_button = QPushButton('Ping &balances')
        self.ping_balances_button.clicked.connect(self.ping_balances)
        self.ping_whisker_button = QPushButton('&Ping Whisker')
        self.ping_whisker_button.clicked.connect(self.ping_whisker)
        report_status_button = QPushButton('&Report status')
        report_status_button.clicked.connect(self.report_status)
        report_status_button = QPushButton('&About')
        report_status_button.clicked.connect(self.about)
        test_layout.addWidget(self.reset_rfids_button)
        test_layout.addWidget(self.ping_balances_button)
        test_layout.addWidget(self.ping_whisker_button)
        test_layout.addWidget(report_status_button)
        test_layout.addStretch(1)
        test_group.setLayout(test_layout)

        self.status_group = StyledQGroupBox("Status")
        self.status_grid = None
        self.lay_out_status()

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
        main_layout.addWidget(self.status_group)
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
        readonly = self.anything_running()
        with session_thread_scope(readonly) as session:
            config = MasterConfig.get_singleton(session)
            dialog = MasterConfigWindow(session, config, parent=self,
                                        readonly=readonly)
            dialog.edit_in_nested_transaction()
            session.commit()

    # -------------------------------------------------------------------------
    # Starting, stopping, thread management
    # -------------------------------------------------------------------------

    @Slot()
    def start(self):
        if self.anything_running():
            QMessageBox.about(self, "Can't start",
                              "Can't start: already running.")
            return

        with session_thread_scope() as session:
            config = MasterConfig.get_singleton(session)
            # Continue to hold the session beyond this.
            # http://stackoverflow.com/questions/13904735/sqlalchemy-how-to-use-an-instance-in-sqlalchemy-after-session-close  # noqa

            # -----------------------------------------------------------------
            # Whisker
            # -----------------------------------------------------------------
            self.whisker_task = WeightWhiskerTask()
            self.whisker_owner = WhiskerOwner(
                self.whisker_task, config.server, parent=self)
            self.whisker_owner.finished.connect(self.something_finished)
            self.whisker_owner.status_sent.connect(self.on_status)
            self.whisker_owner.error_sent.connect(self.on_status)
            # It's OK to connect signals before or after moving them to a
            # different thread: http://stackoverflow.com/questions/20752154
            # We don't want time-critical signals going via the GUI thread,
            # because that might be busy with user input.
            # So we'll use the self.whisker_task as the recipient; see below.

            # -----------------------------------------------------------------
            # RFIDs
            # -----------------------------------------------------------------
            self.rfid_list = []
            self.rfid_id_to_obj = {}
            self.rfid_id_to_idx = {}
            for i, rfid_config in enumerate(config.rfidreader_configs):
                if not rfid_config.enabled:
                    continue
                rfid = RfidOwner(rfid_config, parent=self)
                rfid.status_sent.connect(self.on_status)
                rfid.error_sent.connect(self.on_status)
                rfid.finished.connect(self.something_finished)
                rfid.rfid_received.connect(self.whisker_task.on_rfid)
                rfid.rfid_received.connect(self.on_rfid)
                self.rfid_list.append(rfid)
                self.rfid_id_to_obj[rfid.reader_id] = rfid
                self.rfid_id_to_idx[rfid.reader_id] = i

            # -----------------------------------------------------------------
            # Balances
            # -----------------------------------------------------------------
            self.balance_list = []
            self.balance_id_to_obj = {}
            self.balance_id_to_idx = {}
            for i, balance_config in enumerate(config.balance_configs):
                if not balance_config.enabled:
                    continue
                if not balance_config.reader:
                    continue
                if not balance_config.reader.enabled:
                    continue
                balance = BalanceOwner(
                    balance_config,
                    rfid_effective_time_s=config.rfid_effective_time_s,
                    parent=self)
                balance.status_sent.connect(self.on_status)
                balance.error_sent.connect(self.on_status)
                balance.finished.connect(self.something_finished)
                balance.mass_received.connect(self.whisker_task.on_mass)
                balance.mass_received.connect(self.on_mass)
                balance.calibrated.connect(self.on_calibrated)
                self.balance_list.append(balance)
                self.balance_id_to_obj[balance.balance_id] = balance
                self.balance_id_to_idx[balance.balance_id] = i
                rfid = self.rfid_id_to_obj[balance_config.reader_id]
                rfid.rfid_received.connect(balance.on_rfid)

        # ---------------------------------------------------------------------
        # Display
        # ---------------------------------------------------------------------
        self.lay_out_status()

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
    def ping_balances(self):
        for balance in self.balance_list:
            balance.ping()

    @Slot()
    def calibrate_balances(self):
        dialog = CalibrateBalancesWindow(balance_owners=self.balance_list,
                                         parent=self)
        dialog.exec_()

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

    @Slot()
    def about(self):
        QMessageBox.about(self, "Starfeeder", """
<b>Starfeeder</b><br>
<br>
Whisker bird monitor.<br>
By Rudolf Cardinal (rudolf@pobox.com).<br>
Functions:
<ul>
  <li>
    Talks to
    <ul>
      <li>multiple radiofrequency identification (RFID) readers</li>
      <li>multiple weighing balances</li>
      <li>one Whisker server (<a
        href="http://www.whiskercontrol.com/">www.whiskercontrol.com</a>)</li>
    </ul>
  </li>
  <li>Detects the mass of subjects identified by their RFID (having configured
    RFID readers/balances into pairs)</li>
  <li>Tells the Whisker server, and its other clients, about RFID and mass
    events.</li>
  <li>Stores its data to a database (e.g. SQLite; MySQL).</li>
</ul>
External libraries used include Qt (via PySide); SQLAlchemy; Alembic;
bitstring; PyInstaller.<br>
""")

    # -------------------------------------------------------------------------
    # Calibration
    # -------------------------------------------------------------------------

    def on_calibrated(self, calibration_report):
        msg = str(calibration_report)
        self.status(msg)
        logger.info(msg)
        with session_thread_scope() as session:
            balance_config = session.query(BalanceConfig).get(
                calibration_report.balance_id)
            logger.debug("WAS: {}".format(repr(balance_config)))
            balance_config.zero_value = calibration_report.zero_value
            balance_config.refload_value = calibration_report.refload_value
            logger.debug("NOW: {}".format(repr(balance_config)))
            session.commit()

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

    def lay_out_status(self, config=None):
        # Since we want to remove and add items, the simplest thing isn't to
        # own the grid layout and remove/add widgets, but to own the Group
        # within which the layout sits, and assign a new layout (presumably
        # garbage-collecting the old ones).
        # Actually, we have to pass ownership of the old layout to a dummy
        # widget owner that's then destroyed;
        # http://stackoverflow.com/questions/10416582/replacing-layout-on-a-qwidget-with-another-layout  # noqa
        if self.status_grid:
            QWidget().setLayout(self.status_grid)
        # Now we should be able to redo it:
        self.status_grid = QGridLayout()
        self.status_group.setLayout(self.status_grid)
        # Header row
        self.status_grid.addWidget(QLabel("RFID reader"), 0, 0, ALIGNMENT)
        self.status_grid.addWidget(QLabel("Last RFID seen"), 0, 1, ALIGNMENT)
        self.status_grid.addWidget(QLabel("At"), 0, 2, ALIGNMENT)
        self.status_grid.addWidget(QLabel("Balance"), 0, 3, ALIGNMENT)
        self.status_grid.addWidget(QLabel("Raw mass (kg)"), 0, 4, ALIGNMENT)
        self.status_grid.addWidget(QLabel("At"), 0, 5, ALIGNMENT)
        self.status_grid.addWidget(QLabel("Stable mass (kg)"), 0, 6, ALIGNMENT)
        self.status_grid.addWidget(QLabel("At"), 0, 7, ALIGNMENT)
        self.status_grid.addWidget(QLabel("Identified mass (kg)"),
                                   0, 8, ALIGNMENT)
        self.status_grid.addWidget(QLabel("RFID"), 0, 9, ALIGNMENT)
        self.status_grid.addWidget(QLabel("At"), 0, 10, ALIGNMENT)

        self.rfid_labels_rfid = []
        self.rfid_labels_at = []
        row = 1
        for rfid in self.rfid_list:
            self.status_grid.addWidget(
                QLabel("{}: {}".format(rfid.reader_id, rfid.name)),
                row, 0, ALIGNMENT)

            rfid_label_rfid = QLabel("-")
            self.status_grid.addWidget(rfid_label_rfid, row, 1, ALIGNMENT)
            self.rfid_labels_rfid.append(rfid_label_rfid)

            rfid_label_at = QLabel("-")
            self.status_grid.addWidget(rfid_label_at, row, 2, ALIGNMENT)
            self.rfid_labels_at.append(rfid_label_at)

            row += 1

        self.balance_labels_raw_mass = []
        self.balance_labels_raw_mass_at = []
        self.balance_labels_stable_mass = []
        self.balance_labels_stable_mass_at = []
        self.balance_labels_idmass = []
        self.balance_labels_rfid = []
        self.balance_labels_idmass_at = []
        row = 1
        for balance in self.balance_list:
            self.status_grid.addWidget(
                QLabel("{}: {}".format(balance.balance_id, balance.name)),
                row, 3, ALIGNMENT)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 4, ALIGNMENT)
            self.balance_labels_raw_mass.append(label)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 5, ALIGNMENT)
            self.balance_labels_raw_mass_at.append(label)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 6, ALIGNMENT)
            self.balance_labels_stable_mass.append(label)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 7, ALIGNMENT)
            self.balance_labels_stable_mass_at.append(label)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 8, ALIGNMENT)
            self.balance_labels_idmass.append(label)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 9, ALIGNMENT)
            self.balance_labels_rfid.append(label)

            label = QLabel("-")
            self.status_grid.addWidget(label, row, 10, ALIGNMENT)
            self.balance_labels_idmass_at.append(label)

            row += 1

    @exit_on_exception
    def on_rfid(self, rfid_event):
        rfid_index = self.rfid_id_to_idx[rfid_event.reader_id]
        self.rfid_labels_rfid[rfid_index].setText(str(rfid_event.rfid))
        self.rfid_labels_at[rfid_index].setText(
            rfid_event.timestamp.strftime(GUI_TIME_FORMAT))

    @exit_on_exception
    def on_mass(self, mass_event):
        rfid_index = self.rfid_id_to_idx[mass_event.reader_id]
        # For all mass events:
        self.balance_labels_raw_mass[rfid_index].setText(
            GUI_MASS_FORMAT % mass_event.mass_kg)
        self.balance_labels_raw_mass_at[rfid_index].setText(
            mass_event.timestamp.strftime(GUI_TIME_FORMAT))
        # For stable mass events:
        if mass_event.stable:
            self.balance_labels_stable_mass[rfid_index].setText(
                GUI_MASS_FORMAT % mass_event.mass_kg)
            self.balance_labels_stable_mass_at[rfid_index].setText(
                mass_event.timestamp.strftime(GUI_TIME_FORMAT))
        # For identified mass events:
        if mass_event.rfid is not None:
            self.balance_labels_idmass[rfid_index].setText(
                GUI_MASS_FORMAT % mass_event.mass_kg)
            self.balance_labels_rfid[rfid_index].setText(str(mass_event.rfid))
            self.balance_labels_idmass_at[rfid_index].setText(
                mass_event.timestamp.strftime(GUI_TIME_FORMAT))

    def set_button_states(self):
        running = self.anything_running()
        sqlite = database_is_sqlite()
        self.configure_button.setText(
            'View configuration' if running and not sqlite else '&Configure')
        self.configure_button.setEnabled(not running or not sqlite)
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.reset_rfids_button.setEnabled(running)
        self.ping_balances_button.setEnabled(running)
        self.calibrate_balances_button.setEnabled(running)
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
    if getattr(sys, 'frozen', False):
        logger.debug("Running inside a PyInstaller bundle")

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
