#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""Bird-monitoring Whisker client.

See help for details.

Copyright (C) Rudolf Cardinal, 2015.
Last modification: 12 Jan 2015.

REFERENCES cited in code below:

[1] E-mail to Rudolf Cardinal from Søren Ellegaard, 9 Dec 2014.
[2] E-mail to Rudolf Cardinal from Søren Ellegaard, 10 Dec 2014.
[3] "RFID Reader.docx" in [1]; main reference for the RFID tag reader.
[4] "ba_ad105_e_2.pdf" in [1]; main reference for the balance.
[5] "RFID and LOAD CELL DEVICES - SE_20141209.pptx" in [1].
"""

# =============================================================================
# Dependencies
# =============================================================================

# Python Standard Library:
from __future__ import print_function
import argparse
import datetime
import dateutil.tz
import logging
LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT)
# basicConfig() call should precede loading other modules that might call it
import re
import socket

# Twisted
from twisted.internet import reactor
from twisted.internet.serialport import (
    SerialPort,
    FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS,
    PARITY_NONE, PARITY_EVEN, PARITY_ODD,
    STOPBITS_ONE, STOPBITS_TWO
)
from twisted.protocols.basic import LineReceiver


# Code for remote import, if necessary
def remote_import(name, url):
    import imp
    import urllib
    module = imp.new_module(name)
    code = urllib.urlopen(url).read()
    exec code in module.__dict__
    return module

# Import Whisker code
MODULES_FROM_REMOTE = True  # False in production
if MODULES_FROM_REMOTE:
    URL_ROOT = "http://egret.psychol.cam.ac.uk/pythonlib/"
    rnc_db = remote_import("rnc_db", URL_ROOT + "rnc_db.py")
    whisker = remote_import("whisker", URL_ROOT + "whisker.py")
else:
    import rnc_db
    import whisker

# =============================================================================
# Logger
# =============================================================================

logger = logging.getLogger("birdmonitor")
logger.setLevel(logging.DEBUG)

# =============================================================================
# Other constants
# =============================================================================

LOCALTZ = dateutil.tz.tzlocal()  # constant for a given run
ISO8601_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"  # e.g. 2013-07-24T20:04:07.000000+0100


# =============================================================================
# Support functions
# =============================================================================

def get_now():
    return datetime.datetime.now(LOCALTZ)


def indexed_or_last(array, index):
    try:
        return array[index]
    except:
        try:
            return array[-1]
        except:
            # not an array (or empty)
            return array


def indexed_or_default(array, index, default):
    try:
        return array[index]
    except:
        return default


def get_my_ip_address():
    # http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib  # noqa
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS server
        ipaddr = s.getsockname()[0]
        s.close()
        return ipaddr
    except:
        return "localhost"


# =============================================================================
# Communication with RFID tag reader
# =============================================================================

class Rfid(LineReceiver):
    # 1. LineReceiver default delimiter is '\r\n', i.e. CR + LF.
    # 2. RFID protocol uses a CR+LF delimiter [3].
    # 3. For socat debugging in interactive mode, we offer the option to use
    #    a LF delimiter (as per Unix).
    # 4. Commands/responses from [3].

    CMD_RESET_1 = "x"
    CMD_RESET_2 = "z"
    CMD_REQUEST_VERSION = "v"
    CMD_READING_CONTINUES = "c"
    CMD_LOGIN = "l"
    CMD_READ_PAGE = "r"
    CMD_WRITE_PAGE = "w"
    CMD_DENOMINATION_OF_LED = "d"
    CMD_ANTENNA_POWER_OFF = "p"

    RESPONSE_COMMAND_INVALID = "?"
    RESPONSE_COMMAND_NOT_EXECUTED = "N"
    RESPONSE_CONTINUOUS_READ_STOPPED = "S"

    def __init__(self, controller, devnumber, name,
                 debug_lf_terminator=False):
        self.controller = controller
        self.devnumber = devnumber
        self.name = name
        self.debug_lf_terminator = debug_lf_terminator
        if debug_lf_terminator:
            Rfid.delimiter = '\n'

    def connectionMade(self):
        self.reset()

    def reset(self):
        self.send(Rfid.CMD_RESET_1)
        self.send(Rfid.CMD_READING_CONTINUES)
        # *** needs testing

    def error(self, msg):
        logger.error("Error from RFID tag reader {num} ({name}): {msg}".format(
            num=self.devnumber,
            name=self.name,
            msg=msg
        ))

    def lineReceived(self, data):
        # will look like e.g. "Z5A2080A70C2C0001" [5].
        if data == Rfid.RESPONSE_COMMAND_INVALID:
            self.error("RESPONSE_COMMAND_INVALID")
        elif data == Rfid.RESPONSE_COMMAND_NOT_EXECUTED:
            self.error("RESPONSE_COMMAND_NOT_EXECUTED")
        elif data == Rfid.RESPONSE_CONTINUOUS_READ_STOPPED:
            self.error("RESPONSE_CONTINUOUS_READ_STOPPED")
        else:
            rfid = data
            self.controller.from_rfid(self, rfid)
        # *** needs testing

    def send(self, data):
        logger.debug("Sending to RFID tag reader {num} ({name}): {data}".format(
            num=self.devnumber,
            name=self.name,
            data=data))
        if self.debug_lf_terminator:
            self.sendLine(data)
        else:
            # this is for real; no CR+LF delimiter sent to the RFID [3], just
            # received from it.
            self.transport.write(data)


# =============================================================================
# Communication with weighing balance
# =============================================================================

class Balance(LineReceiver):
    # Balance uses CR+LF terminator when sending to computer [4].
    # Computer can use LF or semicolon terminator when sending to balance [4].

    def __init__(self, controller, devnumber, name,
                 debug_lf_terminator=False):
        self.controller = controller
        self.devnumber = devnumber
        self.name = name
        self.debug_lf_terminator = debug_lf_terminator
        if debug_lf_terminator:
            Balance.delimiter = '\n'

    def connectionMade(self):
        self.reset()

    def reset(self):
        # Reference is [4]
        self.send("RES")  # warm restart (p46)
        #self.send("TEX172")  # set a comma+CRLF as the data delimiter (p22)
        self.send("COF3")  # select ASCII result output (page 19)
        self.send("NOV0")  # deactivate output scaling (page 31)
        # *** set measuring time/frequency with ICR
        # *** then start measuring with MSV and stop with STP?
        # *** trap exit (e.g. Ctrl-C) and call STP?

    def lineReceived(self, data):
        # will look like e.g. "99.99 g" [5]
        try:
            m = re.match("(.*)\s+(\w+)$", data)
            mass = float(m.group(1))
            units = m.group(2)
            self.controller.from_balance(self, mass, units)
        except:
            logger.error("Unknown message from balance: {}".format(data))

    def send(self, data):
        logger.debug("Sending to balance {} ({}): {}".format(
            self.devnumber, self.name, data))
        if self.debug_lf_terminator:
            self.sendLine(data)
        else:
            # this is for real
            self.transport.write(str(data) + "\r")  # \r is LF


# =============================================================================
# WhiskerClient
# =============================================================================

class WhiskerClient(whisker.WhiskerTask):

    def __init__(self, controller, wcm_prefix):
        super(WhiskerClient, self).__init__()  # call base class init
        self.controller = controller
        self.wcm_prefix = wcm_prefix

    def fully_connected(self):
        self.command("ReportName WhiskerBirdMonitor")
        self.command("ReportStatus running")

    def broadcast(self, msg):
        self.command("SendToClient -1 {} {}".format(self.wcm_prefix, msg))
        # use client number -1 to broadcast to all other clients

    def rfid_event(self, device, rfid):
        self.broadcast("RFID {device} {rfid}".format(
            device=device.name,
            rfid=rfid))

    def balance_event(self, device, mass, units):
        self.broadcast("balance {device} {mass} {units}".format(
            device=device.name,
            mass=mass,
            units=units))


# =============================================================================
# Database interface
# =============================================================================

class Database(object):
    RFID_TABLENAME = "rfid"
    RFID_FIELDS = [
        "ipaddr", "when_dt", "when_utc", "device_number", "device_name", "rfid"
    ]
    BALANCE_TABLENAME = "balance"
    BALANCE_FIELDS = [
        "ipaddr", "when_dt", "when_utc", "device_number", "device_name",
        "mass", "units"
    ]

    def __init__(self, controller, odbc_dsn):
        self.controller = controller
        self.odbc_dsn = odbc_dsn
        self.ipaddr = get_my_ip_address()
        self.db = rnc_db.DatabaseSupporter()
        if not self.db.connect_to_database_odbc_access(odbc_dsn):
            raise Exception("Unable to open database")
        self.ensure_table_and_columns(Database.RFID_TABLENAME,
                                      Database.RFID_FIELDS)
        self.ensure_table_and_columns(Database.BALANCE_TABLENAME,
                                      Database.BALANCE_FIELDS)

    def ensure_table_and_columns(self, table, columns):
        self.ensure_table(table)
        for c in columns:
            self.ensure_column(table, c)

    def ensure_table(self, table):
        if not self.db.table_exists(table):
            raise Exception("Database {} doesn't have table {}".format(
                self.odbc_dsn, table))

    def ensure_column(self, table, column):
        if not self.db.column_exists(table, column):
            raise Exception("Database {} doesn't have column {}.{}".format(
                self.odbc_dsn, table, column))

    def rfid_event(self, device, rfid, now):
        nowstr = now.strftime(ISO8601_FMT)
        logger.debug("TO DATABASE / rfid: {num}, {name}, {rfid}, {now}".format(
            num=device.devnumber,
            name=device.name,
            rfid=rfid,
            now=nowstr))
        self.db.insert_record(
            Database.RFID_TABLENAME,
            Database.RFID_FIELDS,
            [self.ipaddr, now, nowstr, device.devnumber, device.name, rfid]
        )

    def balance_event(self, device, mass, units, now):
        nowstr = now.strftime(ISO8601_FMT)
        logger.debug(
            "TO DATABASE / balance: {num}, {name}, {mass}, "
            "{units}, {now}".format(
                num=device.devnumber,
                name=device.name,
                mass=mass,
                units=units,
                now=nowstr))
        self.db.insert_record(
            Database.BALANCE_TABLENAME,
            Database.BALANCE_FIELDS,
            [self.ipaddr, now, nowstr, device.devnumber, device.name,
             mass, units]
        )


# =============================================================================
# Controller, the main controlling class
# =============================================================================

class Controller(object):

    def __init__(self, args, reactor):
        self.args = args
        self.reactor = reactor
        # We communicate via the following things:
        self.whiskerclient = None
        self.rfid = []
        self.balance = []
        self.database = None

        for i in range(len(args.rfid_serialdev)):
            name = indexed_or_default(args.rfid_name, i, str(i))
            rfid = Rfid(self, i, name, args.rfid_debug_lf_terminator)
            dev = args.rfid_serialdev[i]
            baud = indexed_or_last(args.rfid_baudrate, i)
            b = indexed_or_last(args.rfid_bytesize, i)
            p = indexed_or_last(args.rfid_parity, i)
            s = indexed_or_last(args.rfid_stopbits, i)
            x = indexed_or_last(args.rfid_xonxoff, i)
            r = indexed_or_last(args.rfid_rtscts, i)
            logger.info(
                "RFID tag reader {i} ('{name}'): "
                "starting serial comms on device {dev} "
                "({baud} bps, {b}{p}{s}, XON/XOFF {x}, RTS/CTS {r})".format(
                    i=i,
                    name=name,
                    dev=dev,
                    baud=baud,
                    b=b,
                    p=p,
                    s=s,
                    x="enabled" if x else "disabled",
                    r="enabled" if r else "disabled"))
            SerialPort(protocol=rfid,
                       deviceNameOrPortNumber=dev,
                       reactor=reactor,
                       baudrate=baud,
                       bytesize=b,
                       parity=p,
                       stopbits=s,
                       xonxoff=x,
                       rtscts=r)
            self.rfid.append(rfid)

        for i in range(len(args.balance_serialdev)):
            name = indexed_or_default(args.balance_name, i, str(i))
            balance = Balance(self, i, name, args.balance_debug_lf_terminator)
            dev = args.balance_serialdev[i]
            baud = indexed_or_last(args.balance_baudrate, i)
            b = indexed_or_last(args.balance_bytesize, i)
            p = indexed_or_last(args.balance_parity, i)
            s = indexed_or_last(args.balance_stopbits, i)
            x = indexed_or_last(args.balance_xonxoff, i)
            r = indexed_or_last(args.balance_rtscts, i)
            logger.info(
                "Balance {i} ('{name}'): "
                "starting serial comms on device {dev} "
                "({baud} bps, {b}{p}{s}, XON/XOFF {x}, RTS/CTS {r})".format(
                    i=i,
                    name=name,
                    dev=dev,
                    baud=baud,
                    b=b,
                    p=p,
                    s=s,
                    x="enabled" if x else "disabled",
                    r="enabled" if r else "disabled"))
            SerialPort(protocol=balance,
                       deviceNameOrPortNumber=dev,
                       reactor=reactor,
                       baudrate=baud,
                       bytesize=b,
                       parity=p,
                       stopbits=s,
                       xonxoff=x,
                       rtscts=r)
            self.balance.append(balance)

        if len(self.rfid) + len(self.balance) == 0:
            raise Exception("No input devices specified. Use --help for help.")

        logger.info("Using {} balance(s) and {} RFID tag reader(s)".format(
            len(self.balance),
            len(self.rfid),
        ))

        if args.odbc_dsn:
            logger.info("Opening database")
            self.database = Database(self, args.odbc_dsn)
        else:
            logger.info("No database specified")

        if args.server:
            logger.info("Starting Whisker client; connecting to {}:{}".format(
                args.server, args.port))
            self.whiskerclient = WhiskerClient(self, args.wcm_prefix)
            self.whiskerclient.set_verbose_logging(args.debug_whisker)
            self.whiskerclient.connect(args.server, args.port)
        else:
            logger.info("No Whisker server specified")

    def no_op(self):
        pass

    def from_rfid(self, device, rfid):
        now = get_now()
        logger.info("Received from RFID {num} ({name}): {rfid} [{now}]".format(
            num=device.devnumber,
            name=device.name,
            rfid=rfid,
            now=now))
        if self.whiskerclient:
            self.whiskerclient.rfid_event(device, rfid)
        if self.database:
            self.database.rfid_event(device, rfid, now)

    def from_balance(self, device, mass, units):
        now = get_now()
        logger.info(
            "Received from balance {num} ({name}): {mass} {units} "
            "[{now}]".format(
                num=device.devnumber,
                name=device.name,
                mass=mass,
                units=units,
                now=now))
        if self.whiskerclient:
            self.whiskerclient.balance_event(device, mass, units)
        if self.database:
            self.database.balance_event(device, mass, units, now)


# =============================================================================
# Main
# =============================================================================

def main():
    # Fetch command-line options.
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=r"""
Whisker bird monitor (reading from RFID tag reader and weighing balance).
INPUT is from:
    * zero or more serial-port RFID tag readers
    * zero or more serial-port balances
