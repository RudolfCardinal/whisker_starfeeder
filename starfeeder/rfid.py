#!/usr/bin/env python
# starfeeder/rfid.py

"""
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

import re
from typing import Optional

import arrow
import bitstring
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from whisker.qt import exit_on_exception

from starfeeder.serial_controller import (
    # CR,
    CRLF,
    # LF,
    LF_STR,
    NO_BYTES,
    SerialController,
    SerialOwner,
)
from starfeeder.models import (
    BalanceConfig,  # for type hints
    RfidEvent,
    RfidReaderConfig,  # for type hints
)

CMD_RESET_1 = "x"  # response: "MULTITAG-125 01" (+/- "S" as a separate line)
CMD_RESET_2 = "z"  # response: "MULTITAG-125 01"
CMD_REQUEST_VERSION = "v"  # response: "MULTITAG-125 01"
CMD_READING_CONTINUES = "c"  # response: nothing -> RFIDs; "S" after next char
CMD_NO_OP_CANCEL = LF_STR
CMD_LOGIN = "l"  # but response: "?"
CMD_READ_PAGE = "r"  # but response: "?"
CMD_WRITE_PAGE = "w"  # but response: "?"
CMD_DENOMINATION_OF_LED = "d"
CMD_ANTENNA_POWER_OFF = "p"  # response: "P"

RESPONSE_COMMAND_INVALID = "?"
RESPONSE_COMMAND_NOT_EXECUTED = "N"
RESPONSE_CONTINUOUS_READ_STOPPED = "S"
RESPONSE_ANTENNA_OFF = "P"

HELLO_REGEX = re.compile(r"^MULTITAG(.*)$")

RESET_PAUSE_MS = 200


def ztag_to_rfid_number(ztag: str) -> Optional[int]:
    """
    Parses a Z-tag from the RFID reader. Examples:
        Z5A2080A70C2C0001 [= RFID 208210000479322; 208 = Denmark]
        Z1FC68BAD50870001 [= RFID 900046000071672; 900 = user-assigned]

    References:
    - [6], though very hard to read; ignored
    - http://www.priority1design.com.au/fdx-b_animal_identification_protocol.html  # noqa
    - https://en.wikipedia.org/wiki/ISO_11784_%26_11785
    - http://www.gizmolab.co.za/fdx-b-protocol/
    - http://python-bitstring.googlecode.com/svn/trunk/doc/bitstring_manual.pdf

    The RFID tag reader uses the FDX-B protocol [6].

    Country codes:
    - https://en.wikipedia.org/wiki/ISO_3166-1
    - UK is 826 decimal

    What I think is going on:
    - The FDX-B protocol sends 128 bits of data:
        11 header bits
        64 identification bits with [plus] 8 control bits
        16 bits of CRC with 2 control bits
        24 bits of extended data with [plus] 3 control bits
        ... 11 + 64 + 8 + 16 + 2 + 24 + 3 = 128
    - The Z tag contains 16 hex characters = 8 bytes = 64 bits.
      So that's probably the 64 identification bits, with the control bits
      stripped out. (Yes; confirmed by match to bar code at the end.)
    - The 64 identification bits look like this:
            (https://en.wikipedia.org/wiki/ISO_11784_%26_11785#FDX)
        38 bits of identification code
            ... NOTE: little-endian (LSB to "left")
        10 bits of country code (or 999 decimal = test transponder)
            ... NOTE: little-endian (LSB to "left")
         1 bit of "additional data block yes (1) or no (0)"
         7 bits of padding
         7 bits of padding
         1 bit of "animal identification yes (1) or no (0)"

    - Reading: bitstring is great. But it can't read a little-endian integer
      directly from a segment that's not a multiple of 8 bytes (not sure why!).
      So we can't map "uintle:38" to national_id; instead, we map "bits:38" to
      national_id_bits, reverse it, and take its number.

    - At the end, rfid_string and rfid_int should match the number on the tag's
      bar code.
    - The final number is at most 15 digits (3 country, 12 national_id).
    - A 32-bit signed integer goes up to 2,147,483,647 -- not enough.
    - A 32-bit unsigned integer goes up to 4,294,967,295 -- not enough.
    - A 64-bit unsigned integer goes up to 18,446,744,073,709,551,615 -- OK.
    - A 64-bit signed integer goes up to +9,223,372,036,854,775,807 -- OK.
    - So as long as it's 64-bit, we're OK.
    """
    if not isinstance(ztag, str) or len(ztag) != 17 or ztag[0] != 'Z':
        return None
    hexcode = ztag[1:]
    bits = bitstring.BitStream(hex=hexcode)
    national_id_bits, country_bits, has_additional_data, is_animal_id = (
        bits.readlist('bits:38, bits:10, bool, pad:7, pad:7, bool'))
    national_id_bits.reverse()  # little-endian to big-endian
    national_id = national_id_bits.uint
    country_bits.reverse()
    country = country_bits.uint
    rfid_string = str(country) + str(national_id).zfill(12)
    rfid_int = int(rfid_string)
    return rfid_int


class RfidController(SerialController):
    """
    Serial controller that knows about RFID reader devices.

    - RFID protocol uses a CR+LF delimiter [3] from device to computer.
    - DO NOT use a terminator from computer to RFID; send single characters
      only. (For example, if you send 'c\n', the 'c' will start the reader
      and the '\n' wil stop it.)
    - Commands/responses from [3].
    """
    rfid_received = pyqtSignal(RfidEvent)

    def __init__(self, reader_config: RfidReaderConfig,
                 balance_config: BalanceConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.reader_config = reader_config
        self.balance_config = balance_config
        self.swallow_next_stopped_read = False
        self.reset_timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self.reset_timer.timeout.connect(self.reset_2)

    def send(self, data: str, delay_ms: int = 0) -> None:
        self.send_str(data, delay_ms)

    @pyqtSlot()
    @exit_on_exception
    def on_start(self) -> None:
        self.reset()

    @pyqtSlot()
    @exit_on_exception
    def on_stop(self) -> None:
        self.send(CMD_NO_OP_CANCEL)  # something to cancel any ongoing read
        self.finished.emit()
        # Inelegant! Risk the writer thread will be terminated before it
        # sends this command. Still, ho-hum.

    @pyqtSlot()
    @exit_on_exception
    def reset(self) -> None:
        self.info("Resetting RFID: phase 1")
        self.swallow_next_stopped_read = True
        self.send(CMD_NO_OP_CANCEL)  # something to cancel any ongoing read
        self.debug("RFID resetting: waiting {} ms for reset".format(
            RESET_PAUSE_MS))
        self.reset_timer.setSingleShot(True)
        self.reset_timer.start(RESET_PAUSE_MS)
        # POTENTIALLY SUBOPTIMAL: these pauses are in the GUI (main) thread,
        # so could be disrupted by something going wrong on the main event
        # loop. The solution would be to use a class derived from SerialWriter
        # and pass it to the SerialController constructor. And then think about
        # how we then see that class instance to connect up its signals.
        # Anyway, let's not over-complicate it for now; resetting isn't a
        # common thing, and the user will have triggered it directly.

    @pyqtSlot()
    def reset_2(self) -> None:
        self.info("Resetting RFID: phase 2")
        self.swallow_next_stopped_read = False
        self.send(CMD_RESET_1)  # again, to make sure we actually reset
        # Wait for the RFID to say hello before we start reading, or the read
        # command will be swallowed up during the reset.

    def start_reading(self) -> None:
        self.info("Asking RFID to start reading")
        self.send(CMD_READING_CONTINUES)

    @pyqtSlot(str, arrow.Arrow)
    def on_receive(self, data: str, timestamp: arrow.Arrow) -> None:
        if not isinstance(data, str):
            self.critical("bad data: {}".format(repr(data)))
            return
        if not isinstance(timestamp, arrow.Arrow):
            self.critical("bad timestamp: {}".format(repr(timestamp)))
            return
        self.debug("Receiving at {}: {}".format(timestamp, repr(data)))
        if data == RESPONSE_COMMAND_INVALID:
            self.debug("RESPONSE_COMMAND_INVALID")
            # We might get this because we send CMD_NO_OP_CANCEL either in the
            # "waiting for command" state (which will produce '?') or in the
            # "continuous read" state, which will cancel the read.
        elif data == RESPONSE_COMMAND_NOT_EXECUTED:
            self.error("RESPONSE_COMMAND_NOT_EXECUTED")
        elif data == RESPONSE_CONTINUOUS_READ_STOPPED:
            self.info("RESPONSE_CONTINUOUS_READ_STOPPED")
            if self.swallow_next_stopped_read:
                self.swallow_next_stopped_read = False
            else:
                self.start_reading()
        elif data == RESPONSE_ANTENNA_OFF:
            self.info("RESPONSE_ANTENNA_OFF")
        elif HELLO_REGEX.match(data):
            self.status("RFID reader says hello: {}".format(repr(data)))
            self.start_reading()
        else:
            # Should be a Z-tag; see above.
            rfid_number = ztag_to_rfid_number(data)
            if rfid_number is None:
                self.error("Received unknown data: {}".format(repr(data)))
                return
            self.debug("rfid number = {}".format(rfid_number))
            # WATCH OUT. Signal "int" values are 32-bit. So we should
            # emit a Python object instead.
            rfid_event = RfidEvent(
                reader_id=self.reader_config.id,
                reader_name=self.reader_config.name,
                rfid=rfid_number,
                timestamp=timestamp)
            self.rfid_received.emit(rfid_event)


class RfidOwner(SerialOwner):  # GUI thread
    # Outwards, to world:
    rfid_received = pyqtSignal(RfidEvent)
    # Inwards, to posessions:
    reset_requested = pyqtSignal()

    def __init__(self, rfid_config: RfidReaderConfig, callback_id: int,
                 parent: QObject = None) -> None:
        # Do not keep a copy of rfid_config; it will expire.
        super().__init__(
            serial_args=rfid_config.get_serial_args(),
            parent=parent,
            callback_id=callback_id,
            name=rfid_config.name,
            rx_eol=CRLF,
            tx_eol=NO_BYTES,
            controller_class=RfidController,
            controller_kwargs=dict(
                reader_config=rfid_config.get_attrdict(),
                balance_config=(rfid_config.balance.get_attrdict()
                                if rfid_config.balance else None),
            ))
        self.reader_id = rfid_config.id  # used by main GUI
        self.name = rfid_config.name  # used by main GUI
        self.reset_requested.connect(self.controller.reset)
        self.controller.rfid_received.connect(self.rfid_received)  # different thread  # noqa

    def reset(self) -> None:
        self.reset_requested.emit()
