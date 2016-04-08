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
    **do not** close the console window (this will close the GUI app). Use the
    method

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
