#!/usr/bin/env python

"""
This file exists so as to launch the 'main' script as a module.
It's not relevant when the package is installed via pip (as that
creates its own launch script) or packaged via PyInstaller.

Note that the alternative to this is:

    $ python -m starfeeder.main

This launch method is important to avoid this error:
    SystemError: Parent module '' not loaded, cannot perform relative import
... which is what happens if you call starfeeder/main.py directly; see
http://stackoverflow.com/questions/16981921/relative-imports-in-python-3
"""

import starfeeder.main

if __name__ == '__main__':
    starfeeder.main.main()