OUTPUT is to:
    * the console
    * +/- Whisker (client broadcast messages), via TCP/IP
    * +/- a database, via ODBC
    * +/- a log file

1. You can specify a list of RFID tag readers, and a list of balances.

 * Use the --rfid_serialdev and --balance_serialdev to specify their devices.
 * Each can have a name; pass corresponding lists to the --rfid_name and
   --balance_name options.
 * Similarly, each device can have its serial port settings configured
   independently. If you specify fewer serial port options than there are
   corresponding devices, the last-specified option is used for all subsequent
   devices.

2. You can specify a database via an Open Database Connectivity (ODBC) data
   source name (DSN). The program will expect the following tables and fields:

   {rt}
     {rc}
   {bt}
     {bc}

3. To split long command lines, remember the end-of-line backslash (\, Unix)
   or caret (^, Windows).""".format(
        rt=Database.RFID_TABLENAME,
        rc=", ".join(Database.RFID_FIELDS),
        bt=Database.BALANCE_TABLENAME,
        bc=", ".join(Database.BALANCE_FIELDS),
    ))

    parser.add_argument(
        "--server", type=str,
        help="Whisker server to use (specify 'localhost' for this machine)")
    parser.add_argument(
        "--port", type=int, default=3233,
        help="TCP port for Whisker server (default: %(default)s)")
    parser.add_argument(
        "--wcm_prefix", type=str, default="birdmonitor",
        help="Prefix for Whisker client message (default: %(default)s)")

    parser.add_argument(
        "--odbc_dsn", type=str,
        help="ODBC DSN for database to use.")

    parser.add_argument(
        "--rfid_serialdev", type=str, nargs="*", default=[],
        help="Device(s) to talk to RFID tag reader "
             "(e.g. Linux /dev/XXX; Windows COM4)")
    parser.add_argument(
        "--rfid_name", type=str, nargs="*",
        help="Name to assign to each device (default: 0-based device number)")
    # The RFID devices are fixed at 9600 bps, 8N1 [3]
    parser.add_argument(
        "--rfid_baudrate", type=int,  nargs="*", default=9600,
        help="RFID tag reader: baud rate (default: %(default)s)")
    parser.add_argument(
        "--rfid_bytesize", type=int,  nargs="*",
        choices=[FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS], default=EIGHTBITS,
        help="RFID tag reader: number of bits (default: %(default)s)")
    parser.add_argument(
        "--rfid_parity", type=str,  nargs="*",
        choices=[PARITY_NONE, PARITY_EVEN, PARITY_ODD], default=PARITY_NONE,
        help="RFID tag reader: parity (default: %(default)s)")
    parser.add_argument(
        "--rfid_stopbits", type=int,  nargs="*",
        choices=[STOPBITS_ONE, STOPBITS_TWO], default=STOPBITS_ONE,
        help="RFID tag reader: stop bits (default: %(default)s)")
    parser.add_argument(
        "--rfid_xonxoff", type=int,  nargs="*", choices=[0, 1], default=0,
        help="RFID tag reader: use XON/XOFF (default: %(default)s)")
    parser.add_argument(
        "--rfid_rtscts", type=int, nargs="*", choices=[0, 1], default=0,
        help="RFID tag reader: use RTS/CTS (default: %(default)s)")
    parser.add_argument(
        "--rfid_debug_lf_terminator", action="store_true",
        help="RFID tag reader: use LF (not CR+LF) terminator "
             "(for socat debugging only)")

    parser.add_argument(
        "--balance_serialdev", type=str, nargs="*", default=[],
        help="Device(s) to talk to weighing balance "
             "(e.g. Linux /dev/YYY; Windows COM5)")
    parser.add_argument(
        "--balance_name", type=str, nargs="*",
        help="Name to assign to each device (default: 0-based device number)")
    parser.add_argument(
        "--balance_baudrate", type=int,  nargs="*", default=19200,
        help="Balance: baud rate (default: %(default)s)")
    parser.add_argument(
        "--balance_bytesize", type=int,  nargs="*",
        choices=[FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS], default=EIGHTBITS,
        help="Balance: number of bits (default: %(default)s)")
    parser.add_argument(
        "--balance_parity", type=str,  nargs="*",
        choices=[PARITY_NONE, PARITY_EVEN, PARITY_ODD], default=PARITY_NONE,
        help="Balance: parity (default: %(default)s)")
    parser.add_argument(
        "--balance_stopbits", type=int,  nargs="*",
        choices=[STOPBITS_ONE, STOPBITS_TWO], default=STOPBITS_ONE,
        help="Balance: stop bits (default: %(default)s)")
    parser.add_argument(
        "--balance_xonxoff", type=int,  nargs="*", choices=[0, 1], default=0,
        help="Balance: use XON/XOFF (default: %(default)s)")
    parser.add_argument(
        "--balance_rtscts", type=int,  nargs="*", choices=[0, 1], default=0,
        help="Balance: use RTS/CTS (default: %(default)s)")
    parser.add_argument(
        "--balance_debug_lf_terminator", action="store_true",
        help="Balance: use LF (not CR+LF) terminator "
             "(for socat debugging only)")

    parser.add_argument(
        "--debug_whisker", action="store_true",
        help="Verbose debugging messages for Whisker")
    parser.add_argument(
        "--debug_birdmonitor", action="store_true",
        help="Verbose debugging messages for bird monitor")
    parser.add_argument(
        "--logfile", default=None,
        help="Filename to append log to")

    args = parser.parse_args()

    if args.debug_birdmonitor:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    logger.info("Starting; local IP address is {}".format(get_my_ip_address()))

    if args.logfile:
        fh = logging.FileHandler(args.logfile)
        # default file mode is 'a' for append
        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
        fh.setFormatter(formatter)
        # Send everything to this handler:
        for name, obj in logging.Logger.manager.loggerDict.iteritems():
            obj.addHandler(fh)

    logger.debug("Arguments: {}".format(repr(args)))

    controller = Controller(args, reactor)
    controller.no_op()  # removes a lint warning
    reactor.run()


# =============================================================================
# Entry point
# =============================================================================

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.exception(e)
        raise


TESTING = """

# sudo apt-get install socat

# Make two virtual serial ports and establish interactive communication with
# them. Make a note of the /dev/pts/N numbers.
socat -d -d - pty,raw,echo=0
socat -d -d - pty,raw,echo=0

./bird_monitor.py \
    --rfid_serialdev=/dev/pts/13 \
    --rfid_name=first_rfid \
    --rfid_debug_lf_terminator \
    --balance_serialdev=/dev/pts/0 \
    --balance_name=first_balance \
    --balance_debug_lf_terminator \
    --debug_birdmonitor \
    --logfile=birdlog.txt \
    --server=wombatvmxp

"""

TO_DO = """
    - test database connection
    - code the RFID interface (needs test kit)
    - code the balance interface (needs test kit)
        - may also need a frequency parameter
    - Windows distribution
"""
