#!/usr/bin/env/python
# starfeeder/common_serial_testing.py

from argparse import ArgumentParser, Namespace
import logging
import random
import re
from typing import Optional, Pattern, Sequence, Union

import serial

from starfeeder.serial_controller import LF, READ_TIMEOUT_SEC

log = logging.getLogger(__name__)


# =============================================================================
# Generic command-line arguments for PySerial serial ports
# =============================================================================

def add_serial_port_args(parser: ArgumentParser) -> None:
    group = parser.add_argument_group('serial port')
    group.add_argument(
        '--port', type=str, required=True,
        help="Serial port (e.g. Linux: /dev/ttyS0, Windows: COM1). For Linux "
             "testing, you can use 'socat [-d [-d [-d [-d]]]] "
             "pty,raw,echo=0,b9600 pty,raw,echo=0,b9600' to create a pair of "
             "linked pseudo-ports, and use the resulting /dev/pts/* devices,"
             "one for this program, and the other for the program you wish "
             "to test. For manual testing, you can replace one of the socat "
             "settings with '-' and type into it, but that only works with "
             "LF (and similar) line endings. For raw manual testing (e.g. for "
             "devices that expect commands without CR/LF endings), use socat "
             "as above and talk to the other port with e.g. 'minicom "
             "--device /dev/pts/SOMETHING'.")
    group.add_argument(
        '--baudrate', nargs='?', type=int, default=9600,
        choices=serial.SerialBase.BAUDRATES,
        help="Baud rate")
    group.add_argument(
        '--bytesize', nargs='?', type=int, default=serial.EIGHTBITS,
        choices=serial.SerialBase.BYTESIZES,
        help="Byte size")
    group.add_argument(
        '--parity', nargs='?',
        type=lambda c: c.upper(),
        default=serial.PARITY_NONE,
        choices=serial.SerialBase.PARITIES,
        help="Parity")
    group.add_argument(
        '--stopbits', nargs='?', type=float, default=serial.STOPBITS_ONE,
        choices=serial.SerialBase.STOPBITS,
        help="Stop bits")
    # group.add_argument(
    #     '--timeout', type=float, default=None,
    #     help="Read timeout (s)")
    group.add_argument(
        '--xonxoff', action='store_true',
        help="Use XON/XOFF software flow control")
    group.add_argument(
        '--rtscts', action='store_true',
        help="Use RTS/CTS hardware flow control")
    group.add_argument(
        '--rts', type=int, default=None,
        choices=[0, 1],
        help='Set initial RTS line state')
    group.add_argument(
        '--dsrdtr', action='store_true',
        help="Use DSR/DTR hardware flow control")
    group.add_argument(
        '--dtr', type=int, default=None,
        choices=[0, 1],
        help='Set initial DTR line state')
    group.add_argument(
        '--write_timeout', type=float, default=None,
        help="Write timeout (s)")
    group.add_argument(
        '--inter_byte_timeout', type=float, default=None,
        help="Inter-byte timeout (s)")


# =============================================================================
# Split by multiple delimiters
# =============================================================================
# http://stackoverflow.com/questions/1059559/python-split-strings-with-multiple-delimiters  # noqa

REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.


def escape_literal_string_for_regex(s: str) -> str:
    r"""
    Escape any regex characters.

    Start with \ -> \\
        ... this should be the first replacement in REGEX_METACHARS.
    """
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


def escape_literal_bytes_for_regex(b: bytes) -> bytes:
    for c in REGEX_METACHARS:
        cb = c.encode("ascii")
        b.replace(cb, b"\\" + cb)
    return b


def compile_literal_splitter_regex(
        separators: Sequence[Union[str, bytes]],
        flags: int = re.IGNORECASE) -> Pattern:
    if not separators:
        raise ValueError("No separators provided")
    if isinstance(separators[0], bytes):
        escaped_separators = [b'(?:' + escape_literal_bytes_for_regex(s) + b')'
                              for s in separators]
        regex_str = b'|'.join(escaped_separators)
    else:
        escaped_separators = ['(?:' + escape_literal_string_for_regex(s) + ')'
                              for s in separators]
        regex_str = '|'.join(escaped_separators)
    log.debug("separators: {}".format(repr(separators)))
    log.debug("regex_str: {}".format(repr(regex_str)))
    return re.compile(regex_str, flags)


