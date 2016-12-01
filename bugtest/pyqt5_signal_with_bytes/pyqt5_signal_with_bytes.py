#!/usr/bin/env python
# pyqt5_signal_with_bytes.py

import signal
import sys
from PyQt5.QtCore import (
    QCoreApplication, QObject, QThread, pyqtSignal, pyqtSlot
)

THREADED = True
WITH_TEMPORARY_VARIABLES = True

VERBOSE = False

SOURCE_STR_FOR_TEMP = "ab cd ef"
SOURCE_BYTES_FOR_TEMP = b"gh ij kl"

SOURCE_STR_STATIC = ["mn", "op", "qr"]
SOURCE_BYTES_STATIC = [b"st", b"uv", b"wx"]


class Sender(QObject):
    send_bytes = pyqtSignal(bytes)
    send_str = pyqtSignal(str)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    @pyqtSlot()
    def act(self) -> None:
        while True:
            if VERBOSE:
                print("Sending from thread {}".format(
                    int(QThread.currentThreadId())))
            if WITH_TEMPORARY_VARIABLES:
                # By iterating through x.split(), we create and send
                # temporary variables, which have the potential to be
                # garbage-collected.
                for s in SOURCE_STR_FOR_TEMP.split(" "):
                    self.send_str.emit(s)
                for b in SOURCE_BYTES_FOR_TEMP.split(b" "):
                    self.send_bytes.emit(b)
            else:
                # Here, the objects already exist
                for s in SOURCE_STR_STATIC:
                    self.send_str.emit(s)
                for b in SOURCE_BYTES_STATIC:
                    self.send_bytes.emit(b)


class Receiver(QObject):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    @pyqtSlot(bytes)
    def on_bytes(self, data: bytes) -> None:
        if VERBOSE:
            print("on_bytes received: {} [thread {}]".format(
                repr(data), int(QThread.currentThreadId())))
        if ((WITH_TEMPORARY_VARIABLES and
                data not in SOURCE_BYTES_FOR_TEMP.split(b" ")) or
                (not WITH_TEMPORARY_VARIABLES and
                    data not in SOURCE_BYTES_STATIC)):
            print("FAILURE: on_bytes received {}".format(repr(data)))

    @pyqtSlot(str)
    def on_str(self, data: str) -> None:
        if VERBOSE:
            print("on_str received: {} [thread {}]".format(
                repr(data), int(QThread.currentThreadId())))
        if ((WITH_TEMPORARY_VARIABLES and
                data not in SOURCE_STR_FOR_TEMP.split(" ")) or
                (not WITH_TEMPORARY_VARIABLES and
                    data not in SOURCE_STR_STATIC)):
            print("FAILURE: on_str received {}".format(repr(data)))


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # respond to CTRL-C
    app = QCoreApplication(sys.argv)
    sender = Sender(parent=app)
    if THREADED:
        receiver = Receiver()
        thread = QThread(app)
        receiver.moveToThread(thread)
        thread.start()
    else:
        receiver = Receiver(parent=app)
    sender.send_bytes.connect(receiver.on_bytes)
    sender.send_str.connect(receiver.on_str)
    if THREADED:
        thread.started.connect(sender.act)
    else:
        sender.act()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


"""
- Test environment:
        Python 3.5.2 [GCC 5.4.0 20160609] on linux
        pip install PyQt5==5.7

- FAILS with only this combination:
        bytes (not str)
        THREADED = True
        WITH_TEMPORARY_VARIABLES = True

- The failure messages have included:
        FAILURE: on_bytes received b'\xb0C\x8a\x01'
        FAILURE: on_bytes received b''

- This suggests that bytes objects are being corrupted in transit when they are
  created as temporary variables and passed through threads, which suggests,
  perhaps, that they are being garbage-collected before/during receipt?

- Why?
    - PyQt5 translates signal parameters into C++ objects
      http://pyqt.sourceforge.net/Docs/PyQt5/signals_slots.html

    - It looks like a Python 3 bytes object is translated into "const char*"
        ... line 419 of https://github.com/baoboa/pyqt5/blob/master/qpy/QtCore/qpycore_chimera.cpp

        ... note that QMetaType::UnknownType is 0
            - http://doc.qt.io/qt-5/qmetatype.html#Type-enum
        ... whereas lines 421-2 assigns _metatype = -1; _name = "const char*";

        ... anyway, I'm not sure how the PyQt5 system should be managing
            reference counts here (INCREF etc.), and it looks like it does try:
                Py_INCREF((PyObject *)_py_type);

    - The other places of interest look like:

        - transmission: qpycore_pyqtsignal*.cpp

        - receipt: line 139 of https://github.com/baoboa/pyqt5/blob/master/qpy/QtCore/qpycore_pyqtslot.cpp
            PyObject *arg = (*it)->toPyObject(*++qargs);

            - calls Chimera::toPyObject
                ? relevant bit is line 1318 of qypycore_chimera.cpp:
                return toPyObject(const_cast<void *>(var.data()));

- Anyway, not sure, but there's a bug.

"""  # noqa
