#!/usr/bin/python2.7

"""
whisker_python_demo.py

Created: 7 Feb 2010
Last amended: 7 Apr 2015

"""

from __future__ import print_function
import argparse
import csv
import getpass
import logging
import twisted.internet

import rnc_db
import whisker  # read in whisker.py from current directory or PYTHONPATH

LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT)
logger = logging.getLogger("whisker_python_demo")
logger.setLevel(logging.DEBUG)


# =============================================================================
# Whisker client class
# =============================================================================

class DemoWhiskerTask(whisker.WhiskerTask):

    def __init__(self, ):
        super(DemoWhiskerTask, self).__init__()  # call base class init
        # ... anything extra here

    def fully_connected(self):
        logger.info("SENDING SOME TEST/DEMONSTRATION COMMANDS")
        self.command("Timestamps on")
        self.command("ReportName Whisker python demo program")
        self.send("ReportStatus Absolutely fine.")
        self.send("WhiskerStatus")
        self.send("TestNetworkLatency")
        self.command("TimerSetEvent 1000 9 TimerFired")
        self.command("TimerSetEvent 12000 0 EndOfTask")

    def incoming_event(self, event, timestamp=None):
        logger.info("Event: {e} (timestamp {t})".format(e=event, t=timestamp))
        if event == "EndOfTask":
            twisted.internet.reactor.stop()


# =============================================================================
# Main program
# =============================================================================

# Fetch command-line options.
parser = argparse.ArgumentParser(description="Whisker test client")
# Output
parser.add_argument("resultfilename", nargs="?", default="whiskertemp.txt",
                    help="Text results file")
# Whisker connection
parser.add_argument("-s", "--server", type=str, default="localhost",
                    help="connect to Whisker server (default: %(default)s)")
parser.add_argument("-p", "--port", type=int, default="3233",
                    help="TCP/IP port (default: %(default)s)")
parser.add_argument("-v", "--verbosenetwork", action="store_true",
                    default=True,
                    help="show verbose network messages")
parser.add_argument("-q", "--quietnetwork", action="store_false",
                    dest="verbosenetwork",
                    help="suppress network messages")
# Database
parser.add_argument("--dbengine", type=str, default="mysql",
                    help="database engine (default: %(default)s)")
parser.add_argument("--dbinterface", type=str, default="mysqldb",
                    help="database interface (default: %(default)s)")
parser.add_argument("--dbhost", type=str, default="127.0.0.1",
                    help="database host (default: %(default)s)")
parser.add_argument("--dbport", type=int, default=3306,
                    help="database port (default: %(default)s)")
parser.add_argument("--dbdatabase", type=str, default="demo_whisker_junk",
                    help="database name (default: %(default)s)")
parser.add_argument("--dbuser", type=str, default="root",
                    help="database user (default: %(default)s)")
parser.add_argument("--dbpassword", action="store_true",
                    help="ask for database password")
parser.add_argument("--dbdsn", type=str,
                    help="database DSN")
parser.add_argument("--odbc_connection_string", type=str,
                    help="database ODBC connection string")
parser.add_argument("--dbautocommit", type=bool, default=True,
                    help="database: autocommit?")
parser.add_argument("-d", "--verbosedatabase", action="store_true",
                    help="show verbose database messages")
parser.add_argument("-x", "--quietdatabase", action="store_false",
                    dest="verbosedatabase",
                    help="suppress database messages")
args = parser.parse_args()

logger.info("Whisker demo in Python")
logger.info("----------------------")

logger.debug("Arguments: {}".format(args))
password = None
if args.dbpassword:
    password = getpass.getpass("Database password: ")

# Open log file.
logger.info("--- Let's open a log file.")
logfile = open(args.resultfilename, "w")

# Open database connection.
logger.info("--- Let's open a database connection.")
rnc_db.set_verbose_logging(args.verbosedatabase)
db = rnc_db.DatabaseSupporter()
db.connect(
    engine=args.dbengine,
    interface=args.dbinterface,
    host=args.dbhost,
    port=args.dbport,
    database=args.dbdatabase,
    dsn=args.dbdsn,
    odbc_connection_string=args.odbc_connection_string,
    user=args.dbuser,
    password=password,
    autocommit=args.dbautocommit  # if False, need to commit manually
)

logger.info("--- Let's connect to Whisker.")
w = DemoWhiskerTask()
w.set_verbose_logging(args.verbosenetwork)
w.connect(args.server, args.port)
twisted.internet.reactor.run()

# Create some sample data.
table = "table1"
fieldspecs = [
    dict(name="field1", sqltype="VARCHAR(10)"),
    dict(name="field2", sqltype="VARCHAR(10)"),
    dict(name="field3", sqltype="VARCHAR(10)"),
]
fields = [x["name"] for x in fieldspecs]
values = [
    ["data1", "data2", "data3"],
    ["data4", "data5", "data6"],
    ["data7", "data8", "data9"],
]
db.make_table(table, fieldspecs)

# Write data to disk/database.
# Do these separately, disk first, in case there are database problems.
logger.info("--- Let's write to the log file.")
writer = csv.writer(logfile)
writer.writerows([fields] + values)

logger.info("--- Let's write to the database.")
db.insert_multiple_records(table, fields, values)
db.commit()

logger.info("----------------")
logger.info("Finished.")
