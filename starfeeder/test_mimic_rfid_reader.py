#!/usr/bin/env python
# starfeeder/test_mimic_rfid_reader.py

"""
Very simple program to mimic an RFID reader talking to a serial port, for
testing Starfeeder. This does not use Qt.
"""

import argparse
import logging

from whisker.logging import configure_logger_for_colour

from starfeeder.constants import (
    LOG_FORMAT,
    LOG_DATEFMT,
)
from starfeeder.common_serial_testing import (
    add_serial_port_args,
    coin,
    CommandLineSerialProcessor,
)
from starfeeder.getch import getch, kbhit
from starfeeder.rfid import (
    CMD_RESET_1,
    CMD_RESET_2,
    CMD_REQUEST_VERSION,
    CMD_READING_CONTINUES,
    CMD_NO_OP_CANCEL,
    CMD_LOGIN,
    CMD_READ_PAGE,
    CMD_WRITE_PAGE,
    CMD_DENOMINATION_OF_LED,
    CMD_ANTENNA_POWER_OFF,

    RESPONSE_COMMAND_INVALID,
    # RESPONSE_COMMAND_NOT_EXECUTED,
    RESPONSE_CONTINUOUS_READ_STOPPED,
    RESPONSE_ANTENNA_OFF,
)
from starfeeder.serial_controller import (
    CRLF,
    # NO_BYTES,
    READ_TIMEOUT_SEC,
)

log = logging.getLogger(__name__)


# =============================================================================
# Behave like an RFID reader
# =============================================================================

class RfidMimic(CommandLineSerialProcessor):
    RFID_ZTAG_EXAMPLES = [
        None,
        'Z5A2080A70C2C0001',
        'Z1FC68BAD50870001',
    ]
    VERSION = "MULTITAG-125 01"

    def __init__(self, args: argparse.Namespace, **kwargs) -> None:
        self.read_timeout_sec = READ_TIMEOUT_SEC
        super().__init__(args,
                         inbound_eol=None, inbound_bytewise=True,
                         outbound_eol=CRLF,
                         read_timeout_sec=self.read_timeout_sec,
                         **kwargs)
        # Device to computer (from our perspective here, outbound): CR+LF
        # Computer to device (here, inbound): no delimiter, single-char commands

        # noinspection PyUnresolvedReferences
        self.mean_time_between_rfids_s = args.mean_time_between_rfids_s
        mean_num_reads_per_rfid = (
            self.mean_time_between_rfids_s / self.read_timeout_sec)
        self.p_send = 1 / mean_num_reads_per_rfid
        self.reading = False
        self.current_rfid = None

        log.info("Use keys 0-{} to select an RFID".format(
            len(self.RFID_ZTAG_EXAMPLES) - 1))

    def start(self) -> None:
        pass

    def spontaneous(self) -> None:
        if kbhit():
            c = getch()
            rfid_index = ord(c) - ord('0')
            if 0 <= rfid_index < len(self.RFID_ZTAG_EXAMPLES):
                self.current_rfid = self.RFID_ZTAG_EXAMPLES[rfid_index]
                log.info("Setting RFID to {}".format(self.current_rfid))
            else:
                log.warning("Key {} invalid; use 0-{}".format(
                    repr(c), len(self.RFID_ZTAG_EXAMPLES) - 1))

        if self.reading:
            # log.debug("shall we send one? p = {}".format(self.p_send))
            if coin(self.p_send):
                if self.current_rfid is not None:
                    self.send_line(self.current_rfid)

    def line_received(self, line: bytes) -> None:
        log.info("Command received: {}".format(repr(line)))

        if line == CMD_RESET_1:
            log.info("CMD_RESET_1 -> send version")
            self.send_line(self.VERSION)

        elif line == CMD_RESET_2:
            log.info("CMD_RESET_2 -> send version")
            self.send_line(self.VERSION)

        elif line == CMD_REQUEST_VERSION:
            log.info("CMD_REQUEST_VERSION -> send version")
            self.send_line(self.VERSION)

        elif line == CMD_READING_CONTINUES:
            log.info("CMD_READING_CONTINUES -> start reading")
            self.start_reading()
            # but no overt reply

        elif line == CMD_NO_OP_CANCEL:
            log.info("CMD_NO_OP_CANCEL -> don't know")

        elif line == CMD_LOGIN:
            log.info("CMD_LOGIN -> RESPONSE_COMMAND_INVALID")
            self.send_line(RESPONSE_COMMAND_INVALID)

        elif line == CMD_READ_PAGE:
            log.info("CMD_READ_PAGE -> RESPONSE_COMMAND_INVALID")
            self.send_line(RESPONSE_COMMAND_INVALID)

        elif line == CMD_WRITE_PAGE:
            log.info("CMD_WRITE_PAGE -> RESPONSE_COMMAND_INVALID")
            self.send_line(RESPONSE_COMMAND_INVALID)

        elif line == CMD_DENOMINATION_OF_LED:
            log.info("CMD_DENOMINATION_OF_LED -> don't know")

        elif line == CMD_ANTENNA_POWER_OFF:
            if self.reading:
                log.info("CMD_ANTENNA_POWER_OFF -> was reading -> "
                         "stop reading; RESPONSE_CONTINUOUS_READ_STOPPED")
                self.send_line(RESPONSE_CONTINUOUS_READ_STOPPED)
                self.stop_reading()
            else:
                log.info("CMD_ANTENNA_POWER_OFF -> wasn't reading -> "
                         "RESPONSE_ANTENNA_OFF (?)")
                self.send_line(RESPONSE_ANTENNA_OFF)  # I think?

        else:
            log.warning("Unknown command received: {} -> "
                        "RESPONSE_COMMAND_INVALID".format(repr(line)))
            self.send_line(RESPONSE_COMMAND_INVALID)

    def start_reading(self) -> None:
        log.info("Starting to pretend to read RFID tags")
        self.reading = True

    def stop_reading(self) -> None:
        log.info("Stopping RFID tag reading")
        self.reading = False


# =============================================================================
# Command-line framework
# =============================================================================

def main() -> None:
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="test_mimic_rfid_reader -- to test Starfeeder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--verbose', '-v', action='store_true', help="Be verbose")
    parser.add_argument(
        '--mean_time_between_rfids_s', type=float, default=1.0,
        help="Mean time between RFID generation (s) when reading")
    add_serial_port_args(parser)
    args = parser.parse_args()
    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=loglevel)
    rootlogger = logging.getLogger()
    rootlogger.setLevel(loglevel)
    configure_logger_for_colour(rootlogger)  # configure root logger
    # -------------------------------------------------------------------------
    # Go
    # -------------------------------------------------------------------------
    log.info("test_mimic_rfid_reader")
    log.info("args: {}".format(args))

    mimic = RfidMimic(args)
    mimic.run()


if __name__ == '__main__':
    main()
