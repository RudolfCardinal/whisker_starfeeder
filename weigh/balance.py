#!/usr/bin/env python3
# weigh/balance.py

"""
Reference is [4].
Summary of commands on p14.

The balance doesn't have any concept of real-world mass, it seems.
So it needs calibrating.
We should NOT use the tare function, since the tare zero point is lost through
a reset. Instead, let's store it in the database.
"""

import datetime
import math
import re

import bitstring
from PySide.QtCore import QTimer, Signal
import serial

from weigh.constants import GUI_MASS_FORMAT
from weigh.lang import CompiledRegexMemory
from weigh.models import CalibrationReport, MassSingleEvent
from weigh.serial_controller import (
    # CR,
    CRLF,
    # LF,
    SerialController,
    SerialOwner,
)

# Startup sequence
CMD_NO_OP = ""  # p12: a termination character on its own clears the buffer
CMD_WARM_RESTART = "RES"  # p46; no reply; takes up to 3 s
CMD_SET_BAUD_RATE = "BDR"  # p17
CMD_QUERY_BAUD_RATE = "BDR?"  # p17
CMD_ASCII_RESULT_OUTPUT = "COF3"  # p19
CMD_DATA_DELIMITER_COMMA_CR_LF = "TEX172"  # set comma+CRLF as delimiter; p22

CMD_QUERY_IDENTIFICATION = "IDN?"  # p48
CMD_QUERY_STATUS = "ESR?"  # p58

# Signal processing and measurement; see summary on p6
CMD_SET_FILTER = "ASF"  # p37 ***
CMD_FILTER_TYPE = "FMD"  # p37 ***
CMD_DEACTIVATE_OUTPUT_SCALING = "NOV0"  # p31
# ... I can't get any NOV command (apart from the query, NOV?) to produce
# anything other than '?'.
CMD_QUERY_OUTPUT_SCALING = "NOV?"  # p31
CMD_TARE = "TAR"  # p41
CMD_MEASUREMENT_RATE = "ICR"  # p40; "Mv/s" = measured values per second
RATE_MAP_HZ_TO_CODE = {
    100: 0,
    50: 1,
    25: 2,
    12: 3,
    6: 4,
    3: 5,
    2: 6,
    1: 7,
}
CMD_QUERY_MEASURE = "MSV?"
# For example: MSV?10; gives 10 values.
# If you use COF11 then the "status" field isn't a countdown, it's something
# fixed. We don't have a simple countdown, so we have to maintain our own.
# And we can't say "keep going for ever", it seems.
CMD_STOP_MEASURING = "STP"  # p36

# Note also factory defaults on p50.
# Note also LED control, p57
# Examples of communication sequences/startup, p63.

RESET_PAUSE_MS = 3000  # p46
BAUDRATE_PAUSE_MS = 200  # p64 ("approx. 150ms"); p17 ("<15 ms")

RESPONSE_UNKNOWN = '?'
RESPONSE_NONSPECIFIC_OK = '0'
BAUDRATE_REGEX = re.compile(r"^(\d+),(\d)$")  # e.g. 09600,1

# NONSENSE # MASS_REGEX = re.compile(r"^(.*)\s+(\w+)$")  # e.g. "99.99 g" [5]
# ... the balance doesn't actually work out any mass for you.


