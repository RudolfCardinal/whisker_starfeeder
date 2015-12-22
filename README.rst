Whisker Starfeeder
==================

Manages radiofrequency identification (RFID) readers and weighing balances,
and talks to a Whisker client (http://www.whiskercontrol.com/).

Installation: Ubuntu Linux
--------------------------

From a command prompt:

.. code-block::

    sudo apt-get install python3 python3-pip  # install Python with pip

    python3 -m virtualenv /PATH/TO/MY/NEW/VIRTUALENV  # make a virtualenv

    source /PATH/TO/MY/NEW/VIRTUALENV/bin/activate  # activate the virtualenv

    pip install starfeeder  # install from PyPI


Installation: Windows
---------------------

You need to have Python 3 installed (which will come with :code:`pip`,
:code:`pyvenv`, and :code:`virtualenv`).
Obtain it from https://www.python.org/ and install it. We'll suppose you've
installed Python at :code:`C:\Python34`.

Then fire up a Command Prompt and do:

.. code-block::

    C:\Python34\Scripts\virtualenv.exe C:\PATH\TO\MY\NEW\VIRTUALENV

    C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\activate.bat

    pip install starfeeder


Run
---

Run the `starfeeder` program from within your virtual environment. It will be
at:

*Linux*

.. code-block::

    /PATH/TO/MY/NEW/VIRTUALENV/bin/starfeeder

*Windows*

.. code-block::

    C:\PATH\TO\MY\NEW\VIRTUALENV\Scripts\starfeeder.bat  # *** check


You can't yet run from a binary distribution
--------------------------------------------

A single-file installation based on PyInstaller isn't working at the moment;
it pops up a console window (despite options asking it not to) and if this is
closed, the GUI program terminates instantly, which is dangerous.
