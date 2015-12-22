#!/usr/bin/env python
# starfeeder/gui.py

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

import collections
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import platform

from PySide.QtCore import Qt, Slot
from PySide.QtGui import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextCursor,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import serial
from serial.tools.list_ports import comports

from starfeeder.balance import BalanceOwner
from starfeeder.constants import (
    ABOUT,
    BALANCE_ASF_MINIMUM,
    BALANCE_ASF_MAXIMUM,
    GUI_MASS_FORMAT,
    GUI_TIME_FORMAT,
)
from starfeeder.db import (
    database_is_sqlite,
    session_thread_scope,
)
from starfeeder.lang import natural_keys
from starfeeder.models import BalanceConfig, MasterConfig, RfidReaderConfig
from starfeeder.qt import (
    GenericListModel,
    ModalEditListView,
    RadioGroup,
    TransactionalEditDialogMixin,
    ValidationError,
)
from starfeeder.rfid import RfidOwner
from starfeeder.qt import exit_on_exception
from starfeeder.task import WeightWhiskerTask
from starfeeder.whisker_qt import WhiskerOwner


# =============================================================================
# Constants
# =============================================================================

AVAILABLE_SERIAL_PORTS = sorted([item[0] for item in comports()],
                                key=natural_keys)
# comports() returns a list/tuple of tuples: (port, desc, hwid)

# POSSIBLE_RATES_HZ = [100, 50, 25, 10, 6, 3, 2, 1]
POSSIBLE_RATES_HZ = [10, 6, 3, 2, 1]
# ... 100 Hz (a) ends up with a bunch of messages concatenated from the serial
# device, so timing becomes pointless, (b) is pointless, and (c) leads rapidly
# to a segmentation fault.
# Note that 9600 bps at 8E1 = 960 cps.
# So divide that by the length of the message (including CR+LF) to get the
# absolute maximum rate. And don't go near that.

POSSIBLE_ASF_MODES = list(range(BALANCE_ASF_MINIMUM, BALANCE_ASF_MAXIMUM + 1))

ALIGNMENT = Qt.AlignLeft | Qt.AlignTop
DEVICE_ID_LABEL = "Device ID (set when first saved)"
KEEP_LABEL = "Device has associated data and<br>cannot be deleted"
RENAME_WARNING = (
    "<b>Once created and used for real data, AVOID RENAMING devices;<br>"
    "RFID/mass data will refer to these entries by number (not name).</b>"
)

# =============================================================================
# Styled elements
# =============================================================================

GROUPBOX_STYLESHEET = """
QGroupBox {
    border: 1px solid gray;
    border-radius: 2px;
    margin-top: 0.5em;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 2px 0 2px;
}
"""
# http://stackoverflow.com/questions/14582591/border-of-qgroupbox
# http://stackoverflow.com/questions/2730331/set-qgroupbox-title-font-size-with-style-sheets  # noqa