# =============================================================================
# Class to process serial port data from the command line
# =============================================================================

class CommandLineSerialProcessor(object):
    # noinspection PyUnresolvedReferences
    def __init__(self,
                 args: Namespace,
                 inbound_eol: Optional[Union[bytes, Sequence[bytes]]] = LF,
                 inbound_bytewise: bool = False,
                 outbound_eol: bytes = LF,
                 encoding: str = 'ascii',
                 read_timeout_sec: float = READ_TIMEOUT_SEC) -> None:
        self.serial_port = serial.Serial(
            port=args.port,
            baudrate=args.baudrate,
            bytesize=args.bytesize,
            parity=args.parity,
            stopbits=args.stopbits,
            timeout=read_timeout_sec,
            xonxoff=args.xonxoff,
            rtscts=args.rtscts,
            dsrdtr=args.dsrdtr,
            write_timeout=args.write_timeout,
            inter_byte_timeout=args.inter_byte_timeout
        )
        if args.rts is not None:
            self.serial_port.rts = args.rts
        if args.dtr is not None:
            self.serial_port.dtr = args.dtr

        if isinstance(inbound_eol, str):
            self.inbound_eol = [inbound_eol]
        elif not inbound_eol:
            self.inbound_eol = []
        else:
            self.inbound_eol = inbound_eol
            if len(self.inbound_eol) > 1:
                # noinspection PyTypeChecker
                for individual_eol in self.inbound_eol:
                    if not individual_eol or len(individual_eol) == 0:
                        raise ValueError(
                            "Can't have any zero-length inbound_eol members if"
                            " some have non-zero length")
        if self.inbound_eol:
            self.inbound_eol_splitter = compile_literal_splitter_regex(
                self.inbound_eol)
        else:
            self.inbound_eol_splitter = None
        self.use_inbound_eol = inbound_eol and len(inbound_eol[0]) > 0
        self.inbound_bytewise = inbound_bytewise
        self.outbound_eol = outbound_eol
        self.encoding = encoding
        self.residual = b''

    def run(self) -> None:
        self.start()
        log.info("Starting to read from serial port")
        while True:
            data = self.serial_port.read(1)  # will wait until timeout
            # ... will return b'' if no data
            if not self.inbound_bytewise:
                data += self.serial_port.read(self.serial_port.inWaiting())
            if len(data) > 0:
                self.bytes_received(data)
            self.spontaneous()

    def start(self) -> None:
        """May be overridden."""
        pass

    def spontaneous(self) -> None:
        """May be overridden."""
        pass

    def bytes_received(self, data: bytes) -> None:
        """May be overridden."""
        log.debug("bytes_received: {}".format(repr(data)))
        if self.inbound_bytewise or not self.inbound_eol_splitter:
            self.line_received(data.decode(self.encoding))
        else:
            data = self.residual + data
            fragments = self.inbound_eol_splitter.split(data)
            lines = fragments[:-1]
            self.residual = fragments[-1]
            # log.debug("lines={}, residual={}".format(
            #     repr(lines), repr(self.residual)))
            for line in lines:
                self.line_received(line.decode(self.encoding))

    # noinspection PyMethodMayBeStatic
    def line_received(self, line: str) -> None:
        log.info("line_received: {}".format(repr(line)))

    def send_line(self, line: str) -> None:
        log.info("sending line: {}".format(repr(line)))
        data = line.encode(self.encoding) + self.outbound_eol
        self.send_bytes(data)

    def send_bytes(self, data: bytes) -> None:
        log.debug("sending data: {}".format(repr(data)))
        self.serial_port.write(data)


# =============================================================================
# Flip a coin
# =============================================================================

def coin(p: float) -> bool:
    return random.random() < p
