#!/usr/bin/env python3
# bugtest_qt_signal_derived.py
# http://stackoverflow.com/questions/34125065/derived-classes-receiving-signals-in-wrong-thread-in-pyside-qt-pyqt

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import sys
import threading
import time

from PySide import QtCore
from PySide.QtCore import (
    QCoreApplication,
    QObject,
    QThread,
    Signal,
    Slot,
)

_oldEmit = QtCore.QObject.emit  # normal method


def debug_emit(self, *args):
    logger.debug("EMIT: thread name={}, emit args={}".format(
        threading.current_thread().name,
        repr(args),
    ))
    _oldEmit(self, *args)

QtCore.QObject.emit = debug_emit


def debug_object(obj):
    logger.debug("Object {} belongs to QThread {}".format(obj, obj.thread()))


def debug_thread(thread_name, thread):
    logger.debug("{} is QThread {}".format(thread_name, thread))


def report(msg):
    logger.info("{} [{}]".format(msg, threading.current_thread().name))


class Transmitter(QObject):
    transmit = Signal()
    finished = Signal()

    def start(self):
        count = 3
        report("Starting transmitter")
        while count > 0:
            time.sleep(1)  # seconds
            report("transmitting, count={}".format(count))
            self.transmit.emit()
            count -= 1
        report("Stopping transmitter")
        self.finished.emit()


class Base(QObject):
    def __init__(self, parent=None):
        # report("Base: super: {}".format(super()))
        super().__init__(parent=parent)

    @Slot()
    def start(self):
        report("Starting receiver")

    @Slot()
    def receive(self):
        report("receive: BASE")


class Derived(Base):
    def __init__(self, parent=None):
        # report("Derived: super: {}".format(super()))
        super().__init__(parent=parent)

    @Slot()
    def receive(self):
        report("receive: DERIVED")


class DerivedTwo(Base):
    def __init__(self, parent=None):
        super().__init__(parent=parent)


class DerivedThree(Base):
    def __init__(self, parent=None):
        # report("DerivedThree: super: {}".format(super()))
        QObject.__init__(self, parent=parent)

#    @Slot()
#    def receive(self):
#        report("receive: DERIVED_THREE")


class RelayBase(QObject):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    @Slot()
    def start(self):
        report("Starting receiver")

    @Slot()
    def receive(self):
        self.on_receive()

    def on_receive(self):
        report("on_receive: BASE")


class RelayDerived(RelayBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def on_receive(self):
        report("on_receive: DERIVED")


class NoSlotBase(QObject):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
    # @Slot()
    def start(self):
        report("Starting receiver")

    # @Slot()
    def receive(self):
        report("receive: BASE")


class DerivedFromNoSlot(NoSlotBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    # @Slot()
    def receive(self):
        report("receive: DERIVED")


USE_DERIVED = True

if __name__ == '__main__':
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)

    # Objects
    app = QCoreApplication(sys.argv)

    tx_thread = QThread()
    debug_thread("tx_thread", tx_thread)
    transmitter = Transmitter()
    debug_object(transmitter)
    transmitter.moveToThread(tx_thread)
    debug_object(transmitter)

    rx_thread = QThread()
    debug_thread("rx_thread", rx_thread)
    if USE_DERIVED:
        # receiver = Derived()
        # receiver = DerivedTwo()
        # receiver = DerivedThree()
        # receiver = RelayDerived()
        receiver = DerivedFromNoSlot()
    else:
        receiver = Base()
        # receiver = RelayBase()
        # receiver = NoSlotBase()
    debug_object(receiver)
    receiver.moveToThread(rx_thread)
    debug_object(receiver)

    # Signals: startup
    tx_thread.started.connect(transmitter.start)
    rx_thread.started.connect(receiver.start)
    # ... shutdown
    transmitter.finished.connect(tx_thread.quit)
    tx_thread.finished.connect(rx_thread.quit)
    rx_thread.finished.connect(app.quit)
    # ... action
    transmitter.transmit.connect(receiver.receive)

    # Go
    rx_thread.start()
    tx_thread.start()
    report("Starting app")
    app.exec_()
