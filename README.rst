==================
Whisker Starfeeder
==================

Purpose
=======

Manages radiofrequency identification (RFID) readers and weighing balances,
and talks to a Whisker client (http://www.whiskercontrol.com/).

Single-folder binary distribution
=================================

Unzip the distributed file and double-click the :code:`starfeeder` program.
That's it.

Linux source installation
=========================

Install
-------

From a command prompt:

.. code-block::

    sudo apt-get install python3 python3-pip  # install Python with pip

    python3 -m virtualenv /PATH/TO/MY/NEW/VIRTUALENV  # make a virtualenv

    source /PATH/TO/MY/NEW/VIRTUALENV/bin/activate  # activate the virtualenv

    pip install starfeeder --process-dependency-links  # install from PyPI

Run
---

.. code-block::

    /PATH/TO/MY/NEW/VIRTUALENV/bin/starfeeder


Windows source installation
===========================

*Deprecated, as it's complex.*

Install
-------

1.  You need to have Python 3 installed (which will come with :code:`pip`,
    :code:`pyvenv`, and :code:`virtualenv`).
    Obtain it from https://www.python.org/ and install it. We'll suppose you've
    installed Python at :code:`C:\Python34`.

2.  Install a copy of :code:`cmake`, because PySide wants it.

3.  Then fire up a Command Prompt and do:

    .. code-block::

        C:\Python34\Scripts\virtualenv.exe C:\PATH\TO\MY\NEW\VIRTUALENV

        C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\activate

        pip install starfeeder --process-dependency-links


Run
---

Run the :code:`starfeeder` program from within your virtual environment.

*Windows: just the GUI*

    For normal use:

    .. code-block::

        C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\pythonw.exe C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\starfeeder-script.py

*Windows: to see command-line output*

    Use this for database upgrades, command-line help, and to see debugging output:

    .. code-block::

        C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\starfeeder

    You can append :code:`-v` for more verbose output, or :code:`--help`
    for full details.

    If you use this method to run the graphical user interface (GUI) application,
    **do not** close the console window (this will close the GUI app). Use the
    method

