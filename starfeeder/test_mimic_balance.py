#!/usr/bin/env python
# starfeeder/test_mimic_balance.py

"""
Very simple program to mimic a weighing balance talking to a serial port, for
testing Starfeeder. This does not use Qt.
"""

import argparse
import logging
import random
from time import sleep
from typing import List

from whisker.logging import configure_logger_for_colour

from starfeeder.balance import (
    BAUDRATE_PAUSE_MS,

    CMD_ASCII_RESULT_OUTPUT,
    CMD_DATA_DELIMITER_COMMA_CR_LF,
    CMD_DEACTIVATE_OUTPUT_SCALING,
    CMD_FILTER_TYPE,
    CMD_MEASUREMENT_RATE,
    CMD_NO_OP,
    CMD_QUERY_BAUD_RATE,
    CMD_QUERY_IDENTIFICATION,
    CMD_QUERY_MEASURE,
    CMD_QUERY_OUTPUT_SCALING,
    CMD_QUERY_STATUS,
    CMD_SET_BAUD_RATE,
    CMD_SET_FILTER,
    CMD_STOP_MEASURING,
    CMD_TARE,
    CMD_WARM_RESTART,

    RATE_MAP_HZ_TO_CODE,

    RESPONSE_NONSPECIFIC_OK,
    RESPONSE_UNKNOWN,

    COMMAND_SEPARATOR,
)
from starfeeder.constants import (
    LOG_FORMAT,
    LOG_DATEFMT,
)
from starfeeder.common_serial_testing import (
    add_serial_port_args,
    CommandLineSerialProcessor,
)
from starfeeder.getch import getch, kbhit
from starfeeder.serial_controller import (
    CRLF,
    LF,
    READ_TIMEOUT_SEC,
)

log = logging.getLogger(__name__)


# =============================================================================
# Behave like a balance
# =============================================================================

class OutputMessage(object):
    def __init__(self, delay_s: float, is_measurement: bool,
                 text: str) -> None:
        self.delay_s = delay_s
        self.is_measurement = is_measurement
        self.text = text


