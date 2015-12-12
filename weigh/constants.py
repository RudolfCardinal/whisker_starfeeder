#!/usr/bin/env python3
# weigh/constants.py

from enum import Enum


class ThreadOwnerState(Enum):
    stopped = 0
    starting = 1
    running = 2
    stopping = 3