class StyledQGroupBox(QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet(GROUPBOX_STYLESHEET)


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
        QMessageBox.about(self, "Starfeeder", ABOUT)

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
        self.status_grid.addWidget(QLabel("Locked/ID'd mass (kg)"),
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
        # For locked mass events:
        if mass_event.stable:
            self.balance_labels_stable_mass[rfid_index].setText(
                GUI_MASS_FORMAT % mass_event.mass_kg)
            self.balance_labels_stable_mass_at[rfid_index].setText(
                mass_event.timestamp.strftime(GUI_TIME_FORMAT))
        # For locked, identified mass events:
        if mass_event.locked:
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
# Extra derived classes
# =============================================================================

class KeeperCheckGenericListModel(GenericListModel):
    def item_deletable(self, rowindex):
        return not self.listdata[rowindex].keep


# =============================================================================
# Edit main config
# =============================================================================

class MasterConfigWindow(QDialog, TransactionalEditDialogMixin):
    """
    Edits a MasterConfig object.
    """
    def __init__(self, session, config, parent=None, readonly=False):
        super().__init__(parent)  # QDialog

        # Title
        self.setWindowTitle("Configure Starfeeder")

        # Elements
        self.rfid_effective_time_edit = QLineEdit()
        self.server_edit = QLineEdit(placeholderText="typically: localhost")
        self.port_edit = QLineEdit(placeholderText="typically: 3233")
        self.wcm_prefix_edit = QLineEdit()
        self.rfid_lv = ModalEditListView(session, RfidConfigDialog,
                                         readonly=readonly)
        self.rfid_lv.selected_maydelete.connect(self.set_rfid_button_states)
        self.balance_lv = ModalEditListView(session, BalanceConfigDialog,
                                            readonly=readonly)
        self.balance_lv.selected_maydelete.connect(
            self.set_balance_button_states)

        # Layout/buttons
        logic_group = StyledQGroupBox('Task logic')
        lform = QFormLayout()
        lform.addRow("RFID effective time (s)<br>This is the time that an RFID"
                     " event ‘persists’ for.", self.rfid_effective_time_edit)
        logic_group.setLayout(lform)

        whisker_group = StyledQGroupBox('Whisker')
        wform = QFormLayout()
        wform.addRow("Whisker server", self.server_edit)
        wform.addRow("Whisker port", self.port_edit)
        wform.addRow("Whisker client message prefix", self.wcm_prefix_edit)
        whisker_group.setLayout(wform)

        rfid_group = StyledQGroupBox('RFID readers')
        rfid_layout_1 = QHBoxLayout()
        rfid_layout_2 = QVBoxLayout()
        if not readonly:
            self.rfid_add_button = QPushButton('Add')
            self.rfid_add_button.clicked.connect(self.add_rfid)
            self.rfid_remove_button = QPushButton('Remove')
            self.rfid_remove_button.clicked.connect(self.remove_rfid)
            rfid_layout_2.addWidget(self.rfid_add_button)
            rfid_layout_2.addWidget(self.rfid_remove_button)
        self.rfid_edit_button = QPushButton('View' if readonly else 'Edit')
        self.rfid_edit_button.clicked.connect(self.edit_rfid)
        # ... or double-click
        rfid_layout_2.addWidget(self.rfid_edit_button)
        rfid_layout_2.addStretch(1)
        rfid_layout_1.addWidget(self.rfid_lv)
        rfid_layout_1.addLayout(rfid_layout_2)
        rfid_group.setLayout(rfid_layout_1)

        balance_group = StyledQGroupBox('Balances')
        balance_layout_1 = QHBoxLayout()
        balance_layout_2 = QVBoxLayout()
        if not readonly:
            self.balance_add_button = QPushButton('Add')
            self.balance_add_button.clicked.connect(self.add_balance)
            self.balance_remove_button = QPushButton('Remove')
            self.balance_remove_button.clicked.connect(self.remove_balance)
            balance_layout_2.addWidget(self.balance_add_button)
            balance_layout_2.addWidget(self.balance_remove_button)
        self.balance_edit_button = QPushButton('View' if readonly else 'Edit')
        self.balance_edit_button.clicked.connect(self.edit_balance)
        balance_layout_2.addWidget(self.balance_edit_button)
        balance_layout_2.addStretch(1)
        balance_layout_1.addWidget(self.balance_lv)
        balance_layout_1.addLayout(balance_layout_2)
        balance_group.setLayout(balance_layout_1)

        main_layout = QVBoxLayout()
        main_layout.addWidget(logic_group)
        main_layout.addWidget(whisker_group)
        main_layout.addWidget(rfid_group)
        main_layout.addWidget(balance_group)

        # Shared code
        TransactionalEditDialogMixin.__init__(self, session, config,
                                              main_layout, readonly=readonly)

        self.set_rfid_button_states(False, False)
        self.set_balance_button_states(False, False)

    def object_to_dialog(self, obj):
        self.rfid_effective_time_edit.setText(str(
            obj.rfid_effective_time_s
            if obj.rfid_effective_time_s is not None else ''))
        self.server_edit.setText(obj.server)
        self.port_edit.setText(str(obj.port or ''))
        self.wcm_prefix_edit.setText(obj.wcm_prefix)
        rfid_lm = KeeperCheckGenericListModel(obj.rfidreader_configs, self)
        self.rfid_lv.setModel(rfid_lm)
        balance_lm = KeeperCheckGenericListModel(obj.balance_configs, self)
        self.balance_lv.setModel(balance_lm)

    def dialog_to_object(self, obj):
        # Master config validation and cross-checks.
        # ---------------------------------------------------------------------
        # Basic checks
        # ---------------------------------------------------------------------
        try:
            obj.rfid_effective_time_s = float(
                self.rfid_effective_time_edit.text())
            assert obj.rfid_effective_time_s > 0
        except:
            raise ValidationError("Invalid RFID effective time")
        try:
            obj.server = self.server_edit.text()
            assert len(obj.server) > 0
        except:
            raise ValidationError("Invalid server name")
        try:
            obj.port = int(self.port_edit.text())
            assert obj.port > 0
        except:
            raise ValidationError("Invalid port number")
        # ---------------------------------------------------------------------
        # Duplicate device ports, or names?
        # ---------------------------------------------------------------------
        name_port_pairs = (
            [(r.name, r.port) for r in obj.rfidreader_configs]
            + [(b.name, b.port) for b in obj.balance_configs]
        )
        names = [x[0] for x in name_port_pairs]
        duplicate_names = [
            item for item, count in collections.Counter(names).items()
            if count > 1
        ]
        if duplicate_names:
            raise ValidationError(
                "Devices have duplicate names!<br>"
                "Names: {}.".format(duplicate_names))
        ports = [x[1] for x in name_port_pairs]
        if platform.system() == 'Windows':
            # Windows is case-insensitive; e.g. com1, COM1
            ports = [x.upper() for x in ports]
        duplicate_ports = [
            item for item, count in collections.Counter(ports).items()
            if count > 1
        ]
        names_of_duplicate_ports = [x[0] for x in name_port_pairs
                                    if x[1] in duplicate_ports]
        if duplicate_ports:
            raise ValidationError(
                "More than one device on a single serial port!<br>"
                "Names: {}.<br>Ports: {}".format(names_of_duplicate_ports,
                                                 duplicate_ports))
        obj.wcm_prefix = self.wcm_prefix_edit.text()
        # ---------------------------------------------------------------------
        # Balances without a paired RFID, or with duplicate pairs?
        # ---------------------------------------------------------------------
        used_reader_names = []
        for balance_config in obj.balance_configs:
            if balance_config.reader is None:
                raise ValidationError(
                    "Balance {} has no paired RFID reader".format(
                        balance_config.name))
            if not balance_config.reader.enabled:
                raise ValidationError(
                    "Balance {} is using RFID reader {},<br>"
                    "but this is disabled".format(
                        balance_config.name,
                        balance_config.reader.name))
            if balance_config.reader.name in used_reader_names:
                raise ValidationError(
                    "More than one balance is trying to use reader {}".format(
                        balance_config.reader.name))
            used_reader_names.append(balance_config.reader.name)

    @Slot()
    def add_rfid(self):
        config = RfidReaderConfig(master_config_id=self.obj.id)
        self.rfid_lv.add_in_nested_transaction(config)

    @Slot()
    def remove_rfid(self):
        self.rfid_lv.remove_selected()

    @Slot()
    def edit_rfid(self):
        self.rfid_lv.edit_selected()

    @Slot()
    def add_balance(self):
        config = BalanceConfig(master_config_id=self.obj.id)
        self.balance_lv.add_in_nested_transaction(config)

    @Slot()
    def remove_balance(self):
        self.balance_lv.remove_selected()

    @Slot()
    def edit_balance(self):
        self.balance_lv.edit_selected()

    @Slot()
    def set_rfid_button_states(self, selected, maydelete):
        if not self.readonly:
            self.rfid_remove_button.setEnabled(maydelete)
        self.rfid_edit_button.setEnabled(selected)

    @Slot()
    def set_balance_button_states(self, selected, maydelete):
        if not self.readonly:
            self.balance_remove_button.setEnabled(maydelete)
        self.balance_edit_button.setEnabled(selected)


# =============================================================================
# Dialog components for serial config
# =============================================================================

class SerialPortMixin(object):
    FLOW_NONE = 0
    FLOW_XONXOFF = 1
    FLOW_RTSCTS = 2
    FLOW_DTRDSR = 3

    def __init__(self, port_options=None, allow_other_port=True,
                 baudrate_options=None, allow_other_baudrate=False,
                 bytesize_options=None, parity_options=None,
                 stopbits_options=None, flow_options=None):
        """
        Always helpful to have allow_other_port=True on Linux, because you can
        create new debugging ports at the drop of a hat, and the serial port
        enumerator may not notice.
        """
        self.sp_port_options = port_options
        self.sp_allow_other_port = allow_other_port
        self.sp_baudrate_options = baudrate_options
        self.sp_allow_other_baudrate = allow_other_baudrate

        bytesize_map = [
            (serial.FIVEBITS, "&5"),
            (serial.SIXBITS, "&6"),
            (serial.SEVENBITS, "&7"),
            (serial.EIGHTBITS, "&8"),
        ]
        if bytesize_options:
            bytesize_map = [x for x in bytesize_map
                            if x[0] in bytesize_options]

        parity_map = [
            (serial.PARITY_NONE, "&None"),
            (serial.PARITY_EVEN, "&Even"),
            (serial.PARITY_ODD, "&Odd"),
            (serial.PARITY_MARK, "Mark (rare)"),
            (serial.PARITY_SPACE, "Space (rare)"),
        ]
        if parity_options:
            parity_map = [x for x in parity_map if x[0] in parity_options]

        stopbits_map = [
            (serial.STOPBITS_ONE, "&1"),
            (serial.STOPBITS_ONE_POINT_FIVE, "1.5 (rare)"),
            (serial.STOPBITS_TWO, "&2"),
        ]
        if stopbits_options:
            stopbits_map = [x for x in stopbits_map
                            if x[0] in stopbits_options]

        flow_map = [
            (self.FLOW_NONE, "None (not advised)"),
            (self.FLOW_XONXOFF, "&XON/XOFF software flow control"),
            (self.FLOW_RTSCTS, "&RTS/CTS hardware flow control"),
            (self.FLOW_DTRDSR, "&DTR/DSR hardware flow control"),
        ]
        if flow_options:
            flow_map = [x for x in flow_map if x[0] in flow_options]

        form = QFormLayout()
        if self.sp_port_options:
            self.sp_port_combo = QComboBox()
            self.sp_port_combo.setEditable(allow_other_port)
            self.sp_port_combo.addItems(port_options)
            sp_port_thing = self.sp_port_combo
        else:
            self.sp_port_edit = QLineEdit()
            sp_port_thing = self.sp_port_edit
        form.addRow("Serial port", sp_port_thing)
        if baudrate_options:
            self.sp_baudrate_combo = QComboBox()
            self.sp_baudrate_combo.setEditable(allow_other_baudrate)
            self.sp_baudrate_combo.addItems([str(x) for x in baudrate_options])
            sp_baudrate_thing = self.sp_baudrate_combo
        else:
            self.sp_baudrate_edit = QLineEdit()
            sp_baudrate_thing = self.sp_baudrate_edit
        form.addRow("Speed in bits per second", sp_baudrate_thing)

        sp_bytesize_group = StyledQGroupBox("Data bits")
        self.sp_bytesize_rg = RadioGroup(bytesize_map,
                                         default=serial.EIGHTBITS)
        sp_bytesize_layout = QHBoxLayout()
        self.sp_bytesize_rg.add_buttons_to_layout(sp_bytesize_layout)
        sp_bytesize_layout.addStretch(1)
        sp_bytesize_group.setLayout(sp_bytesize_layout)

        sp_parity_group = StyledQGroupBox("Parity bit")
        self.sp_parity_rg = RadioGroup(parity_map, default=serial.PARITY_NONE)
        sp_parity_layout = QHBoxLayout()
        self.sp_parity_rg.add_buttons_to_layout(sp_parity_layout)
        sp_parity_layout.addStretch(1)
        sp_parity_group.setLayout(sp_parity_layout)

        sp_stop_group = StyledQGroupBox("Stop bits")
        self.sp_stop_rg = RadioGroup(stopbits_map, default=serial.STOPBITS_ONE)
        sp_stop_layout = QHBoxLayout()
        self.sp_stop_rg.add_buttons_to_layout(sp_stop_layout)
        sp_stop_layout.addStretch(1)
        sp_stop_group.setLayout(sp_stop_layout)

        # It's daft to use >1 method of flow control. So use a single radio.
        sp_flow_group = StyledQGroupBox("Flow control")
        self.sp_flow_rg = RadioGroup(flow_map, default=self.FLOW_RTSCTS)
        sp_flow_layout = QVBoxLayout()
        self.sp_flow_rg.add_buttons_to_layout(sp_flow_layout)
        sp_flow_group.setLayout(sp_flow_layout)

        vlayout = QVBoxLayout()
        vlayout.addLayout(form)
        vlayout.addWidget(sp_bytesize_group)
        vlayout.addWidget(sp_parity_group)
        vlayout.addWidget(sp_stop_group)
        vlayout.addWidget(sp_flow_group)

        self.sp_group = StyledQGroupBox('Serial port settings')
        self.sp_group.setLayout(vlayout)

    def serial_port_group_to_object(self, obj):
        try:
            if self.sp_port_options:
                obj.port = self.sp_port_combo.currentText()
            else:
                obj.port = self.sp_port_edit.text()
            assert len(obj.port) > 0
        except:
            raise ValidationError("Invalid serial port name")
        try:
            if self.sp_baudrate_options:
                obj.baudrate = int(self.sp_baudrate_combo.currentText())
            else:
                obj.baudrate = int(self.sp_baudrate_edit.text())
            assert obj.baudrate > 0
        except:
            raise ValidationError("Invalid speed")
        obj.bytesize = self.sp_bytesize_rg.get_value()
        obj.parity = self.sp_parity_rg.get_value()
        obj.stopbits = self.sp_stop_rg.get_value()
        flow = self.sp_flow_rg.get_value()
        obj.xonxoff = flow == self.FLOW_XONXOFF
        obj.rtscts = flow == self.FLOW_RTSCTS
        obj.dsrdtr = flow == self.FLOW_DTRDSR

    def object_to_serial_port_group(self, obj):
        if self.sp_port_options:
            if obj.port in self.sp_port_options:
                index = self.sp_port_options.index(obj.port)
                self.sp_port_combo.setCurrentIndex(index)
            elif self.sp_allow_other_port:
                self.sp_port_combo.setEditText(obj.port)
            else:
                self.sp_port_combo.setCurrentIndex(0)
        else:
            self.sp_port_edit.setText(obj.port)
        if self.sp_baudrate_options:
            if obj.baudrate in self.sp_baudrate_options:
                index = self.sp_baudrate_options.index(obj.baudrate)
                self.sp_baudrate_combo.setCurrentIndex(index)
            elif self.sp_allow_other_baudrate:
                self.sp_baudrate_combo.setEditText(str(obj.baudrate))
            else:
                self.sp_baudrate_combo.setCurrentIndex(0)
        else:
            self.sp_baudrate_edit.setText(str(obj.baudrate or ''))
        self.sp_bytesize_rg.set_value(obj.bytesize)
        self.sp_parity_rg.set_value(obj.parity)
        self.sp_stop_rg.set_value(obj.stopbits)
        if obj.rtscts:
            flow = self.FLOW_RTSCTS
        elif obj.dsrdtr:
            flow = self.FLOW_DTRDSR
        elif obj.xonxoff:
            flow = self.FLOW_XONXOFF
        else:
            flow = self.FLOW_NONE
        self.sp_flow_rg.set_value(flow)


# =============================================================================
# Edit RFID config
# =============================================================================

class RfidConfigDialog(QDialog, TransactionalEditDialogMixin,
                       SerialPortMixin):

    def __init__(self, session, rfid_config, parent=None, readonly=False):
        super().__init__(parent)  # QDialog
        SerialPortMixin.__init__(
            self,
            port_options=AVAILABLE_SERIAL_PORTS,
            baudrate_options=[9600],
            bytesize_options=[serial.EIGHTBITS],
            parity_options=[serial.PARITY_NONE],
            stopbits_options=[serial.STOPBITS_ONE],
        )  # [3]

        # Title
        self.setWindowTitle("Configure RFID reader")

        # Elements
        self.enabled_group = StyledQGroupBox("Enabled")
        self.enabled_group.setCheckable(True)
        self.id_value_label = QLabel()
        self.keep_value_label = QLabel()
        self.name_edit = QLineEdit()
        warning1 = QLabel(RENAME_WARNING)
        warning2 = QLabel("<b>NOTE:</b> the intended RFID devices are fixed "
                          "in hardware to 9600 bps, 8N1</b>")  # [3]

        # Layout
        form = QFormLayout()
        form.addRow(DEVICE_ID_LABEL, self.id_value_label)
        form.addRow(KEEP_LABEL, self.keep_value_label)
        form.addRow("RFID name", self.name_edit)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form)
        main_layout.addWidget(warning1)
        main_layout.addWidget(warning2)
        main_layout.addWidget(self.sp_group)

        self.enabled_group.setLayout(main_layout)
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.enabled_group)

        # Shared code
        TransactionalEditDialogMixin.__init__(self, session, rfid_config,
                                              top_layout, readonly=readonly)

    def object_to_dialog(self, obj):
        self.enabled_group.setChecked(obj.enabled)
        self.id_value_label.setText(str(obj.id))
        self.keep_value_label.setText(str(obj.keep))
        self.name_edit.setText(obj.name)
        self.object_to_serial_port_group(obj)

    def dialog_to_object(self, obj):
        obj.enabled = self.enabled_group.isChecked()
        try:
            obj.name = self.name_edit.text()
            assert len(obj.name) > 0
        except:
            raise ValidationError("Invalid name")
        self.serial_port_group_to_object(obj)


