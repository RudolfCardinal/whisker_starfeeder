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
HELP = """
<b>Troubleshooting</b><br>
On Windows:
<ul>
  <li>Download and install PuTTY (<a href="{putty_url}">{putty_url}</a>); this
    is a good terminal emulator (as well as an SSH client).</li>
  <li>
    For the RFID readers:
    <ul>
      <li>Connect to the correct COM port using the settings 9600, 8N1,
        XON/XOFF (do not use RTS/CTS under Windows).</li>
      <li>Use the keystrokes <b>x</b> for status (it should say
        "MULTITAG-125 01"), <b>c</b> to start reading (it'll say nothing at
        first, then spit out RFID codes when a tag is waved next to the
        antenna), and <b>p</b> to stop reading (it'll say "S").
        Note that the commands are case-sensitive and single-character only
        (do not send a newline or you will cancel ongoing reads).</li>
      <li>If it doesn't understand something, it will say "?".</li>
    </ul>
  </li>
  <li>
    For the balance:
    <ul>
      <li>Connect to the correct COM port using the settings 9600, 8<b>E</b>1,
        XON/XOFF.</li>
      <li>The balance is particularly frustrating, as it usually doesn't say
        anything if you get the syntax wrong. Occasionally it says "?".</li>
      <li>Type <b>RES;</b> to restart. There will be no reply.</li>
      <li>Type <b>ESR?;</b> to request status. It should say "000".</li>
      <li>Type <b>COF3;</b> to request ASCII output. It should say "0".</li>
      <li>Type <b>MSV?10;</b> to request 10 readings. Data should come.</li>
    </ul>
  </li>
</ul>
""".format(
    putty_url="http://www.chiark.greenend.org.uk/~sgtatham/putty/"
)
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


class ThreadOwnerState(Enum):
    stopped = 0
    starting = 1
    running = 2
    stopping = 3
