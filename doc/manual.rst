##########
Starfeeder
##########

.. include:: ../README.rst

============
Installation
============

To install, you just unzip it and run the ``starfeeder.exe`` executable.

==============
Database setup
==============

When you first run Starfeeder you might see this:

.. image:: screenshots/database_url_not_specified.png

Before it'll work you'll also need to set an environment variable to point to a
database. The simplest would be to use SQLite (https://www.sqlite.org/),
like this:

.. code-block::

    set STARFEEDER_DATABASE_URL=sqlite:///C:\path\to\starfeeder_database.sqlite3

... and then run Sqliteman (http://sqliteman.yarpen.cz/) to inspect the
database. But the software supports other databases (e.g. MySQL, others:
http://docs.sqlalchemy.org/en/latest/core/engines.html) via this URL scheme.
The configuration and data are stored in this database.

If the database isn't structured correctly, as it won't be if you've just
invented the URL (so a blank database is autocreated), the first time you run
it you get a button to "Upgrade database" (then close and re-run).

.. image:: screenshots/database_wrong_revision.png

Here's the happy starting screen:

.. image:: screenshots/start_screen.png

=============
Configuration
=============

Configure like this:

.. image:: screenshots/configure_main.png

.. image:: screenshots/configure_rfid.png

*I am not completely sure if the RFID reader supports any flow control. Under
Linux, XON/XOFF and RTS/CTS don't break it (but that doesn't mean it uses them).
Under Windows, RTS/CTS breaks it. The physical serial interface inside it is
RS-485, which is two-wire and therefore not only can't have RTS/CTS but is
unidirectional. I don't know if the USB interface adds anything; I suspect not.
So the best option is either XON/XOFF or None -- probably None.*

.. image:: screenshots/configure_balance.png

*The balance says (p15 of its manual) that it copes with XON/XOFF.*

When you click "Start..." it starts the RFID readers, balances, and connects to
Whisker.

=======================
Data storage and output
=======================

All data goes to the database (as well as to Whisker if connected).

The balance won't produce numbers until it's tared and calibrated. The default
is for an 0.1kg calibration mass, so you just start; click the Tare/calibrate
button; then remove all mass and click "Tare", then put the 0.1kg mass on and
click "Calibrate 0.1kg". It'll store the readings so you don't necessarily have
to recalibrate next time.

.. image:: screenshots/calibrate_balance.png

When it's running and things are happening, it looks like this:

.. image:: screenshots/running.png

Here are some examples of the output, as seen by Sqliteman:

.. image:: screenshots/sqliteman_rfid_event.png

.. image:: screenshots/sqliteman_mass_event.png

... and by Whisker:

.. image:: screenshots/whisker_event_log.png

========================
Operating systems tested
========================

- Linux (Ubuntu 14.04)
- Windows XP
- Windows 10

===============
Troubleshooting
===============

On Windows:

-   Download and install PuTTY
    (http://www.chiark.greenend.org.uk/~sgtatham/putty/); this is a good
    terminal emulator (as well as an excellent SSH client).

On Linux:

-   Lots of ways. But using PySerial (as Starfeeder does):

.. code-block::

    pip install https://github.com/pyserial/pyserial/tarball/3e02f7052747521a21723a618dccf303065da732  # install PySerial 3.0b1

    python -m serial.tools.miniterm /dev/ttyUSB0 9600 --eol LF --develop --parity N  # RFID reader

    python -m serial.tools.miniterm /dev/ttyUSB1 9600 --eol LF --develop --parity E  # Balance

Regardless of operating system:

-   For the RFID readers:

    -   Connect to the correct COM port using the settings 9600, 8N1,
        XON/XOFF (do not use RTS/CTS under Windows).
    -   A few key commands are shown below.
    -   Note that the commands are case-sensitive and single-character only
        (do not send a newline or you will cancel ongoing reads).
    -   If it doesn't understand something, it will say "?".

=============   ========    =================================================
Action          You type    Reply
=============   ========    =================================================
Reset           ``x``       ``MULTITAG-125 01``
Start reading   ``c``       nothing, then RFID tag codes as they are detected
Stop reading    ``p``       ``S``
=============   ========    =================================================

-   For the balance:

    -   Connect to the correct COM port using the settings 9600, **8E1**,
        XON/XOFF.
    -   The balance is particularly frustrating, as it usually doesn't say
        anything if you get the syntax wrong. Occasionally it says ``?``.
    -   Specimen commands are shown below.

====================    ===========     =======
Action                  You type        Reply
====================    ===========     =======
Restart                 ``RES;``        nothing
Request status          ``ESR?;``       ``000``
Request ASCII output    ``COF3;``       ``0``
Request 10 readings     ``MSV?10;``     data
====================    ===========     =======