# =============================================================================
# Edit balance config
# =============================================================================

class BalanceConfigDialog(QDialog, TransactionalEditDialogMixin,
                          SerialPortMixin):

    def __init__(self, session, balance_config, parent=None,
                 readonly=False):
        super().__init__(parent)  # QDialog
        SerialPortMixin.__init__(
            self,
            port_options=AVAILABLE_SERIAL_PORTS,
            baudrate_options=[1200, 2400, 4800, 9600, 19200, 38400],
            bytesize_options=[serial.EIGHTBITS],
            parity_options=[serial.PARITY_NONE, serial.PARITY_EVEN],
            stopbits_options=[serial.STOPBITS_ONE],
            flow_options=[SerialPortMixin.FLOW_NONE,
                          SerialPortMixin.FLOW_XONXOFF],
        )  # [4]
        # RTS/CTS sometimes seems to break it.
        # Manual mentions XON/XOFF only (p15), and says that its serial
        # interface is RS-485, 2-wire, half-duplex (p4, 5).

        reader_map = []
        readers = (
            session.query(RfidReaderConfig)
            .filter(RfidReaderConfig.enabled == True)  # http://stackoverflow.com/questions/18998010  # noqa
            .all()
        )
        for reader in readers:
            reader_map.append((reader.id, reader.name))
        if reader_map:
            reader_map.sort(key=lambda x: natural_keys(x[1]))
            self.reader_ids, self.reader_names = zip(*reader_map)
        else:
            self.reader_ids = []
            self.reader_names = []

        self.setWindowTitle("Configure balance")

        warning1 = QLabel(RENAME_WARNING)
        warning2 = QLabel(
            "<b>NOTE:</b> the intended balance devices default to 9600 bps, "
            "8E1,<br>and are restricted in their serial options")  # [4]
        self.enabled_group = StyledQGroupBox("Enabled")
        self.enabled_group.setCheckable(True)
        self.id_value_label = QLabel()
        self.keep_value_label = QLabel()
        self.name_edit = QLineEdit()
        self.reader_combo = QComboBox()
        self.reader_combo.addItems(self.reader_names)
        self.reader_combo.setEditable(False)
        self.asf_combo = QComboBox()
        self.asf_combo.addItems(list(str(x) for x in POSSIBLE_ASF_MODES))
        self.asf_combo.setEditable(False)
        self.fast_filter_check = QCheckBox()
        self.measurement_rate_hz_combo = QComboBox()
        self.measurement_rate_hz_combo.addItems(
            [str(x) for x in POSSIBLE_RATES_HZ])
        self.measurement_rate_hz_combo.setEditable(False)
        self.stability_n_edit = QLineEdit()
        self.tolerance_kg_edit = QLineEdit()
        self.min_mass_kg_edit = QLineEdit()
        self.unlock_mass_kg_edit = QLineEdit()
        self.refload_mass_kg_edit = QLineEdit()
        self.zero_value_label = QLabel()
        self.refload_value_label = QLabel()
        self.read_continuously_check = QCheckBox()

        form1 = QFormLayout()
        form1.addRow(DEVICE_ID_LABEL, self.id_value_label)
        form1.addRow(KEEP_LABEL, self.keep_value_label)
        form1.addRow("Balance name", self.name_edit)
        form1.addRow("Paired RFID reader", self.reader_combo)

        meas_group = StyledQGroupBox('Measurement settings')
        form2 = QFormLayout()
        form2.addRow("Amplifier signal filter (ASF) mode (0 = none; "
                     "see p37 of manual)", self.asf_combo)
        form2.addRow("Fast response filter (FMD; see p37 of manual)",
                     self.fast_filter_check)
        form2.addRow("Measurement rate (Hz)", self.measurement_rate_hz_combo)
        form2.addRow("Number of consecutive readings judged for stability",
                     self.stability_n_edit)
        form2.addRow("Stability tolerance (kg) (range [max - min] of<br>"
                     "consecutive readings must not exceed this)",
                     self.tolerance_kg_edit)
        form2.addRow("Minimum mass for detection (kg)", self.min_mass_kg_edit)
        form2.addRow("Mass below which balance will unlock (kg)",
                     self.unlock_mass_kg_edit)
        form2.addRow("Reference (calibration) mass (kg)",
                     self.refload_mass_kg_edit)
        form2.addRow("Zero (tare) calibration point", self.zero_value_label)
        form2.addRow("Reference mass calibration point",
                     self.refload_value_label)
        form2.addRow("Read continuously (inefficient)",
                     self.read_continuously_check)

        mg_vl = QVBoxLayout()
        mg_vl.addLayout(form2)
        meas_group.setLayout(mg_vl)

        main_layout = QVBoxLayout()
        main_layout.addWidget(warning1)
        main_layout.addLayout(form1)
        main_layout.addWidget(meas_group)
        main_layout.addWidget(warning2)
        main_layout.addWidget(self.sp_group)

        self.enabled_group.setLayout(main_layout)
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.enabled_group)

        TransactionalEditDialogMixin.__init__(self, session, balance_config,
                                              top_layout, readonly=readonly)

    def object_to_dialog(self, obj):
        self.enabled_group.setChecked(obj.enabled or False)
        self.id_value_label.setText(str(obj.id))
        self.keep_value_label.setText(str(obj.keep))
        self.name_edit.setText(obj.name)
        if obj.reader_id in self.reader_ids:
            self.reader_combo.setCurrentIndex(
                self.reader_ids.index(obj.reader_id))
        else:
            self.reader_combo.setCurrentIndex(0)
        if obj.measurement_rate_hz in POSSIBLE_RATES_HZ:
            self.measurement_rate_hz_combo.setCurrentIndex(
                POSSIBLE_RATES_HZ.index(obj.measurement_rate_hz))
        if obj.amp_signal_filter_mode in POSSIBLE_ASF_MODES:
            self.asf_combo.setCurrentIndex(
                POSSIBLE_ASF_MODES.index(obj.amp_signal_filter_mode))
        self.fast_filter_check.setChecked(obj.fast_response_filter or False)
        self.stability_n_edit.setText(str(obj.stability_n))
        self.tolerance_kg_edit.setText(str(obj.tolerance_kg))
        self.min_mass_kg_edit.setText(str(obj.min_mass_kg))
        self.unlock_mass_kg_edit.setText(str(obj.unlock_mass_kg))
        self.refload_mass_kg_edit.setText(str(obj.refload_mass_kg))
        self.zero_value_label.setText(str(obj.zero_value))
        self.refload_value_label.setText(str(obj.refload_value))
        self.read_continuously_check.setChecked(obj.read_continuously or False)
        self.object_to_serial_port_group(obj)

    def dialog_to_object(self, obj):
        obj.enabled = self.enabled_group.isChecked()
        try:
            obj.name = self.name_edit.text()
            assert len(obj.name) > 0
        except:
            raise ValidationError("Invalid name")
        reader_name = self.reader_combo.currentText()
        try:
            reader_index = self.reader_names.index(reader_name)
            obj.reader_id = self.reader_ids[reader_index]
        except:
            raise ValidationError("Invalid reader")
        try:
            obj.measurement_rate_hz = int(
                self.measurement_rate_hz_combo.currentText())
            assert obj.measurement_rate_hz in POSSIBLE_RATES_HZ
        except:
            raise ValidationError("Invalid measurement_rate_hz")
        try:
            obj.amp_signal_filter_mode = int(self.asf_combo.currentText())
            assert obj.amp_signal_filter_mode in POSSIBLE_ASF_MODES
        except:
            raise ValidationError("Invalid amp_signal_filter_mode")
        obj.fast_response_filter = self.fast_filter_check.isChecked()
        try:
            obj.stability_n = int(self.stability_n_edit.text())
            assert obj.stability_n > 1
        except:
            raise ValidationError("Invalid stability_n")
        try:
            obj.tolerance_kg = float(self.tolerance_kg_edit.text())
            assert obj.tolerance_kg > 0
        except:
            raise ValidationError("Invalid tolerance_kg")
        try:
            obj.min_mass_kg = float(self.min_mass_kg_edit.text())
            assert obj.min_mass_kg > 0
        except:
            raise ValidationError("Invalid min_mass_kg")
        try:
            obj.unlock_mass_kg = float(self.unlock_mass_kg_edit.text())
            assert obj.unlock_mass_kg > 0
        except:
            raise ValidationError("Invalid unlock_mass_kg")
        try:
            obj.refload_mass_kg = float(self.refload_mass_kg_edit.text())
            assert obj.refload_mass_kg > 0
        except:
            raise ValidationError("Invalid refload_mass_kg")
        obj.read_continuously = self.read_continuously_check.isChecked()
        self.serial_port_group_to_object(obj)
        if obj.unlock_mass_kg >= obj.min_mass_kg:
            raise ValidationError(
                "unlock_mass_kg must be less than min_mass_kg")


# =============================================================================
# Tare/calibrate balances
# =============================================================================

class CalibrateBalancesWindow(QDialog):
    def __init__(self, balance_owners, parent=None):
        super().__init__(parent)  # QDialog
        self.setWindowTitle("Calibrate balances")

        grid = QGridLayout()
        for i, balance in enumerate(balance_owners):
            grid.addWidget(QLabel("Balance {}:".format(
                balance.balance_id, balance.name)), i, 0)
            tare_button = QPushButton("&Tare (zero)")
            tare_button.clicked.connect(balance.tare)
            grid.addWidget(tare_button, i, 1)
            calibrate_button = QPushButton("&Calibrate to {} kg".format(
                balance.refload_mass_kg))
            calibrate_button.clicked.connect(balance.calibrate)
            grid.addWidget(calibrate_button, i, 2)

        ok_buttons = QDialogButtonBox(QDialogButtonBox.Ok,
                                      Qt.Horizontal, self)
        ok_buttons.accepted.connect(self.accept)

        vlayout = QVBoxLayout(self)
        vlayout.addLayout(grid)
        vlayout.addWidget(ok_buttons)