class BalanceMimic(CommandLineSerialProcessor):
    MASS_KG_MEANS = [0, 0.1, 0.350, 0.450]
    # need 0 for tare and 0.1 for calibrate
    MASS_KG_SD = 0.0005
    RESTART_TIME_S = 3
    REPLY_STATUS = "000"
    DEFAULT_MAX_VALUE = 100000
    INTEGER_UNITS_PER_KG = 1000
    IDENTIFICATION = "HBM,PW4 MCR2 2kg   ,70820   ,P52"
    # ... from screenshot (number of spaces may be a bit wrong, though)

    def __init__(self, args: argparse.Namespace, **kwargs) -> None:
        self.read_timeout_sec = READ_TIMEOUT_SEC

        super().__init__(args,
                         inbound_eol=[COMMAND_SEPARATOR, CRLF, LF],
                         outbound_eol=CRLF,
                         read_timeout_sec=self.read_timeout_sec,
                         **kwargs)
        # Device to computer (from our perspective here, outbound): CR+LF
        # Computer to device (here, inbound): no delimiter, single-char commands

        self.baudrate = args.baudrate
        self.parity = args.parity
        self.internal_period_s = self.read_timeout_sec
        self.read_frequency_hz = 6
        self.read_period_s = 1 / self.read_frequency_hz
        self.time_to_next_read = 0
        self.tare_mass_kg = 0.00
        self.current_true_mass_kg = self.MASS_KG_MEANS[0]
        self.output_queue = []  # type: List[OutputMessage]

        log.info("Use keys 0-{} to select a mass".format(
            len(self.MASS_KG_MEANS) - 1))

    def start(self) -> None:
        pass

    def spontaneous(self) -> None:
        if kbhit():
            c = getch()
            mass_index = ord(c) - ord('0')
            if 0 <= mass_index < len(self.MASS_KG_MEANS):
                self.current_true_mass_kg = self.MASS_KG_MEANS[mass_index]
                log.info("Setting mass to {} kg (takes effect at next read "
                         "cycle)".format(self.current_true_mass_kg))
            else:
                log.warning("Key {} invalid; use 0-{}".format(
                    repr(c), len(self.MASS_KG_MEANS) - 1))

        while self.output_queue and self.output_queue[0].delay_s <= 0:
            self.send_line(self.output_queue[0].text)
            self.output_queue.pop(0)
        if self.output_queue:
            self.output_queue[0].delay_s -= self.internal_period_s

    def reply(self, text: str) -> None:
        om = OutputMessage(0, False, text)
        self.output_queue.append(om)

    def clear_queue(self) -> None:
        self.output_queue.clear()

    def line_received(self, line: bytes) -> None:
        log.info("Command received: {}".format(repr(line)))
        if line == CMD_ASCII_RESULT_OUTPUT:
            log.info("CMD_ASCII_RESULT_OUTPUT -> RESPONSE_NONSPECIFIC_OK")
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line == CMD_DATA_DELIMITER_COMMA_CR_LF:
            log.info("CMD_DATA_DELIMITER_COMMA_CR_LF -> "
                     "RESPONSE_NONSPECIFIC_OK")
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line == CMD_DEACTIVATE_OUTPUT_SCALING:
            log.info("CMD_DEACTIVATE_OUTPUT_SCALING -> "
                     "RESPONSE_NONSPECIFIC_OK (?)")
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line.startswith(CMD_FILTER_TYPE):
            rest = line[len(CMD_FILTER_TYPE):]
            log.info("CMD_FILTER_TYPE {} -> RESPONSE_NONSPECIFIC_OK".format(
                rest))
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line.startswith(CMD_MEASUREMENT_RATE):
            rest = line[len(CMD_MEASUREMENT_RATE):]
            try:
                code = int(rest)
                hz = None
                for lookup_hz, lookup_code in RATE_MAP_HZ_TO_CODE.items():
                    if code == lookup_code:
                        hz = lookup_hz
                if hz is None:
                    raise ValueError
                log.info(
                    "CMD_MEASUREMENT_RATE {} -> set measurement rate to {} "
                    "Hz; RESPONSE_NONSPECIFIC_OK".format(rest, hz))
                self.read_frequency_hz = hz
                self.read_period_s = 1 / hz
                self.reply(RESPONSE_NONSPECIFIC_OK)
            except (TypeError, ValueError):
                log.info("CMD_MEASUREMENT_RATE {} [duff] -> "
                         "RESPONSE_UNKNOWN (?)".format(rest))
                self.reply(RESPONSE_UNKNOWN)

        elif line == CMD_NO_OP:
            log.info("CMD_NO_OP -> clear buffer, no reply")

        elif line == CMD_QUERY_IDENTIFICATION:
            log.info("CMD_QUERY_IDENTIFICATION -> {}".format(
                self.IDENTIFICATION))
            self.reply(self.IDENTIFICATION)

        elif line.startswith(CMD_QUERY_MEASURE):
            rest = line[len(CMD_QUERY_MEASURE):]
            try:
                n = int(rest)
                log.info("CMD_QUERY_MEASURE {n} -> send {n} measurements; no "
                         "other reply".format(n=n))
                self.start_measuring(n)
            except (TypeError, ValueError):
                log.info("CMD_QUERY_MEASURE {} [duff] -> "
                         "RESPONSE_UNKNOWN (?)".format(rest))
                self.reply(RESPONSE_UNKNOWN)

        elif line == CMD_QUERY_OUTPUT_SCALING:
            log.info("CMD_QUERY_OUTPUT_SCALING -> {}".format(
                self.DEFAULT_MAX_VALUE))
            self.reply(str(self.DEFAULT_MAX_VALUE))

        elif line == CMD_QUERY_STATUS:
            log.info("CMD_QUERY_STATUS -> {}".format(self.REPLY_STATUS))
            self.reply(self.REPLY_STATUS)

        elif line == CMD_QUERY_BAUD_RATE:
            result = self.baudrate_string()
            delay_s = 0.5 * BAUDRATE_PAUSE_MS / 1000
            log.info("CMD_QUERY_BAUD_RATE -> pause {} s -> {}".format(
                delay_s, result))
            sleep(delay_s)
            self.reply(result)

        elif line.startswith(CMD_SET_BAUD_RATE):
            # MUST BE AFTER line.startswith(CMD_QUERY_BAUD_RATE),
            # since this is a substring of that
            rest = line[len(CMD_SET_BAUD_RATE):]
            log.info("CMD_SET_BAUD_RATE {} -> RESPONSE_NONSPECIFIC_OK".format(
                rest))
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line.startswith(CMD_SET_FILTER):
            rest = line[len(CMD_SET_FILTER):]
            log.info("CMD_SET_FILTER {} -> RESPONSE_NONSPECIFIC_OK".format(
                rest))
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line == CMD_STOP_MEASURING:
            log.info("CMD_STOP_MEASURING -> stop measuring, no reply")
            self.stop_measuring()

        elif line == CMD_TARE:
            log.info("CMD_TARE -> RESPONSE_NONSPECIFIC_OK")
            self.reply(RESPONSE_NONSPECIFIC_OK)

        elif line == CMD_WARM_RESTART:
            log.info("CMD_WARM_RESTART -> wait {} s, clear queue, "
                     "no reply".format(self.RESTART_TIME_S))
            self.clear_queue()
            sleep(self.RESTART_TIME_S)

        else:
            log.info("Unknown command: {} -> RESPONSE_UNKNOWN".format(
                repr(line)))
            self.reply(RESPONSE_UNKNOWN)

    def baudrate_string(self) -> str:
        if self.parity == 'E':
            parity_code = 1
        elif self.parity == 'N':
            parity_code = 0
        else:
            parity_code = 2  # no idea
        return "{:05d},{}".format(self.baudrate, parity_code)

    def start_measuring(self, n_measurements) -> None:
        log.info(
            "Starting to pretend to measure {} masses; current read frequency "
            "is {} Hz (period {} s)".format(
                n_measurements,
                self.read_frequency_hz,
                self.read_period_s,
            ))
        for i in range(n_measurements):
            delay_s = 0 if i == 0 else self.read_period_s
            mass_kg = random.gauss(self.current_true_mass_kg, self.MASS_KG_SD)
            balance_perceived_mass_kg = mass_kg - self.tare_mass_kg
            value = int(balance_perceived_mass_kg * self.INTEGER_UNITS_PER_KG)
            value_text = str(value)
            log.info(
                "QUEUING {i}/{n}: True mass {mass} kg - tare {tare} kg = "
                "perceived mass {perc} kg -> value {val}".format(
                    i=i+1,
                    n=n_measurements,
                    mass=mass_kg,
                    tare=self.tare_mass_kg,
                    perc=balance_perceived_mass_kg,
                    val=value))
            om = OutputMessage(delay_s=delay_s, is_measurement=True,
                               text=value_text)
            self.output_queue.append(om)

    def stop_measuring(self) -> None:
        log.info("Stopping mass reading")
        self.output_queue = [x for x in self.output_queue
                             if not x.is_measurement]


# =============================================================================
# Command-line framework
# =============================================================================

def main() -> None:
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="test_mimic_balance -- to test Starfeeder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        # formatter_class=lambda prog: argparse.ArgumentDefaultsHelpFormatter(
        #     prog, max_help_position=30, width=120)
        # http://stackoverflow.com/questions/5462873/control-formatting-of-the-argparse-help-argument-list  # noqa
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true', help="Be verbose")
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
    log.info("test_mimic_balance")
    log.info("args: {}".format(args))

    mimic = BalanceMimic(args)
    mimic.run()


if __name__ == '__main__':
    main()
