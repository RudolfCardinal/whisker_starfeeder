#!/usr/bin/env python3
# weigh/gui.py

import collections
import logging
logger = logging.getLogger(__name__)
import platform

from PySide.QtCore import Qt, Slot
from PySide.QtGui import (
    # QCheckBox,
    QComboBox,
    QDialog,
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

        # Title
        self.setWindowTitle("Configure Starfeeder")

        # Elements
        rfid_effective_time_label = QLabel("RFID effective time (s)")
        self.rfid_effective_time_edit = QLineEdit()
        server_label = QLabel("Whisker server")
        self.server_edit = QLineEdit(placeholderText="typically: localhost")
        port_label = QLabel("Whisker port")
        self.port_edit = QLineEdit(placeholderText="typically: 3233")
        wcm_prefix_label = QLabel("Whisker client message prefix")
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
        lgrid = QGridLayout()
        lgrid.addWidget(rfid_effective_time_label, 0, 0, ALIGNMENT)
        lgrid.addWidget(self.rfid_effective_time_edit, 0, 1, ALIGNMENT)
        logic_group.setLayout(lgrid)

        whisker_group = StyledQGroupBox('Whisker')
        wgrid = QGridLayout()
        wgrid.addWidget(server_label, 0, 0, ALIGNMENT)
        wgrid.addWidget(self.server_edit, 0, 1, ALIGNMENT)
        wgrid.addWidget(port_label, 1, 0, ALIGNMENT)
        wgrid.addWidget(self.port_edit, 1, 1, ALIGNMENT)
        wgrid.addWidget(wcm_prefix_label, 2, 0, ALIGNMENT)
        wgrid.addWidget(self.wcm_prefix_edit, 2, 1, ALIGNMENT)
        whisker_group.setLayout(wgrid)

        rfid_group = StyledQGroupBox('RFID readers')
        rfid_layout_1 = QHBoxLayout()
        rfid_layout_2 = QVBoxLayout()
        self.rfid_add_button = QPushButton('Add')
        self.rfid_add_button.clicked.connect(self.add_rfid)
        self.rfid_remove_button = QPushButton('Remove')
        self.rfid_remove_button.clicked.connect(self.remove_rfid)
        self.rfid_edit_button = QPushButton('Edit')
        self.rfid_edit_button.clicked.connect(self.edit_rfid)
        # ... or double-click
        rfid_layout_2.addWidget(self.rfid_add_button)
        rfid_layout_2.addWidget(self.rfid_remove_button)
        rfid_layout_2.addWidget(self.rfid_edit_button)
        rfid_layout_2.addStretch(1)
        rfid_layout_1.addWidget(self.rfid_lv)
        rfid_layout_1.addLayout(rfid_layout_2)
        rfid_group.setLayout(rfid_layout_1)

        balance_group = StyledQGroupBox('Balances')
        balance_layout_1 = QHBoxLayout()
        balance_layout_2 = QVBoxLayout()
        self.balance_add_button = QPushButton('Add')
        self.balance_add_button.clicked.connect(self.add_balance)
        self.balance_remove_button = QPushButton('Remove')
        self.balance_remove_button.clicked.connect(self.remove_balance)
        self.balance_edit_button = QPushButton('Edit')
        self.balance_edit_button.clicked.connect(self.edit_balance)
        balance_layout_2.addWidget(self.balance_add_button)
        balance_layout_2.addWidget(self.balance_remove_button)
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
        self.rfid_remove_button.setEnabled(maydelete)
        self.rfid_edit_button.setEnabled(selected)

    @Slot()
    def set_balance_button_states(self, selected, maydelete):
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
                 stopbits_options=None):
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
        stopbits_map = [
            (serial.STOPBITS_ONE, "&1"),
            (serial.STOPBITS_ONE_POINT_FIVE, "1.5 (rare)"),
            (serial.STOPBITS_TWO, "&2"),
        ]
        if stopbits_options:
            stopbits_map = [x for x in stopbits_map
                            if x[0] in stopbits_options]
        if parity_options:
            parity_map = [x for x in parity_map if x[0] in parity_options]

        sp_port_label = QLabel("Serial port")
        sp_baudrate_label = QLabel("Speed in bits per second")
        grid = QGridLayout()
        grid.addWidget(sp_port_label, 0, 0, ALIGNMENT)
        grid.addWidget(sp_baudrate_label, 1, 0, ALIGNMENT)
        if self.sp_port_options:
            self.sp_port_combo = QComboBox()
            self.sp_port_combo.setEditable(allow_other_port)
            self.sp_port_combo.addItems(port_options)
            grid.addWidget(self.sp_port_combo, 0, 1, ALIGNMENT)
        else:
            self.sp_port_edit = QLineEdit()
            grid.addWidget(self.sp_port_edit, 0, 1, ALIGNMENT)
        if baudrate_options:
            self.sp_baudrate_combo = QComboBox()
            self.sp_baudrate_combo.setEditable(allow_other_baudrate)
            self.sp_baudrate_combo.addItems([str(x) for x in baudrate_options])
            grid.addWidget(self.sp_baudrate_combo, 1, 1, ALIGNMENT)
        else:
            self.sp_baudrate_edit = QLineEdit()
            grid.addWidget(self.sp_baudrate_edit, 1, 1, ALIGNMENT)

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
        self.sp_flow_rg = RadioGroup(
            [
                (self.FLOW_NONE, "None (not advised)"),
                (self.FLOW_XONXOFF,
                 "&XON/XOFF software flow control (suboptimal)"),
                (self.FLOW_RTSCTS, "&RTS/CTS hardware flow control (ideal)"),
                (self.FLOW_DTRDSR, "&DTR/DSR hardware flow control"),
            ],
            default=self.FLOW_RTSCTS
        )
        sp_flow_layout = QVBoxLayout()
        self.sp_flow_rg.add_buttons_to_layout(sp_flow_layout)
        sp_flow_group.setLayout(sp_flow_layout)

        vlayout = QVBoxLayout()
        vlayout.addLayout(grid)
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
        id_label = QLabel(DEVICE_ID_LABEL)
        self.id_value_label = QLabel()
        keep_label = QLabel(KEEP_LABEL)
        self.keep_value_label = QLabel()
        name_label = QLabel("RFID name")
        self.name_edit = QLineEdit()
        warning1 = QLabel(RENAME_WARNING)
        warning2 = QLabel("<b>NOTE:</b> the intended RFID devices are fixed "
                          "in hardware to 9600 bps, 8N1</b>")  # [3]

        # Layout
        grid = QGridLayout()
        grid.addWidget(id_label, 0, 0, ALIGNMENT)
        grid.addWidget(self.id_value_label, 0, 1, ALIGNMENT)
        grid.addWidget(keep_label, 1, 0, ALIGNMENT)
        grid.addWidget(self.keep_value_label, 1, 1, ALIGNMENT)
        grid.addWidget(name_label, 2, 0, ALIGNMENT)
        grid.addWidget(self.name_edit, 2, 1, ALIGNMENT)

        main_layout = QVBoxLayout()
        main_layout.addLayout(grid)
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
        )  # [4]

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

        self.enabled_group = StyledQGroupBox("Enabled")
        self.enabled_group.setCheckable(True)
        id_label = QLabel(DEVICE_ID_LABEL)
        self.id_value_label = QLabel()
        keep_label = QLabel(KEEP_LABEL)
        self.keep_value_label = QLabel()
        name_label = QLabel("Balance name")
        self.name_edit = QLineEdit()
        warning1 = QLabel(RENAME_WARNING)
        reader_label = QLabel("Paired RFID reader")
        self.reader_combo = QComboBox()
        self.reader_combo.addItems(self.reader_names)
        self.reader_combo.setEditable(False)
        warning2 = QLabel(
            "<b>NOTE:</b> the intended balance devices default to 9600 bps, "
            "8E1,<br>and are restricted in their serial options")  # [4]

        grid = QGridLayout()
        grid.addWidget(id_label, 0, 0, ALIGNMENT)
        grid.addWidget(self.id_value_label, 0, 1, ALIGNMENT)
        grid.addWidget(keep_label, 1, 0, ALIGNMENT)
        grid.addWidget(self.keep_value_label, 1, 1, ALIGNMENT)
        grid.addWidget(name_label, 2, 0, ALIGNMENT)
        grid.addWidget(self.name_edit, 2, 1, ALIGNMENT)
        grid.addWidget(warning1, 3, 0, 1, 2, ALIGNMENT)
        # ... row, col, rowspan, colspan, alignment
        grid.addWidget(reader_label, 4, 0, ALIGNMENT)
        grid.addWidget(self.reader_combo, 4, 1, ALIGNMENT)
        grid.addWidget(warning2, 5, 0, 1, 2, ALIGNMENT)

        main_layout = QVBoxLayout()
        main_layout.addLayout(grid)
        main_layout.addWidget(self.sp_group)

        self.enabled_group.setLayout(main_layout)
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.enabled_group)

        TransactionalEditDialogMixin.__init__(self, session, balance_config,
                                              top_layout, readonly=readonly)

    def object_to_dialog(self, obj):
        self.enabled_group.setChecked(obj.enabled)
        self.id_value_label.setText(str(obj.id))
        self.keep_value_label.setText(str(obj.keep))
        self.name_edit.setText(obj.name)
        if obj.reader_id in self.reader_ids:
            self.reader_combo.setCurrentIndex(
                self.reader_ids.index(obj.reader_id))
        else:
            self.reader_combo.setCurrentIndex(0)
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
        except ValueError:
            raise ValidationError("Invalid reader")
        self.serial_port_group_to_object(obj)
