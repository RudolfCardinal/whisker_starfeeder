#!/usr/bin/env python
# starfeeder/debug_qt.py

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

# See: http://stackoverflow.com/questions/2045352

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import threading

from PySide import QtCore

_old_connect = QtCore.QObject.connect  # staticmethod
_old_disconnect = QtCore.QObject.disconnect  # staticmethod
_old_emit = QtCore.QObject.emit  # normal method


def _wrap_connect(callable_object):
    """Returns a wrapped call to the old version of QtCore.QObject.connect"""
    @staticmethod
    def call(*args):
        callable_object(*args)
        _old_connect(*args)
    return call


def _wrap_disconnect(callable_object):
    """
    Returns a wrapped call to the old version of QtCore.QObject.disconnect
    """
    @staticmethod
    def call(*args):
        callable_object(*args)
        _old_disconnect(*args)
    return call


def enable_signal_debugging(**kwargs):
    """Call this to enable Qt Signal debugging. This will trap all
    connect, and disconnect calls."""

    f = lambda *args: None
    connect_call = kwargs.get('connect_call', f)
    disconnect_call = kwargs.get('disconnect_call', f)
    emit_call = kwargs.get('emit_call', f)

    QtCore.QObject.connect = _wrap_connect(connect_call)
    QtCore.QObject.disconnect = _wrap_disconnect(disconnect_call)

    def new_emit(self, *args):
        emit_call(self, *args)
        _old_emit(self, *args)

    QtCore.QObject.emit = new_emit


def simple_connect_debugger(*args):
    logger.debug("CONNECT: args={}".format(args))


def simple_emit_debugger(*args):
    emitter = args[0]
    # emitter_qthread = emitter.thread()
    logger.debug(
        "EMIT: emitter={}, "  # emitter's thread={}, currentThreadId={}, "
        "thread name={}, signal={}, args={}".format(
            emitter,
            # emitter_qthread,
            # emitter_qthread.currentThreadId(),
            threading.current_thread().name,
            repr(args[1]),
            repr(args[2:]),
        )
    )


def enable_signal_debugging_simply():
    enable_signal_debugging(connect_call=simple_connect_debugger,
                            emit_call=simple_emit_debugger)


def debug_object(obj):
    logger.debug("Object {} belongs to QThread {}".format(obj, obj.thread()))
    # Does nothing if library compiled in release mode:
    # logger.debug("... dumpObjectInfo: {}".format(obj.dumpObjectInfo()))
    # logger.debug("... dumpObjectTree: {}".format(obj.dumpObjectTree()))


def debug_thread(thread):
    logger.debug("QThread {}".format(thread))
