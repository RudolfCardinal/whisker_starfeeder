#!/usr/bin/env python
# starfeeder/serial_controller.py

"""
    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

from collections import deque, OrderedDict
import datetime
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import platform

from PySide.QtCore import (
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
    # Slot,
)
import serial
# pySerial 3: http://pyserial.readthedocs.org/en/latest/pyserial.html

from starfeeder.constants import ThreadOwnerState
from starfeeder.qt import exit_on_exception, StatusMixin

CR = b'\r'
CRLF = b'\r\n'
LF = b'\n'
NO_BYTES = b''

DEBUG_WRITE_TIMING = False


class SerialReader(QObject, StatusMixin):
    """
    Object to monitor input from a serial port.
    Assigned to a thread (see below).
    """
    started = Signal()
    finished = Signal()
    line_received = Signal(bytes, datetime.datetime)

    def __init__(self, name='?', parent=None, eol=LF):
        super().__init__(parent)
        StatusMixin.__init__(self, name, logger)
        self.serial_port = None  # set later
        self.eol = eol

        self.len_eol = len(eol)
        self.finish_requested = False
        self.residual = b''

    @exit_on_exception
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

    @exit_on_exception
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

    def __init__(self, name='?', parent=None, eol=LF, encoding='utf8'):
        # ... UTF8 is ASCII for normal characters.
        super().__init__(parent)
        StatusMixin.__init__(self, name, logger)
        self.serial_port = None  # set later
        self.eol = eol
        self.encoding = encoding
        self.callback_timer = QTimer()
        self.callback_timer.timeout.connect(self.process_queue)
        self.queue = deque()  # contains (data, delay_ms) tuples
        # ... left end = next one to be sent; right = most recent request
        self.busy = False
        # = "don't send new things immediately; we're in a delay"

    @exit_on_exception
    def start(self, serial_port):
        self.debug("starting")
        self.serial_port = serial_port
        self.started.emit()

    @exit_on_exception
    def send(self, data, delay_ms):
        """
        Sending interface offered to others.
        We maintain an orderly output queue and allow delays.
        """
        if isinstance(data, str):
            data = data.encode(self.encoding)
        self.queue.append((data, delay_ms))
        if not self.busy:
            self.process_queue()

    @exit_on_exception
    def process_queue(self):
        """Deals with what's in the queue."""
        self.busy = False
        while len(self.queue) > 0:
            data, delay_ms = self.queue.popleft()
            if delay_ms > 0:
                # Put it back at the front of the queue with zero delay,
                # and wait for the delay before continuing.
                self.queue.appendleft((data, 0))
                self.wait(delay_ms)
                return
            self._send(data)

    def wait(self, delay_ms):
        self.busy = True
        self.callback_timer.setSingleShot(True)
        self.callback_timer.start(delay_ms)

    def _send(self, data):
        """
        Internal function to send data to the serial port directly.
        """
        try:
            outdata = data + self.eol
            self.debug("sending: {}".format(repr(outdata)))
            if DEBUG_WRITE_TIMING:
                t1 = datetime.datetime.utcnow()
            self.serial_port.write(outdata)
            # ... will raise SerialTimeoutException if a write timeout is
            #     set and exceeded
            self.serial_port.flush()
            if DEBUG_WRITE_TIMING:
                t2 = datetime.datetime.utcnow()
                nbytes = len(outdata)
                microsec = (t2 - t1).microseconds
                self.debug(
                    "Sent {} bytes in {} microseconds ({} microseconds per "
                    "byte)".format(nbytes, microsec, microsec/nbytes))
        except Exception as e:
            self.error(str(e))


class SerialController(QObject, StatusMixin):
    """
    Does the thinking. Has its own thread.
    """
    data_send_requested = Signal(bytes, int)
    finished = Signal()

    def __init__(self, name, parent=None):
        super().__init__(parent)
        StatusMixin.__init__(self, name, logger)

    @exit_on_exception
    def on_receive(self, data, timestamp):
        """Should be overridden."""
        pass

    def on_start(self):
        """Should be overridden."""
        pass

    def send(self, data, delay_ms=0):
        self.data_send_requested.emit(data, delay_ms)

    def stop(self):
        """
        Can be overridden, for shutdown tasks.
        But you must emit the finished event when you're happy to proceed.
        """
        self.finished.emit()

    def report_status(self):
        """Should be overridden."""
        pass


