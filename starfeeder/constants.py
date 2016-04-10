#!/usr/bin/env python
# starfeeder/constants.py

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
"""

from enum import Enum
import os
import sys
from starfeeder.version import VERSION


ABOUT = """
<b>Starfeeder {VERSION}</b><br>
<br>
Whisker bird monitor.<br>
<br>
Functions:
<ul>
  <li>
    Talks to
    <ul>
      <li>multiple radiofrequency identification (RFID) readers</li>
      <li>multiple weighing balances</li>
      <li>one Whisker server (<a href="{WHISKER_URL}">{WHISKER_URL}</a>)</li>
    </ul>
  </li>
  <li>Detects the mass of subjects identified by their RFID (having configured
    RFID readers/balances into pairs)</li>
  <li>Tells the Whisker server, and its other clients, about RFID and mass
    events.</li>
  <li>Stores its data to a database (e.g. SQLite; MySQL).</li>
</ul>

Hardware supported:
<ul>
  <li>RFID readers: MBRose BW-1/001 integrated load cell scale RFID reader</li>
  <li>Balances: HBM AD105 digital transducer with RS-485 interface</li>
  <li>RFID readers and balances connect to a USB controller (MBRose WS-2/001
    RS232-to-USB interface), which connects to the computer's USB port.</li>
</ul>

You will also need:
<ul>
  <li>A database. Any backend supported by SQLAlchemy will do (see
    <a href="{BACKEND_URL}">{BACKEND_URL}</a>).
    SQLite is quick. Starfeeder finds its database using the environment
    variable STARFEEDER_DATABASE_URL.</li>
  <li>You may want a graphical tool for database management. There are lots.
    For SQLite, consider Sqliteman
    (<a href="{SQLITEMAN_URL}">{SQLITEMAN_URL}</a>).
</ul>

By Rudolf Cardinal (rudolf@pobox.com).<br>
Copyright &copy; 2015 Rudolf Cardinal.
For licensing details see LICENSE.txt.<br>
External libraries used include Alembic; bitstring; PyInstaller; PySerial;
Qt (via PySide); SQLAlchemy.
""".format(
    VERSION=VERSION,
    WHISKER_URL="http://www.whiskercontrol.com/",
    SQLITEMAN_URL="http://sqliteman.yarpen.cz/",
    BACKEND_URL="http://docs.sqlalchemy.org/en/latest/core/engines.html",
)
BALANCE_ASF_MINIMUM = 0  # p37 of balance manual
BALANCE_ASF_MAXIMUM = 8  # p37 of balance manual
DB_URL_ENV_VAR = "STARFEEDER_DATABASE_URL"
DATABASE_ENV_VAR_NOT_SPECIFIED = """
===============================================================================
You must specify the {var} environment variable (which is an
SQLAlchemy database URL). Examples follow.

Windows:
    set {var}=sqlite:///C:\\path\\to\\database.sqlite3
Linux:
    export {var}=sqlite:////absolute/path/to/database.sqlite3
===============================================================================
""".format(var=DB_URL_ENV_VAR)
GUI_MASS_FORMAT = '% 9.6f'
GUI_TIME_FORMAT = '%H:%M:%S'
LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
WINDOW_TITLE = 'Starfeeder: RFID/balance controller for Whisker'
WRONG_DATABASE_VERSION_STUB = """
===============================================================================
Database revision should be {head_revision} but is {current_revision}.

- If the database version is too low, run starfeeder with the
  "--upgrade-database" parameter (because your database is too old), or click
  the "Upgrade database" button in the GUI.

- If the database version is too high, upgrade starfeeder (because you're
  trying to use an old starfeeder version with a newer database).
===============================================================================
"""

# =============================================================================
# Find out where Alembic and other files live
# =============================================================================

if getattr(sys, 'frozen', False):
    # Running inside a PyInstaller bundle.
    # http://pythonhosted.org/PyInstaller/#run-time-operation
    # noinspection PyProtectedMember,PyUnresolvedReferences
    CURRENT_DIR = sys._MEIPASS
else:
    # Running in a normal Python environment.
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

ALEMBIC_CONFIG_FILENAME = os.path.join(CURRENT_DIR, 'alembic.ini')
ALEMBIC_BASE_DIR = CURRENT_DIR
MANUAL_FILENAME = os.path.join(CURRENT_DIR, 'manual.pdf')


# =============================================================================
# Thread state enum
# =============================================================================

class ThreadOwnerState(Enum):
    stopped = 0
    starting = 1
    running = 2
    stopping = 3