class BalanceController(SerialController):
    mass_received = Signal(MassSingleEvent)
    calibrated = Signal(CalibrationReport)

    def __init__(self, balance_id, reader_id, serial_args,
                 stability_n, tolerance_kg, min_mass_kg,
                 measurement_rate_hz, read_continuously,
                 zero_value, refload_value, refload_mass_kg,
                 rfid_effective_time_s,
                 **kwargs):
        """
        stability_n  } When stability_n consecutive readings have a range
        tolerance_kg } <= tolerance_kg, the mass is considered stable.
                       The most recent value is then used, on the basis that an
                       asymptotic approach
        min_mass_kg: a mass smaller than this is ignored
        """
        super().__init__(**kwargs)
        self.balance_id = balance_id
        self.reader_id = reader_id
        self.serial_args = serial_args
        self.stability_n = stability_n
        self.tolerance_kg = tolerance_kg
        self.min_mass_kg = min_mass_kg
        self.measurement_rate_hz = measurement_rate_hz
        self.read_continuously = read_continuously
        self.zero_value = zero_value
        self.refload_value = refload_value
        self.refload_mass_kg = refload_mass_kg
        self.rfid_effective_time_s = rfid_effective_time_s

        # The cycle time should be <1 s so the user can ping/tare with a small
        # latency (we don't take the risk of interrupting an ongoing
        # measurement cycle for that). Roughly.
        # So, for example, at 6 Hz we could have 5 per cycle.
        self.measurements_per_batch = math.ceil(0.5 * self.measurement_rate_hz)
        self.reset_timer_1 = QTimer()
        self.reset_timer_1.timeout.connect(self.reset_2)
        self.reset_timer_2 = QTimer()
        self.reset_timer_2.timeout.connect(self.reset_3)
        self.command_queue = []
        self.n_pending_measurements = 0
        self.read_until = datetime.datetime.utcnow()
        self.max_value = 100000  # default (NOV command) is 100,000
        self.recent_measurements_kg = []
        self.pending_calibrate = False
        self.pending_tare = False

    def on_start(self):
        self.reset()

    def send(self, command, params='', reply_expected=True):
        params = str(params)  # just in case we have a number
        if reply_expected:
            self.command_queue.append(command)
        msg = command + params
        super().send(msg)

    def reset(self):
        self.info("Balance resetting: phase 1")
        self.recent_measurements_kg = []
        self.send(CMD_NO_OP, reply_expected=False)  # cancel anything ongoing
        self.send(CMD_STOP_MEASURING, reply_expected=False)
        self.send(CMD_WARM_RESTART, reply_expected=False)
        self.debug("Balance resetting: waiting {} ms for reset".format(
            RESET_PAUSE_MS))
        self.reset_timer_1.setSingleShot(True)
        self.reset_timer_1.start(RESET_PAUSE_MS)

    def reset_2(self):
        self.info("Balance resetting: phase 2")
        baud = self.serial_args['baudrate']
        parity = self.serial_args['parity']
        if parity == serial.PARITY_NONE:
            parity_code = 0
        elif parity == serial.PARITY_EVEN:
            parity_code = 1
        else:
            self.error("Invalid parity ({})! Choosing even parity. "
                       "COMMUNICATION MAY BREAK.")
            parity_code = 1
        self.send(CMD_SET_BAUD_RATE, "{},{}".format(baud, parity_code))
        self.debug("Balance resetting: waiting {} ms for baud rate "
                   "change".format(BAUDRATE_PAUSE_MS))
        self.reset_timer_2.setSingleShot(True)
        self.reset_timer_2.start(BAUDRATE_PAUSE_MS)

    def reset_3(self):
        self.info("Balance resetting: phase 3")
        self.send(CMD_QUERY_BAUD_RATE)
        self.send(CMD_QUERY_IDENTIFICATION)
        self.send(CMD_QUERY_STATUS)
        self.send(CMD_ASCII_RESULT_OUTPUT)
        self.send(CMD_DATA_DELIMITER_COMMA_CR_LF)
        # self.send(CMD_DEACTIVATE_OUTPUT_SCALING)  # Not working
        self.send(CMD_QUERY_OUTPUT_SCALING)
        self.send(CMD_MEASUREMENT_RATE,
                  RATE_MAP_HZ_TO_CODE.get(self.measurement_rate_hz))
        self.start_measuring()

    def start_measuring(self):
        self.n_pending_measurements += self.measurements_per_batch
        self.send(CMD_QUERY_MEASURE, self.measurements_per_batch)
        self.command_queue.extend(
            [CMD_QUERY_MEASURE] * (self.measurements_per_batch - 1))

    def read_until(self, read_until):
        self.read_until = read_until
        now = datetime.datetime.utcnow()
        if self.read_continuously:
            return  # already measuring
        if self.n_pending_measurements == 0 and now < read_until:
            self.start_measuring()

    def tare(self):
        # Don't use hardware tare:
            # # Commands (and output) are neatly queued up behind MSV commands.
            # # So this will happen at the end of the current MSV cycle.
            # self.send(CMD_TARE)
        # Use software tare.
        self.pending_tare = True
        if self.n_pending_measurements == 0:
            self.start_measuring()

    def calibrate(self):
        self.pending_calibrate = True
        if self.n_pending_measurements == 0:
            self.start_measuring()

    def ping(self):
        # Commands (and output) are neatly queued up behind MSV commands.
        # So this will happen at the end of the current MSV cycle.
        self.status("Asking balance for identification")
        self.send(CMD_QUERY_IDENTIFICATION)
        self.status("Asking balance for status")
        self.send(CMD_QUERY_STATUS)

    def stop_measuring(self):
        self.send(CMD_STOP_MEASURING, reply_expected=False)
        self.command_queue = [x for x in self.command_queue
                              if x != CMD_QUERY_MEASURE]
        self.n_pending_measurements = 0

    def on_stop(self):
        self.stop_measuring()
        self.finished.emit()
        # Inelegant! Risk the writer thread will be terminated before it
        # sends this command. Still, ho-hum.

    def report_status(self):
        self.status("Currently scanning" if self.n_pending_measurements > 0
                    else "Not currently scanning")

    def value_to_mass(self, value):
        if None in [self.refload_value, self.zero_value, self.refload_mass_kg]:
            return None
        return (
            self.refload_mass_kg
            * (value - self.zero_value)
            / (self.refload_value - self.zero_value)
        )

    def process_value(self, value, timestamp):
        mass_kg = self.value_to_mass(value)
        if mass_kg is None:
            # self.warning("Balance uncalibrated; ignoring value")
            return
        self.debug("BALANCE VALUE: {} => {} kg".format(
            value, GUI_MASS_FORMAT % mass_kg))
        while len(self.recent_measurements_kg) >= self.stability_n:
            self.recent_measurements_kg.pop(0)
        self.recent_measurements_kg.append(mass_kg)

        # Do we have a stable mass?
        if mass_kg < self.min_mass_kg:
            # Stable but too low (e.g. zero!).
            return
        if len(self.recent_measurements_kg) < self.stability_n:
            # Too few measurements to judge.
            return
        min_kg = min(self.recent_measurements_kg)
        max_kg = max(self.recent_measurements_kg)
        range_kg = max_kg - min_kg
        if range_kg > self.tolerance_kg:
            # Unstable.
            return

        # We have a stable mass!
        mass_single_event = MassSingleEvent(
            balance_id=self.balance_id,
            reader_id=self.reader_id,
            mass_kg=mass_kg,
            timestamp=timestamp,
        )
        self.debug("Stable mass: {}".format(str(mass_single_event)))
        self.mass_received.emit(mass_single_event)

    def tare_with(self, value):
        self.debug("tare_with: {}".format(value))
        self.pending_tare = False
        if value == self.zero_value:
            return  # No change
        if self.zero_value is None:
            self.zero_value = value
        else:
            delta = value - self.zero_value
            self.zero_value += delta
            if self.refload_value is not None:
                self.refload_value += delta
        if self.refload_value == self.zero_value:
            self.refload_value = None  # stupid, would cause division by zero
        self.report_calibration()

    def calibrate_with(self, value):
        self.debug("calibrate_with: {}".format(value))
        self.pending_calibrate = False
        if value == self.refload_value:
            return  # no change
        self.refload_value = value
        if self.refload_value == self.zero_value:
            self.refload_value = None  # stupid, would cause division by zero
        self.report_calibration()

    def report_calibration(self):
        report = CalibrationReport(
            balance_id=self.balance_id,
            zero_value=self.zero_value,
            refload_value=self.refload_value,
        )
        self.calibrated.emit(report)

    def on_rfid(self, rfid_single_event):
        if (rfid_single_event.reader_id != self.reader_id
                or rfid_single_event.balance_id != self.balance_id):
            self.warning("Bad on_rfid message received: {}".format(
                repr(rfid_single_event)))
            self.warning("self.reader_id={}, self.balance_id={}".format(
                self.reader_id, self.balance_id))
            return
        read_until = rfid_single_event.timestamp + datetime.timedelta(
            seconds=self.rfid_effective_time_s)
        self.read_until(read_until)

    def on_receive(self, data, timestamp):
        data = data.decode("ascii")
        gre = CompiledRegexMemory()
        if self.command_queue:
            cmd = self.command_queue.pop(0)
        else:
            cmd = None
        self.debug("Balance receiving at {}: {} (most recent command was: "
                   "{})".format(timestamp, repr(data), cmd))
        self.debug("len(self.command_queue) %d" % len(self.command_queue))

        if cmd == CMD_QUERY_MEASURE:
            try:
                value = int(data)
                if self.pending_tare:
                    self.tare_with(value)
                elif self.pending_calibrate:
                    self.calibrate_with(value)
                else:
                    self.process_value(value, timestamp)
            except ValueError:
                self.error("Balance sent a bad value")
            self.n_pending_measurements -= 1
            self.debug("n_pending_measurements: {}".format(
                self.n_pending_measurements))
            if self.n_pending_measurements == 0:
                if self.read_continuously or timestamp < self.read_until:
                    self.debug("Finished measuring; restarting")
                    self.start_measuring()
        elif (cmd in [CMD_QUERY_BAUD_RATE, CMD_SET_BAUD_RATE]
                and gre.match(BAUDRATE_REGEX, data)):
            baudrate = int(gre.group(1))
            parity_code = int(gre.group(2))
            if parity_code == 1:
                parity = 'E'
            elif parity_code == 0:
                parity = 'N'
            else:
                parity = '?'
            self.status("Balance is using {} bps, parity {}".format(baudrate,
                                                                    parity))
        elif data == RESPONSE_NONSPECIFIC_OK and cmd in [
                CMD_ASCII_RESULT_OUTPUT,
                CMD_DATA_DELIMITER_COMMA_CR_LF,
                CMD_MEASUREMENT_RATE,
                CMD_SET_BAUD_RATE,
                CMD_TARE,
                ]:
            self.status("Balance acknowledges command {}".format(cmd))
        elif cmd == CMD_QUERY_STATUS:
            self.status("Balance status: {}".format(data))
            try:
                bits = bitstring.BitStream(uint=int(data), length=6)
                command_error, execution_error, hardware_error = (
                    bits.readlist('bool, bool, bool, pad:3'))
                self.status(
                    "command_error={}, execution_error={}, "
                    "hardware_error={}".format(command_error, execution_error,
                                               hardware_error))
            except:
                self.status("Can't interpret status")
        elif cmd == CMD_QUERY_IDENTIFICATION:
            self.status("Balance identification: {}".format(data))
        elif cmd == CMD_QUERY_OUTPUT_SCALING:
            try:
                self.max_value = int(data)
            except ValueError:
                self.error("Bad value received")
        elif data == RESPONSE_UNKNOWN:
            self.status("Balance says 'eh?'")
        else:
            self.error("Unknown message from balance: {}".format(repr(data)))