class SerialOwner(QObject, StatusMixin):
    """
    Encapsulates a serial port + reader (with thread) + writer (with thread)
    and the associated signals/slots.
    """
    # Outwards, to world:
    started = Signal()
    finished = Signal()
    state_change = Signal(str)
    # Inwards, to possessions:
    reader_start_requested = Signal(serial.Serial)
    writer_start_requested = Signal(serial.Serial)
    reader_stop_requested = Signal()
    writer_stop_requested = Signal()
    controller_stop_requested = Signal()
    status_requested = Signal()

    def __init__(self, serial_args, parent=None, rx_eol=LF, tx_eol=LF,
                 name='?', encoding='utf8',
                 reader_class=SerialReader, reader_kwargs=None,
                 writer_class=SerialWriter, writer_kwargs=None,
                 controller_class=SerialController, controller_kwargs=None):
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
        reader_kwargs = reader_kwargs or {}
        writer_kwargs = writer_kwargs or {}
        controller_kwargs = controller_kwargs or {}
        self.serial_port = None
        self.readerthread = QThread()
        self.writerthread = QThread()
        self.controllerthread = QThread()
        self.state = ThreadOwnerState.stopped

        # Serial port
        self.serial_args = serial_args
        self.serial_args.update(dict(
            timeout=0.01,  # seconds
            write_timeout=5.0,  # seconds; None for blocking writes
            inter_byte_timeout=None,
        ))
        # timeout:
        #   read timeout... in seconds, when numeric
        #   See http://pyserial.readthedocs.org/en/latest/pyserial_api.html
        #   Low values: thread more responsive to termination; more CPU.
        #   High values: the converse.
        #   None: wait forever.
        #   0: non-blocking (avoid here).
        # inter_byte_timeout (formerly inter_byte_timeout):
        #   governs when read() calls return when there is a sufficient time
        #   between incoming bytes;
        #   https://github.com/pyserial/pyserial/blob/master/serial/serialposix.py  # noqa
        #   http://www.unixwiz.net/techtips/termios-vmin-vtime.html
        self.debug("Creating SerialOwner: {}".format(serial_args))

        # Serial reader/writer/controller objects
        reader_kwargs.setdefault('name', name)
        reader_kwargs.setdefault('eol', rx_eol)
        self.reader = reader_class(**reader_kwargs)
        writer_kwargs.setdefault('name', name)
        writer_kwargs.setdefault('eol', tx_eol)
        writer_kwargs.setdefault('encoding', encoding)
        self.writer = writer_class(**writer_kwargs)
        controller_kwargs.setdefault('name', name)
        self.controller = controller_class(**controller_kwargs)

        # Assign objects to thread
        self.reader.moveToThread(self.readerthread)
        self.writer.moveToThread(self.writerthread)
        self.controller.moveToThread(self.controllerthread)

        # Connect object and thread start/stop events
        # ... start sequence
        self.writerthread.started.connect(self.writerthread_started)
        self.writer_start_requested.connect(self.writer.start)
        self.writer.started.connect(self.writer_started)
        self.readerthread.started.connect(self.readerthread_started)
        self.reader_start_requested.connect(self.reader.start)
        self.controllerthread.started.connect(self.controllerthread_started)
        self.started.connect(self.controller.on_start)

        # ... stop
        self.controller_stop_requested.connect(self.controller.stop)
        self.controller.finished.connect(self.controllerthread.quit)
        self.controllerthread.finished.connect(self.controllerthread_finished)
        self.controllerthread.finished.connect(self.reader_stop_requested)
        self.controllerthread.finished.connect(self.writer_stop_requested)
        self.reader_stop_requested.connect(self.reader.stop,
                                           Qt.DirectConnection)  # NB!
        self.reader.finished.connect(self.readerthread.quit)
        self.readerthread.finished.connect(self.readerthread_finished)
        self.writer_stop_requested.connect(self.writerthread.quit)
        self.writerthread.finished.connect(self.writerthread_finished)

        # Connect the status events
        self.reader.status_sent.connect(self.status_sent)
        self.reader.error_sent.connect(self.error_sent)
        self.writer.status_sent.connect(self.status_sent)
        self.writer.error_sent.connect(self.error_sent)
        self.controller.status_sent.connect(self.status_sent)
        self.controller.error_sent.connect(self.error_sent)
        self.status_requested.connect(self.controller.report_status)

        # Connect the control events
        self.reader.line_received.connect(self.controller.on_receive)
        self.controller.data_send_requested.connect(self.writer.send)

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
        self.state_change.emit(state.name)

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
        self.set_state(ThreadOwnerState.starting)
        try:
            self.info("Opening serial port: {}".format(self.serial_args))
            self.serial_port = serial.Serial(**self.serial_args)
        except Exception as e:
            self.error(str(e))
            self.stop()
            return
        self.debug("starting writer thread")
        self.writerthread.start()

    @exit_on_exception
    def writerthread_started(self):
        self.writer_start_requested.emit(self.serial_port)

    @exit_on_exception
    def writer_started(self):
        self.debug("start: starting reader thread")
        self.readerthread.start()

    @exit_on_exception
    def readerthread_started(self):
        self.reader_start_requested.emit(self.serial_port)
        # We'll never get a callback from that; it's now busy.
        self.debug("start: starting controller thread")
        self.controllerthread.start()

    @exit_on_exception
    def controllerthread_started(self):
        self.set_state(ThreadOwnerState.running)
        self.started.emit()

    # -------------------------------------------------------------------------
    # Stopping
    # -------------------------------------------------------------------------
    # The stop sequence is more fluid, to cope with any problems.

    def stop(self):
        if self.state == ThreadOwnerState.stopped:
            self.error("Can't stop: state is: {}".format(self.state.name))
            return
        self.set_state(ThreadOwnerState.stopping)
        self.debug("stop: asking threads to finish")
        if self.check_everything_finished():
            return
        self.controller_stop_requested.emit()

    @exit_on_exception
    def reader_finished(self):
        self.debug("SerialController.reader_finished")
        self.readerthread.quit()

    @exit_on_exception
    def readerthread_finished(self):
        self.debug("stop: reader thread stopped")
        self.check_everything_finished()

    @exit_on_exception
    def writerthread_finished(self):
        self.debug("stop: writer thread stopped")
        self.check_everything_finished()

    @exit_on_exception
    def controllerthread_finished(self):
        self.debug("stop: controller thread stopped")
        self.check_everything_finished()

    def check_everything_finished(self):
        if (self.readerthread.isRunning()
                or self.writerthread.isRunning()
                or self.controllerthread.isRunning()):
            return False
        self.set_state(ThreadOwnerState.stopped)
        self.finished.emit()
        return True

    # -------------------------------------------------------------------------
    # Info
    # -------------------------------------------------------------------------

    def report_status(self):
        self.status("state: {}".format(self.state.name))
        # I think it's OK to request serial port information from the GUI
        # thread...
        try:
            sp = self.serial_port
            paritybits = 0 if sp.parity == serial.PARITY_NONE else 1
            n_bits = sp.bytesize + paritybits + sp.stopbits
            time_per_char_microsec = n_bits * 1000000 / sp.baudrate

            portset = OrderedDict()
            portset['name'] = sp.name
            portset['port'] = sp.port
            portset['baudrate'] = sp.baudrate
            portset['bytesize'] = sp.bytesize
            portset['parity'] = sp.parity
            portset['stopbits'] = sp.stopbits
            portset['timeout'] = sp.timeout
            portset['xonxoff'] = sp.xonxoff
            portset['rtscts'] = sp.rtscts
            portset['dsrdtr'] = sp.dsrdtr
            portset['write_timeout'] = sp.write_timeout
            portset['inter_byte_timeout'] = sp.inter_byte_timeout
            self.status("Serial port settings: " + ", ".join(
                "{}={}".format(k, v) for k, v in portset.items()))

            portinfo = OrderedDict()
            portinfo['in_waiting'] = sp.in_waiting
            if platform.system() in ['Linux', 'Windows']:
                portinfo['out_waiting'] = sp.out_waiting
            portinfo['break_condition'] = sp.break_condition
            portinfo['rts'] = sp.rts
            portinfo['cts'] = sp.cts
            portinfo['dtr'] = sp.dtr
            portinfo['dsr'] = sp.dsr
            portinfo['ri'] = sp.ri
            portinfo['cd'] = sp.cd
            portinfo['rs485_mode'] = sp.rs485_mode
            portinfo['[time_per_char_microsec]'] = time_per_char_microsec
            self.status("Serial port info: " + ", ".join(
                "{}={}".format(k, v) for k, v in portinfo.items()))
        except ValueError:
            self.status("Serial port is unhappy - may be closed")
        self.status_requested.emit()
