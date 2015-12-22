Whisker Starfeeder
==================

Manages radiofrequency identification (RFID) readers and weighing balances,
and talks to a Whisker client (http://www.whiskercontrol.com/).

Running from a distributable
----------------------------

Unzip the distributed package and run ``starfeeder``. That's it.

Installation of full package with source
----------------------------------------

1. **Python/pip.**

You need to have Python 3 and :code:`pip` installed.

2. **Make a virtual environment.**

You will want a Python virtual environment.
If you have :code:`pyvenv` installed, you can do:

.. code-block::

   pyvenv /path/to/my/new/virtualenv

If you want :code:`virtualenv`, install it using :code:`pip3 install virtualenv`.
Using :code:`virtualenv`, create your virtual environment with:

.. code-block::

   virtualenv /path/to/my/new/virtualenv

3. **Activate your virtual environment**

On Linux:

.. code-block::

    source /path/to/my/new/virtualenv/bin/activate

On Windows:

.. code-block::

    C:\\path\\to\\my\\new\\virtualenv\\Scripts\\activate.bat

4. **Install Starfeeder**

.. code-block::

   pip install starfeeder  # *** NEED TO ADD GIT REPOSITORY NAME UNTIL ON PYPI


Creating a distributable
------------------------

From within the activated virtualenv:

.. code-block::

    tools/make_pyinstaller_distributable.sh

The folder ``dist/starfeeder`` should now contain everything you need, including
the ``starfeeder`` executable. You'll need to build separately for Linux and
Windows.


