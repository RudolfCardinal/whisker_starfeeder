.. |copy|   unicode:: U+000A9 .. COPYRIGHT SIGN

==========================
Whisker Starfeeder: README
==========================

Purpose
~~~~~~~

Manages radiofrequency identification (RFID) readers and weighing balances,
and talks to a Whisker client (http://www.whiskercontrol.com/).

Author/licensing
~~~~~~~~~~~~~~~~

By Rudolf Cardinal.
Copyright |copy| 2015 Rudolf Cardinal.
See LICENSE.txt.

Single-folder binary distribution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unzip the distributed file and double-click the ``starfeeder`` program.
That's it.

Linux source installation
~~~~~~~~~~~~~~~~~~~~~~~~~

*End users should opt for the single-folder binary distribution instead.*

Install
-------

From a command prompt:

.. code-block::

    sudo apt-get install python3 python3-pip  # install Python with pip
    python3 -m virtualenv /PATH/TO/MY/NEW/VIRTUALENV  # make a virtualenv
    source /PATH/TO/MY/NEW/VIRTUALENV/bin/activate  # activate the virtualenv

    # pip install starfeeder --process-dependency-links  # install from PyPI -- NOT YET IMPLEMENTED

    cd /MY/WORKING/DIR
    git clone https://egret.psychol.cam.ac.uk/git/starfeeder  # Fetch code. Private for now.
    pip install -e .  # Install from working directory into virtualenv.

Run
---

.. code-block::

    /PATH/TO/MY/NEW/VIRTUALENV/bin/starfeeder


Windows source installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Deprecated, as it's complex.*

Install
-------

1.  You need to have Python 3 installed (which will come with ``pip``,
    ``pyvenv``, and sometimes ``virtualenv``).
    Obtain it from https://www.python.org/ and install it. We'll suppose you've
    installed Python at ``C:\Python34``.

2.  On Windows 10, install a copy of ``cmake``, because PySide wants it.
    Also Qt. Also Git if you want to work with repositories directly.
    Possibly other things.
    (I have this working on Windows XP but not Windows 10; PySide is not
    building itself happily.)

3.  Then fire up a Command Prompt and do:

    .. code-block::

        C:\Python34\Tools\Scripts\pyvenv.py C:\PATH\TO\MY\NEW\VIRTUALENV

        C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\activate

        pip install starfeeder --process-dependency-links


Run
---

Run the ``starfeeder`` program from within your virtual environment.

*Windows: just the GUI*

    For normal use:

    .. code-block::

        C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\pythonw.exe C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\starfeeder-script.py

*Windows: to see command-line output*

    Use this for database upgrades, command-line help, and to see debugging output:

    .. code-block::

        C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\starfeeder

    You can append ``-v`` for more verbose output, or ``--help``
    for full details.

    If you use this method to run the graphical user interface (GUI) application,
    **do not** close the console window (this will close the GUI app).

Changelog
~~~~~~~~~

v0.1.2 (2015-12-23)

-   Initial release.
-   Hardware tested via Windows XP, Windows 10, and Ubuntu 14.04.

v0.1.3 (2015-12-26)

-   Ugly ``moveToThread()`` hack fixed by declaring ``QTimer(self)``
    rather than ``QTimer()``.
-   More general updates to declare parents of ``QObject`` objects, except
    in GUI code where it just clutters things up needlessly.
    Note that ``QLayout.addWidget()``, ``QLayout.addLayout()``,
    and ``QWidget.setLayout()`` all take ownership.
-   Bugfix related to using lambdas as slots (PySide causes a segmentation
    fault on exit; https://bugreports.qt.io/browse/PYSIDE-88).
-   Launch PDF manual as help.
-   Retested with hardware on Windows XP and Linux.

v0.1.4 (2015-12-26)

-   callback_id set by GUI, not by derived classes of SerialOwner

v0.1.5 (2016-02-27)

-   bugfix to BaseWindow.on_rfid_state()

v0.2.0 (2016-04-07)

-   GUI log window, for PyInstaller environments.
-   Uses Whisker Python library.
-   Switch to Arrow datetimes internally.
-   Bugfix in error handling when trying to open non-existent serial ports.

v0.2.3 (2016-04-19)
v0.2.4 (2016-04-19)

-   Bugfix.

v0.2.5

-   Internal changes only?

v0.2.6 (2016-11-24)

-   Python type hints.
-   NOTE that to install Python 3.4 (required for this version of PySide) under
    Ubuntu 16.10, you need to:
    - download Python 3.4.4 source, then:

    .. code-block::

        $ tar xvf Python-3.4.4.tgz
        $ cd Python-3.4.4
        $ configure --enable-shared
        $ make
        $ sudo make install

            # now unbreak wrong symlink and replace with old:
        $ sudo rm /usr/bin/python3  # "make install" made this point to python3.4
        $ sudo ln -s /usr/bin/python3.5 /usr/bin/python3

            # now set up library links
        $ sudo ln -s /usr/local/lib/libpython3.4m.so.1.0 /usr/lib/x86_64-linux-gnu/libpython3.4m.so.1.0

            # this should now work:
        $ python3.4

-   Upgraded from pyserial 3.0.1 to 3.2.1
    ... also allows the use of Linux pseudoterminals for testing;
        http://stackoverflow.com/questions/34831131
-   Passwords obscured in debug-level database URLs.
-   Top-level exception tracebacks go to log (like all others), not to print()
    using traceback.print_exc().
-   BalanceController could send 'ICRNone', which is wrong; the frequency 10 Hz
    was offered in the dialogue, but should have been 12. Validity check added.
-   Bug workaround:
    PROBLEM
    -   sometimes, ``WeightWhiskerTask.on_mass()`` received something that was
        not a ``MassEvent``. Not sure why (it doesn't look like anything else
        is ever sent); could this be a PySide signals bug?
    ATTEMPT 1
    -   Workaround is to verify type on receipt (and complain loudly if wrong
        but ignore/continue).
    ... no; irremediable bug in PySide (see development notes); it fails to
        keep references to signal parameters, so sometimes they go AWOL.
    ATTEMPT 2
    -   Switched from PySide to PyQt5, and thus GPLv3 licensing.
    -   Generally, this seems much better.
    -   Even then, apparent corruption in "bytes" object passed from
        SerialController.process_data()
        -> SerialController.line_received
        -> [change thread]
        -> RfidController.on_receive
        Sometimes the received bytes object is b'', not what was sent.
        PyQt does some sort of autoconversion to C++ objects; see
            http://pyqt.sourceforge.net/Docs/PyQt5/signals_slots.html
        and the problem appears to go away by using an encapsulating Python
        object... Not ideal!
        Does it also affect str? No, str seems OK.
        BUG REPRODUCED RELIABLY in pyqt5_signal_with_bytes.py.
        Reported to PyQt mailing list on 2016-12-01.
        SO FOR NOW: AVOID bytes OBJECTS IN PyQt5 SIGNALS.
