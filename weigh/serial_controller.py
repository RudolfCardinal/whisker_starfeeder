#!/usr/bin/env python3
# weigh/serial_controller.py

import datetime
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from PySide.QtCore import (
    QObject,
    Qt,
    QThread,
    Signal,
    # Slot,
)
import serial

from weigh.constants import ThreadOwnerState
from weigh.qt import StatusMixin


CR = b'\r'
CRLF = b'\r\n'
LF = b'\n'
NO_BYTES = b''


class SerialReader(QObject, StatusMixin):
    """
    Object to monitor input from a serial port.
    Assigned to a thread (see below).
    """
    started = Signal()
    finished = Signal()
    line_received = Signal(bytes, datetime.datetime)

    def __init__(self, name='?', parent=None, eol=LF, extra_kwargs=None):
        super().__init__(parent)
        StatusMixin.__init__(self, name, logger)
        self.serial_port = None  # set later
        self.eol = eol

        self.len_eol = len(eol)
        self.finish_requested = False
        self.residual = b''

    # slot
    def start(self, serial_port):
        self.serial_port = serial_port
        self.debug("SerialReader starting. Using port {}".format(serial_port))
        self.finish_requested = False
        try:
            while not self.finish_requested:
                # We could use self.serial_port.readline(), noting also
                # http://pyserial.readthedocs.org/en/latest/shortintro.html
                # But we have to do some EOL stripping anyway, so let's just
                # do it in the raw.
                data = self.serial_port.read(1)  # will wait until timeout
                # ... will return b'' if no data
                data += self.serial_port.read(self.serial_port.inWaiting())
                if len(data) > 0:
                    self.process_data(data)
        # except serial.SerialException as e:
        except Exception as e:
            self.debug("----- EXCEPTION within SerialReader")
            self.error(str(e))
        # We should catch serial.SerialException, but there is a bug in
        # serial/serialposix.py that does "if e[0] != errno.EAGAIN", which
        # raises TypeError: 'SerialException' object does not support indexing
        self.finish()

    def process_data(self, data):
        """
        Adds the incoming data to any stored residual, splits it into lines,
        and sends each line on to the receiver.
        """
        self.debug("data: {}".format(repr(data)))
        timestamp = datetime.datetime.now()
        data = self.residual + data
        fragments = data.split(self.eol)
        lines = fragments[:-1]
        self.residual = fragments[-1]
        for line in lines:
            self.debug("line: {}".format(repr(line)))
            self.line_received.emit(line, timestamp)

    # slot
    def stop(self):
        """
        Request that the serial handler terminates.

        - If you call this using the default Signal/Slot mechanism, the
          connection type is QtCore.Qt.AutoConnection. When used across
          threads, this acts as Qt.QueuedConnection, sending from one thread
          and receiving on another. Atomic access to the variable is therefore
          not an issue, but it has to wait for the receiver to return to its
          message loop. So it won't work for the kind of loop we're operating
          here.
        - We could call the function directly from the calling thread, without
          any signal/slot stuff. That means we have to be sure the variable
          access is atomic.
        - We could use a signal/slot, but specify a Qt.DirectConnection.
          Then the function executes in the caller's thread, so we have to
          think about atomic access again.

        - What about atomic access?
          Well, there's QtCore.QMutex.

        - However, in this specific situation, of a Boolean variable that
          we are writing once, only reading from the other thread, and
          the exact timing of the off-to-on transition is immaterial, we
          should be fine here to ignore it.

        - In general, note also that the thread control mechanisms are LESS
          POWERFUL than you might guess. For example, you will never get a
          "started" message back from a thread function that loops
          indefinitely. (Therefore, if you want to start things in sequence,
          start writers before readers.)

        http://doc.qt.io/qt-4.8/qt.html#ConnectionType-enum
        https://srinikom.github.io/pyside-docs/PySide/QtCore/QMutex.html
        """
        # This is called via the Signal/Slot mechanism, which (when using the
        # default Auto Connection), executes the slot in the receiver's thread.
        # In other words, we don't have to use a mutex on this variable because
        # we are accessing it via the Qt signal/slot mechanism.
        self.debug("stopping")
        self.finish_requested = True

    def finish(self):
        self.finished.emit()


