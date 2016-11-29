#!/usr/bin/env python
# starfeeder/balance.py

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

NOTES:
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
from typing import Optional

import arrow
import bitstring
from PySide.QtCore import QObject, Signal
import serial
from whisker.lang import CompiledRegexMemory
from whisker.qt import exit_on_exception

from starfeeder.constants import (
    BALANCE_ASF_MINIMUM,
    BALANCE_ASF_MAXIMUM,
    GUI_MASS_FORMAT,
)
from starfeeder.models import (
    BalanceConfig,  # for type hints
    CalibrationReport,
    MassEvent,
    RfidEvent,
    RfidReaderConfig,  # for type hints
)
from starfeeder.serial_controller import (
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
CMD_SET_FILTER = "ASF"  # p37
CMD_FILTER_TYPE = "FMD"  # p37
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

COMMAND_SEPARATOR = b";"

# NONSENSE # MASS_REGEX = re.compile(r"^(.*)\s+(\w+)$")  # e.g. "99.99 g" [5]
# ... the balance doesn't actually work out any mass for you.


class BalanceController(SerialController):
    mass_received = Signal(MassEvent)
    calibrated = Signal(CalibrationReport)

    def __init__(self,
                 balance_config: BalanceConfig,
                 reader_config: RfidReaderConfig,
                 rfid_effective_time_s: float,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.balance_config = balance_config
        self.reader_config = reader_config
        self.rfid_effective_time_s = rfid_effective_time_s

        # The cycle time should be <1 s so the user can ping/tare with a small
        # latency (we don't take the risk of interrupting an ongoing
        # measurement cycle for that). Roughly.
        # So, for example, at 6 Hz we could have 5 per cycle.
        self.measurements_per_batch = math.ceil(
            0.5 * self.balance_config.measurement_rate_hz)
        self.command_queue = []
        self.n_pending_measurements = 0
        self.rfid_event_rfid = None
        self.rfid_event_expires = arrow.now()
        self.max_value = 100000  # default (NOV command) is 100,000
        self.recent_measurements_kg = []
        self.pending_calibrate = False
        self.pending_tare = False
        self.locked = False

    @exit_on_exception
    def on_start(self) -> None:
        self.reset()
        self.check_calibrated()

    def send(self, command: str, params: str = '', reply_expected: bool = True,
             delay_ms: int = 0) -> None:
        params = str(params)  # just in case we have a number
        if reply_expected:
            self.command_queue.append(command)
        msg = command + params
        super().send(msg, delay_ms)

    def check_calibrated(self) -> None:
        if self.value_to_mass(1) is None:
            self.warning("Balance uncalibrated; will not read yet")

    def reset(self) -> None:
        self.info("Balance resetting")
        self.recent_measurements_kg = []
        baud = self.balance_config.baudrate
        parity = self.balance_config.parity
        if parity == serial.PARITY_NONE:
            parity_code = 0
        elif parity == serial.PARITY_EVEN:
            parity_code = 1
        else:
            self.error("Invalid parity ({})! Choosing even parity. "
                       "COMMUNICATION MAY BREAK.")
            parity_code = 1

        self.send(CMD_NO_OP, reply_expected=False)  # cancel anything ongoing
        self.send(CMD_STOP_MEASURING, reply_expected=False)
        self.send(CMD_WARM_RESTART, reply_expected=False)
        # We want a short pause before sending the next command... but we can
        # line it up safely with this:.
        self.send(CMD_SET_BAUD_RATE, "{},{}".format(baud, parity_code),
                  delay_ms=RESET_PAUSE_MS)
        # Likewise a pause next (organized by the SerialWriter)...
        self.send(CMD_QUERY_BAUD_RATE, delay_ms=BAUDRATE_PAUSE_MS)
        self.send(CMD_QUERY_IDENTIFICATION)
        self.send(CMD_QUERY_STATUS)
        self.send(CMD_ASCII_RESULT_OUTPUT)
        self.send(CMD_DATA_DELIMITER_COMMA_CR_LF)
        # self.send(CMD_DEACTIVATE_OUTPUT_SCALING)  # Not working
        self.send(CMD_QUERY_OUTPUT_SCALING)
        asf = self.balance_config.amp_signal_filter_mode
        if asf < BALANCE_ASF_MINIMUM or asf > BALANCE_ASF_MAXIMUM:
            self.warning("Bad ASF mode ignored: {}".format(asf))
        else:
            self.send(CMD_SET_FILTER, asf)
        # noinspection PyTypeChecker
        self.send(CMD_FILTER_TYPE,
                  1 if self.balance_config.fast_response_filter else 0)
        # noinspection PyTypeChecker
        self.send(CMD_MEASUREMENT_RATE, RATE_MAP_HZ_TO_CODE.get(
            self.balance_config.measurement_rate_hz))
        self.start_measuring()

    def start_measuring(self) -> None:
        self.n_pending_measurements += self.measurements_per_batch
        # noinspection PyTypeChecker
        self.send(CMD_QUERY_MEASURE, self.measurements_per_batch)
        self.command_queue.extend(
            [CMD_QUERY_MEASURE] * (self.measurements_per_batch - 1))

    def read_until(self, when_to_read_until: arrow.Arrow) -> None:
        self.rfid_event_expires = when_to_read_until
        now = arrow.now()
        if self.balance_config.read_continuously:
            return  # already measuring
        if self.n_pending_measurements == 0 and now < self.rfid_event_expires:
            self.start_measuring()

    @exit_on_exception
    def tare(self) -> None:
        # Don't use hardware tare:
            # # Commands (and output) are neatly queued up behind MSV commands.
            # # So this will happen at the end of the current MSV cycle.
            # self.send(CMD_TARE)
        # Use software tare.
        self.pending_tare = True
        if self.n_pending_measurements == 0:
            self.start_measuring()

    @exit_on_exception
    def calibrate(self) -> None:
        self.pending_calibrate = True
        if self.n_pending_measurements == 0:
            self.start_measuring()

    @exit_on_exception
    def ping(self) -> None:
        self.check_calibrated()
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

    @exit_on_exception
    def on_stop(self) -> None:
        self.stop_measuring()
        self.finished.emit()
        # Inelegant! Risk the writer thread will be terminated before it
        # sends this command. Still, ho-hum.

    def report_status(self) -> None:
        self.status("Currently scanning" if self.n_pending_measurements > 0
                    else "Not currently scanning")

    def value_to_mass(self, value: int) -> Optional[float]:
        r = self.balance_config.refload_value
        z = self.balance_config.zero_value
        m = self.balance_config.refload_mass_kg
        if None in [r, z, m]:
            return None
        return m * (value - z) / (r - z)

    def is_stable(self) -> bool:
        # Do we have a stable mass?
        if len(self.recent_measurements_kg) < self.balance_config.stability_n:
            # ... not enough measurements to judge
            return False
        min_kg = min(self.recent_measurements_kg)
        max_kg = max(self.recent_measurements_kg)
        range_kg = max_kg - min_kg
        if range_kg > self.balance_config.tolerance_kg:
            return False
        # Stable.
        return True

    def process_value(self, value: int, timestamp: arrow.Arrow) -> None:
        mass_kg = self.value_to_mass(value)
        if mass_kg is None:
            self.debug("Balance uncalibrated; ignoring value")
            return
        self.debug("BALANCE VALUE: {} => {} kg".format(
            value, GUI_MASS_FORMAT % mass_kg))
        while (len(self.recent_measurements_kg) >=
                self.balance_config.stability_n):
            self.recent_measurements_kg.pop(0)
        self.recent_measurements_kg.append(mass_kg)
        rfid_valid = timestamp < self.rfid_event_expires
        rfid = self.rfid_event_rfid if rfid_valid else None
        identified = rfid is not None
        stable = self.is_stable()
        stable_high = stable and mass_kg >= self.balance_config.min_mass_kg
        stable_low = stable and mass_kg <= self.balance_config.unlock_mass_kg
        lock_now = stable_high and identified and not self.locked
        unlock_now = stable_low and self.locked
        mass_event = MassEvent(
            balance_id=self.balance_config.id,
            balance_name=self.balance_config.name,
            reader_id=self.reader_config.id,
            reader_name=self.reader_config.name,
            rfid=rfid,
            mass_kg=mass_kg,
            timestamp=timestamp,
            stable=stable,
            locked=lock_now,
        )
        if lock_now:
            self.locked = True
            self.debug("LOCKING at {}".format(mass_kg))
        elif unlock_now:
            self.locked = False
            self.debug("UNLOCKING at {}".format(mass_kg))
        self.mass_received.emit(mass_event)

    def tare_with(self, value: int) -> None:
        self.debug("tare_with: {}".format(value))
        self.pending_tare = False
        if value == self.balance_config.zero_value:
            return  # No change
        if self.balance_config.zero_value is None:
            self.balance_config.zero_value = value
        else:
            delta = value - self.balance_config.zero_value
            self.balance_config.zero_value += delta
            if self.balance_config.refload_value is not None:
                self.balance_config.refload_value += delta
        self.finish_calibration()

    def calibrate_with(self, value: int) -> None:
        self.debug("calibrate_with: {}".format(value))
        self.pending_calibrate = False
        if value == self.balance_config.refload_value:
            return  # no change
        self.balance_config.refload_value = value
        self.finish_calibration()

    def finish_calibration(self) -> None:
        if self.balance_config.refload_value == self.balance_config.zero_value:
            # would cause division by zero
            self.balance_config.refload_value = None
        report = CalibrationReport(
            balance_id=self.balance_config.id,
            balance_name=self.balance_config.name,
            zero_value=self.balance_config.zero_value,
            refload_value=self.balance_config.refload_value,
            refload_mass_kg=self.balance_config.refload_mass_kg,
        )
        self.calibrated.emit(report)
        self.check_calibrated()

    @exit_on_exception
    def on_rfid(self, rfid_event: RfidEvent) -> None:
        if not isinstance(rfid_event, RfidEvent):
            self.critical("Bad rfid_event: {}".format(rfid_event))
            return
        rfid_event_expires = rfid_event.timestamp + datetime.timedelta(
            seconds=self.rfid_effective_time_s)  # type: arrow.Arrow
        # ... an Arrow plus a timedelta gives an Arrow
        self.rfid_event_rfid = rfid_event.rfid
        self.read_until(rfid_event_expires)

    @exit_on_exception
    def on_receive(self, data: bytes, timestamp: arrow.Arrow) -> None:
        if not isinstance(data, bytes):
            self.critical("bad data: {}".format(repr(data)))
            return
        if not isinstance(timestamp, arrow.Arrow):
            self.critical("bad timestamp: {}".format(repr(timestamp)))
            return
        data = data.decode("ascii")
        gre = CompiledRegexMemory()
        if self.command_queue:
            cmd = self.command_queue.pop(0)
        else:
            cmd = None
        self.debug("Balance receiving at {}: {} (most recent command was: "
                   "{})".format(timestamp, repr(data), cmd))
        # self.debug("len(self.command_queue) %d" % len(self.command_queue))

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
            if (self.n_pending_measurements == 0 and
                    (self.balance_config.read_continuously or
                        self.locked or
                        timestamp < self.rfid_event_expires)):
                self.debug("Finished measuring; restarting")
                self.start_measuring()
        elif (cmd in [CMD_QUERY_BAUD_RATE, CMD_SET_BAUD_RATE] and
                gre.match(BAUDRATE_REGEX, data)):
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
        elif (data == RESPONSE_NONSPECIFIC_OK and
                cmd in [
                    CMD_ASCII_RESULT_OUTPUT,
                    CMD_DATA_DELIMITER_COMMA_CR_LF,
                    CMD_FILTER_TYPE,
                    CMD_MEASUREMENT_RATE,
                    CMD_SET_BAUD_RATE,
                    CMD_SET_FILTER,
                    CMD_TARE,
                ]):
            self.status("Balance acknowledges command {}".format(cmd))
        elif cmd == CMD_QUERY_STATUS:
            self.status("Balance status: {}".format(data))
            # noinspection PyBroadException
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
            self.error(
                "Unknown message from balance: {} (for command: {})".format(
                    repr(data), repr(cmd)))


class BalanceOwner(SerialOwner):
    # Outwards, to world:
    mass_received = Signal(MassEvent)
    calibrated = Signal(CalibrationReport)
    # Inwards, to posessions:
    ping_requested = Signal()
    tare_requested = Signal()
    calibration_requested = Signal()
    on_rfid = Signal(RfidEvent)

    def __init__(self,
                 balance_config: BalanceConfig,
                 rfid_effective_time_s: float,
                 callback_id: int,
                 parent: QObject = None) -> None:
        # Do not keep a copy of balance_config; it will expire.
        super().__init__(
            serial_args=balance_config.get_serial_args(),
            parent=parent,
            callback_id=callback_id,
            name=balance_config.name,
            rx_eol=CRLF,
            tx_eol=COMMAND_SEPARATOR,
            controller_class=BalanceController,
            controller_kwargs=dict(
                balance_config=balance_config.get_attrdict(),
                reader_config=balance_config.reader.get_attrdict(),
                rfid_effective_time_s=rfid_effective_time_s,
            ))
        # Balance uses CR+LF terminator when sending to computer [4].
        # Computer can use LF or semicolon terminator when sending to balance
        # [4].
        # Sometimes a semicolon is accepted but LF isn't (p23), so we use a
        # semicolon.
        self.balance_id = balance_config.id  # used by main GUI
        self.name = balance_config.name  # used by main GUI
        self.refload_mass_kg = balance_config.refload_mass_kg  # used by GUI (tare dialog)  # noqa
        self.ping_requested.connect(self.controller.ping)
        self.tare_requested.connect(self.controller.tare)
        self.calibration_requested.connect(self.controller.calibrate)
        self.on_rfid.connect(self.controller.on_rfid)
        self.controller.mass_received.connect(self.mass_received)
        self.controller.calibrated.connect(self.calibrated)

    def ping(self) -> None:
        self.ping_requested.emit()

    def tare(self) -> None:
        self.tare_requested.emit()

    def calibrate(self) -> None:
        self.calibration_requested.emit()