class BalanceOwner(SerialOwner):
    mass_received = Signal(MassSingleEvent)
    ping_requested = Signal()
    tare_requested = Signal()
    calibration_requested = Signal()
    calibrated = Signal(CalibrationReport)

    def __init__(self, balance_config, rfid_effective_time_s, parent=None):
        # Do not keep a copy of rfid_config; it will expire.
        self.balance_id = balance_config.id
        self.name = balance_config.name
        self.reader_id = balance_config.reader_id
        self.refload_mass_kg = balance_config.refload_mass_kg
        serial_args = balance_config.get_serial_args()
        super().__init__(
            serial_args=serial_args,
            parent=parent,
            name=balance_config.name,
            rx_eol=CRLF,
            tx_eol=b";",
            controller_class=BalanceController,
            controller_kwargs=dict(
                balance_id=balance_config.id,
                reader_id=balance_config.reader_id,
                serial_args=serial_args,
                stability_n=balance_config.stability_n,
                tolerance_kg=balance_config.tolerance_kg,
                min_mass_kg=balance_config.min_mass_kg,
                measurement_rate_hz=balance_config.measurement_rate_hz,
                read_continuously=balance_config.read_continuously,
                zero_value=balance_config.zero_value,
                refload_value=balance_config.refload_value,
                refload_mass_kg=balance_config.refload_mass_kg,
                rfid_effective_time_s=rfid_effective_time_s,
            ))
        # Balance uses CR+LF terminator when sending to computer [4].
        # Computer can use LF or semicolon terminator when sending to balance
        # [4].
        # Sometimes a semicolon is accepted but LF isn't (p23), so we use a
        # semicolon.
        self.ping_requested.connect(self.controller.ping)
        self.tare_requested.connect(self.controller.tare)
        self.calibration_requested.connect(self.controller.calibrate)
        self.controller.calibrated.connect(self.calibrated)

    def ping(self):
        self.ping_requested.emit()

    def tare(self):
        self.tare_requested.emit()

    def calibrate(self):
        self.calibration_requested.emit()
