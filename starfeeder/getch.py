#!/usr/bin/env python
# starfeeder/getch.py

import atexit
import select
import sys

try:
    import msvcrt  # Windows only
    termios = None
    tty = None
except ImportError:
    msvcrt = None
    import termios  # Unix only
    import tty  # requires termios, so Unix only


# =============================================================================
# Read single character, waiting for it
# =============================================================================
# http://stackoverflow.com/questions/510357/python-read-a-single-character-from-the-user  # noqa
# http://home.wlu.edu/~levys/software/kbhit.py
# ... modified a little

def _getch_windows():
    """Gets a single character from standard input.  Does not echo to the
    screen."""
    return msvcrt.getch().decode('utf-8')


def _getch_unix():
    """Gets a single character from standard input.  Does not echo to the
    screen. Note that the terminal will have been pre-configured, below."""
    return sys.stdin.read(1)


# =============================================================================
# Is a keystroke available?
# =============================================================================
# http://code.activestate.com/recipes/572182-how-to-implement-kbhit-on-linux/
# http://stackoverflow.com/questions/2408560/python-nonblocking-console-input

def _kbhit_windows():
    return msvcrt.kbhit()


def _kbhit_unix():
    dr, dw, de = select.select([sys.stdin], [], [], 0)
    return dr != []


# =============================================================================
# Configure terminal (UNIX)
# =============================================================================

def set_normal_term():
    # switch to normal terminal
    termios.tcsetattr(_fd, termios.TCSAFLUSH, _old_term)


def set_curses_term():
    # switch to unbuffered terminal
    termios.tcsetattr(_fd, termios.TCSAFLUSH, _new_term)


# =============================================================================
# Set up for specific OS
# =============================================================================

if msvcrt:
    # -------------------------------------------------------------------------
    # Windows
    # -------------------------------------------------------------------------
    getch = _getch_windows
    kbhit = _kbhit_windows
else:
    # -------------------------------------------------------------------------
    # Unix
    # -------------------------------------------------------------------------
    getch = _getch_unix
    kbhit = _kbhit_unix

    # save the terminal settings
    _fd = sys.stdin.fileno()
    _new_term = termios.tcgetattr(_fd)
    _old_term = termios.tcgetattr(_fd)
    # new terminal setting unbuffered
    _new_term[3] = (_new_term[3] & ~termios.ICANON & ~termios.ECHO)
    _new_term[6][termios.VMIN] = 1
    _new_term[6][termios.VTIME] = 0

    atexit.register(set_normal_term)
    set_curses_term()
