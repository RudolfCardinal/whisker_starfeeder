#!/usr/bin/env python

"""
This script's extension is .pyw, not .py; this will trigger the Windows
Python launcher to use pythonw.exe, not python.exe, and that gets rid of the
console window.
"""

from starfeeder.main import main

if __name__ == '__main__':
    main()
