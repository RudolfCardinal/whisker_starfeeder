#!/usr/bin/env python3
# weigh/constants.py

from enum import Enum


GUI_MASS_FORMAT = '% 9.6f'
GUI_TIME_FORMAT = '%H:%M:%S'


class ThreadOwnerState(Enum):
    stopped = 0
    starting = 1
    running = 2
    stopping = 3
