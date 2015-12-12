#!/usr/bin/env python3
# weigh/balance.py

import re

from PySide.QtCore import QTimer, Signal

from weigh.models import MassSingleEvent
from weigh.serial_controller import (
    # CR,
    CRLF,
    # LF,
    SerialController,
)

# Reference is [4]
CMD_ASCII_RESULT_OUTPUT = "COF3"  # p19
CMD_DATA_DELIMITER_COMMA_CR_LF = "TEX172"  # set comma+CRLF as delimiter; p22
CMD_DEACTIVATE_OUTPUT_SCALING = "NOV0"  # p31
CMD_QUERY_IDENTIFICATION = "IDN?"  # p48
CMD_NO_OP = ""  # p12: a termination character on its own clears the buffer
CMD_QUERY_BAUD_RATE = "BDR?"  # p17
CMD_SET_BAUD_RATE = "BDR"  # p17
CMD_STATUS = "ESR"  # p58
CMD_WARM_RESTART = "RES"  # p46

# Note also factory defaults on p50.
# Note also LED control, p57
# Examples of communication sequences/startup, p63.

RESET_PAUSE_MS = 3000  # p46
BAUDRATE_PAUSE_MS = 200  # p64 ("approx. 150ms"); p17 ("<15 ms")

MASS_REGEX = re.compile(r"(.*)\s+(\w+)$")  # e.g. "99.99 g" [5]


class BalanceController(SerialController):
    mass_received = Signal(MassSingleEvent)

    def __init__(self, balance_config, parent=None):
        # Balance uses CR+LF terminator when sending to computer [4].
        # Computer can use LF or semicolon terminator when sending to balance
        # [4].
        # Sometimes a semicolon is accepted but LF isn't (p23), so we use a
        # semicolon.
        super().__init__(balance_config.get_serial_args(), parent=parent,
                         name=balance_config.name, rx_eol=CRLF, tx_eol=b";")
        self.balance_config = balance_config
        self.reset_timer_1 = QTimer()
        self.reset_timer_1.timeout.connect(self.reset_2)
        self.reset_timer_2 = QTimer()
        self.reset_timer_2.timeout.connect(self.reset_3)

    def on_start(self):
        self.reset()

    def reset(self):
        # self.debug("Balance resetting: phase 1")
        # self.send(CMD_NO_OP)  # cancel anything else going on
        # self.send(CMD_WARM_RESTART)  # takes up to 3 seconds, but silent
        # self.debug("Balance resetting: waiting {} ms for reset".format(
        #     RESET_PAUSE_MS))
        self.reset_timer_1.setSingleShot(True)
        self.reset_timer_1.start(RESET_PAUSE_MS)

    def reset_2(self):
        # self.debug("Balance resetting: phase 2")
        # baud = self.balance_config.get_serial_args()['baudrate']
        # parity = self.balance_config.get_serial_args()['parity']
        # if parity == serial.PARITY_NONE:
        #     parity_code = 0
        # elif parity == serial.PARITY_EVEN:
        #     parity_code = 1
        # else:
        #     self.error("Invalid parity ({})!")
        #     return
        # set_rate_cmd = "{}{},{}".format(CMD_SET_BAUD_RATE, baud, parity_code)
        # self.send(set_rate_cmd)
        # self.debug(
        #     "Balance resetting: waiting {} ms for baud rate change".format(
        #         BAUDRATE_PAUSE_MS))
        self.reset_timer_2.setSingleShot(True)
        self.reset_timer_2.start(BAUDRATE_PAUSE_MS)

    def reset_3(self):
        self.debug("Balance resetting: phase 3")
        self.send(CMD_QUERY_BAUD_RATE)
        # self.send(CMD_DATA_DELIMITER_COMMA_CR_LF)
        self.send(CMD_ASCII_RESULT_OUTPUT)
        self.send(CMD_DEACTIVATE_OUTPUT_SCALING)
        self.send(CMD_STATUS)
        # *** set measuring time/frequency with ICR
        # *** then start measuring with MSV and stop with STP?
        # *** call STP when we're quitting?

    def ping(self):
        self.debug("Asking balance for status")
        self.send(CMD_STATUS)
        self.debug("Asking balance for identification")
        self.send(CMD_QUERY_IDENTIFICATION)

    def on_receive(self, data, timestamp):
        data = data.decode("ascii")
        msg = "Balance receiving at {}: {}".format(timestamp, repr(data))
        self.status(msg)
        try:
            m = MASS_REGEX.match(data)
            mass_single_event = MassSingleEvent(
                balance_id=self.balance_config.id,
                mass=float(m.group(1)),
                units=m.group(2),
                timestamp=timestamp,
            )
            self.debug("mass: {}".format(str(mass_single_event)))
            self.mass_received.emit(mass_single_event)
        except:
            self.error("Unknown message from balance: {}".format(repr(data)))