class SerialWriter(QObject, StatusMixin):
    """
    Object to send to a serial port.
    Assigned to a thread (see below).
    """
    started = Signal()
    finished = Signal()

    def __init__(self, name='?', parent=None, eol=LF, encoding='utf8',
                 extra_kwargs=None):
        # ... UTF8 is ASCII for normal characters.
        super().__init__(parent)
        StatusMixin.__init__(self, name, logger)
        self.serial_port = None  # set later
        self.eol = eol
        self.encoding = encoding

    # slot
    def start(self, serial_port):
        self.debug("starting")
        self.serial_port = serial_port
        self.started.emit()

    # slot
    def send(self, data):
        if isinstance(data, str):
            data = data.encode(self.encoding)
        try:
            outdata = data + self.eol
            self.debug("sending: {}".format(repr(outdata)))
            self.serial_port.write(outdata)
            self.serial_port.flush()
        except Exception as e:
            self.error(str(e))


class SerialController(QObject, StatusMixin):
    """
    Encapsulates a serial port + reader (with thread) + writer (with thread)
    and the associated signals/slots.
    """
    reader_start_requested = Signal(serial.Serial)
    writer_start_requested = Signal(serial.Serial)
    reader_stop_requested = Signal()
    writer_stop_requested = Signal()
    finished = Signal()
    data_send_requested = Signal(bytes)

    def __init__(self, serial_args, parent=None, rx_eol=LF, tx_eol=LF,
                 name='?', encoding='utf8',
                 reader_class=SerialReader, reader_kwargs=None,
                 writer_class=SerialWriter, writer_kwargs=None):
        """
        serial_args: as per PySerial:
            port
            baudrate
            bytesize
            parity
            stopbits
            xonxoff
            rtscts
            dsrdtr
        """
        super().__init__(parent)
        StatusMixin.__init__(self, name, logger)
        reader_kwargs = reader_kwargs or []
        writer_kwargs = writer_kwargs or []
        self.serial_port = None
        self.readerthread = QThread()
        self.writerthread = QThread()
        self.reader = None
        self.writer = None
        self.state = ThreadOwnerState.stopped

        # Serial port
        self.serial_args = serial_args
        self.serial_args.update(dict(
            timeout=0.01,  # seconds
            writeTimeout=None,  # blocking writes
            interCharTimeout=None,
        ))
        # timeout:
        #   read timeout... in seconds, when numeric
        #   See http://pyserial.readthedocs.org/en/latest/pyserial_api.html
        #   Low values: thread more responsive to termination; more CPU.
        #   High values: the converse.
        #   None: wait forever.
        #   0: non-blocking (avoid here).
        self.debug("Creating SerialController: {}".format(serial_args))

        # Serial reader/writer objects
        self.reader = reader_class(name=name, eol=rx_eol,
                                   extra_kwargs=reader_kwargs)
        self.writer = writer_class(name=name, eol=tx_eol, encoding=encoding,
                                   extra_kwargs=writer_kwargs)

        # Assign objects to thread
        self.reader.moveToThread(self.readerthread)
        self.writer.moveToThread(self.writerthread)

        # Connect object and thread start/stop events
        # ... start sequence
        self.writerthread.started.connect(self.writerthread_started)
        self.writer_start_requested.connect(self.writer.start)
        self.writer.started.connect(self.writer_started)
        self.readerthread.started.connect(self.readerthread_started)
        self.reader_start_requested.connect(self.reader.start)
        # ... stop
        self.reader_stop_requested.connect(self.reader.stop,
                                           Qt.DirectConnection)  # NB!
        self.reader.finished.connect(self.readerthread.quit)
        self.readerthread.finished.connect(self.readerthread_finished)
        self.writer_stop_requested.connect(self.writerthread.quit)
        self.writerthread.finished.connect(self.writerthread_finished)

        # Connect the control events
        self.reader.error_sent.connect(self.error_sent)
        self.reader.line_received.connect(self.serial_receive)
        self.writer.error_sent.connect(self.error_sent)
        self.data_send_requested.connect(self.writer.send)

    # -------------------------------------------------------------------------
    # General state control
    # -------------------------------------------------------------------------

    def is_running(self):
        running = self.state != ThreadOwnerState.stopped
        self.debug("is_running: {} (state: {})".format(running,
                                                       self.state.name))
        return running

    def set_state(self, state):
        self.debug("state: {} -> {}".format(self.state.name, state.name))
        self.state = state

    # -------------------------------------------------------------------------
    # Starting
    # -------------------------------------------------------------------------
    # We must have control over the order. We mustn't call on_start()
    # until BOTH threads have started. Therefore we must start them
    # sequentially, not simultaneously. The reader does not exit, so can't
    # notify us that it's started (since such notifications are via the Qt
    # message loop); therefore, we must start the writer first.

    def start(self):
        self.status("Starting serial")
        if self.state != ThreadOwnerState.stopped:
            self.error("Can't start: state is: {}".format(self.state.name))
            return
        try:
            self.serial_port = serial.Serial(**self.serial_args)
        except Exception as e:
            self.error(str(e))
            return
        self.set_state(ThreadOwnerState.starting)
        self.debug("starting writer thread")
        self.writerthread.start()

    # slot
    def writerthread_started(self):
        self.writer_start_requested.emit(self.serial_port)

    # slot
    def writer_started(self):
        self.debug("start: starting reader thread")
        self.readerthread.start()

    # slot
    def readerthread_started(self):
        self.reader_start_requested.emit(self.serial_port)
        # We'll never get a callback from that; it's now busy.
        self.set_state(ThreadOwnerState.running)
        self.on_start()

    # -------------------------------------------------------------------------
    # Stopping
    # -------------------------------------------------------------------------
    # The stop sequence is more fluid, to cope with any problems.

    def stop(self):
        if self.state == ThreadOwnerState.stopped:
            self.error("Can't stop: state is: {}".format(self.state.name))
            return
        self.on_stop()
        self.set_state(ThreadOwnerState.stopping)
        self.debug("stop: asking threads to finish")
        self.reader_stop_requested.emit()
        self.writer_stop_requested.emit()

    # slot
    def reader_finished(self):
        self.debug("SerialController.reader_finished")
        self.readerthread.quit()

    # slot
    def readerthread_finished(self):
        self.debug("stop: reader thread stopped")
        self.check_everything_finished()

    # slot
    def writerthread_finished(self):
        self.debug("stop: writer thread stopped")
        self.check_everything_finished()

    def check_everything_finished(self):
        if self.readerthread.isRunning() or self.writerthread.isRunning():
            return
        self.set_state(ThreadOwnerState.stopped)
        self.finished.emit()

    # -------------------------------------------------------------------------
    # Info
    # -------------------------------------------------------------------------

    def report_status(self):
        self.status("state: {}".format(self.state.name))

    # -------------------------------------------------------------------------
    # Other
    # -------------------------------------------------------------------------

    # slot
    def serial_receive(self, data, timestamp):
        self.on_receive(data, timestamp)

    def on_receive(self, data, timestamp):
        """Should be overridden."""
        pass

    def on_start(self):
        """Should be overridden."""
        pass

    def send(self, data):
        if self.state != ThreadOwnerState.running:
            self.warning("send called, but controller not running")
            return
        self.data_send_requested.emit(data)

    def on_stop(self):
        """Can be overridden, for shutdown tasks."""
        pass
