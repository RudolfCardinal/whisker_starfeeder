#!/usr/bin/env python3
# weigh/gui.py

import collections
import logging
logger = logging.getLogger(__name__)
import platform

from PySide.QtCore import Qt, Slot
from PySide.QtGui import (
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
    QPushButton,
    QVBoxLayout,
)
import serial
from serial.tools.list_ports import comports

from weigh.lang import natural_keys
from weigh.models import BalanceConfig, RfidConfig
from weigh.qt import (
    GenericListModel,
    ModalEditListView,
    RadioGroup,
    TransactionalEditDialogMixin,
    ValidationError,
)


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
        self.readonly = readonly

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

        self.set_rfid_button_states(False, False)
        self.set_balance_button_states(False, False)

        # Shared code
        TransactionalEditDialogMixin.__init__(self, session, config,
                                              main_layout, readonly=readonly)

    def object_to_dialog(self, obj):
        self.rfid_effective_time_edit.setText(str(
            obj.rfid_effective_time_s
            if obj.rfid_effective_time_s is not None else ''))
        self.server_edit.setText(obj.server)
        self.port_edit.setText(str(obj.port or ''))
        self.wcm_prefix_edit.setText(obj.wcm_prefix)
        rfid_lm = KeeperCheckGenericListModel(obj.rfid_configs, self)
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
            [(r.name, r.port) for r in obj.rfid_configs]
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
        config = RfidConfig(master_config_id=self.obj.id)
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
            session.query(RfidConfig)
            .filter(RfidConfig.enabled == True)  # http://stackoverflow.com/questions/18998010  # noqa
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
        self.measurement_rate_hz_combo = QComboBox()
        self.measurement_rate_hz_combo.addItems(
            [str(x) for x in POSSIBLE_RATES_HZ])
        self.measurement_rate_hz_combo.setEditable(False)
        self.stability_n_edit = QLineEdit()
        self.tolerance_kg_edit = QLineEdit()
        self.min_mass_kg_edit = QLineEdit()
        self.refload_mass_kg_edit = QLineEdit()
        self.zero_value_label = QLabel()
        self.refload_value_label = QLabel()
        self.read_continuously_check = QCheckBox(
            "Read continuously (inefficient)")

        form1 = QFormLayout()
        form1.addRow(DEVICE_ID_LABEL, self.id_value_label)
        form1.addRow(KEEP_LABEL, self.keep_value_label)
        form1.addRow("Balance name", self.name_edit)
        form1.addRow("Paired RFID reader", self.reader_combo)

        meas_group = StyledQGroupBox('Measurement settings')
        form2 = QFormLayout()
        form2.addRow("Measurement rate (Hz)", self.measurement_rate_hz_combo)
        form2.addRow("Number of consecutive readings judged for stability",
                     self.stability_n_edit)
        form2.addRow("Stability tolerance (kg) (range [max - min] of<br>"
                     "consecutive readings must not exceed this)",
                     self.tolerance_kg_edit)
        form2.addRow("Minimum mass for detection (kg)", self.min_mass_kg_edit)
        form2.addRow("Reference (calibration) mass (kg)",
                     self.refload_mass_kg_edit)
        form2.addRow("Zero (tare) calibration point", self.zero_value_label)
        form2.addRow("Reference mass calibration point",
                     self.refload_value_label)

        mg_vl = QVBoxLayout()
        mg_vl.addLayout(form2)
        mg_vl.addWidget(self.read_continuously_check)
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
        self.stability_n_edit.setText(str(obj.stability_n))
        self.tolerance_kg_edit.setText(str(obj.tolerance_kg))
        self.min_mass_kg_edit.setText(str(obj.min_mass_kg))
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
            obj.refload_mass_kg = float(self.refload_mass_kg_edit.text())
            assert obj.refload_mass_kg > 0
        except:
            raise ValidationError("Invalid refload_mass_kg")
        obj.read_continuously = self.read_continuously_check.isChecked()
        self.serial_port_group_to_object(obj)


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
            tare_button = QPushButton("Tare")
            tare_button.clicked.connect(balance.tare)
            grid.addWidget(tare_button, i, 1)
            calibrate_button = QPushButton("Calibrate to {} kg".format(
                balance.refload_mass_kg))
            calibrate_button.clicked.connect(balance.calibrate)
            grid.addWidget(calibrate_button, i, 2)

        ok_buttons = QDialogButtonBox(QDialogButtonBox.Ok,
                                      Qt.Horizontal, self)
        ok_buttons.accepted.connect(self.accept)

        vlayout = QVBoxLayout(self)
        vlayout.addLayout(grid)
        vlayout.addWidget(ok_buttons)
