==================
Whisker Starfeeder
==================

Purpose
=======

Manages radiofrequency identification (RFID) readers and weighing balances,
and talks to a Whisker client (http://www.whiskercontrol.com/).

Install
=======

Ubuntu Linux
------------

From a command prompt:

.. code-block::

    sudo apt-get install python3 python3-pip  # install Python with pip

    python3 -m virtualenv /PATH/TO/MY/NEW/VIRTUALENV  # make a virtualenv

    source /PATH/TO/MY/NEW/VIRTUALENV/bin/activate  # activate the virtualenv

    pip install starfeeder --process-dependency-links  # install from PyPI


Windows
-------

You need to have Python 3 installed (which will come with :code:`pip`,
:code:`pyvenv`, and :code:`virtualenv`).
Obtain it from https://www.python.org/ and install it. We'll suppose you've
installed Python at :code:`C:\Python34`.

Then fire up a Command Prompt and do:

.. code-block::

    C:\Python34\Scripts\virtualenv.exe C:\PATH\TO\MY\NEW\VIRTUALENV

    C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\activate

    pip install starfeeder --process-dependency-links


Run
===

Run the :code:`starfeeder` program from within your virtual environment.
It will be at:

Linux
-----

.. code-block::

    /PATH/TO/MY/NEW/VIRTUALENV/bin/starfeeder

Windows
-------

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


Single-folder binary distribution
=================================

**You can't yet install and run from a binary distribution.**

A single-file or single-folder installation based on PyInstaller would be
helpful; this bundles Python, the necessary virtual environment, and the
application together. However, it isn't working at the moment.
The app must be able to run without a command-line window, and
should be able also to run with one (since additional command-line tools are
required for database management), but PyInstaller's multipackage bundles are
broken at the moment
(http://pythonhosted.org/PyInstaller/#multipackage-bundles).
