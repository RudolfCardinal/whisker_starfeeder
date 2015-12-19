#!/usr/bin/env python
# weigh/debug_qt.py

# Adapted from: http://stackoverflow.com/questions/2045352

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import threading

from PySide import QtCore

_oldConnect = QtCore.QObject.connect  # staticmethod
_oldDisconnect = QtCore.QObject.disconnect  # staticmethod
_oldEmit = QtCore.QObject.emit  # normal method


def _wrapConnect(callableObject):
    """Returns a wrapped call to the old version of QtCore.QObject.connect"""
    @staticmethod
    def call(*args):
        callableObject(*args)
        _oldConnect(*args)
    return call


def _wrapDisconnect(callableObject):
    """
    Returns a wrapped call to the old version of QtCore.QObject.disconnect
    """
    @staticmethod
    def call(*args):
        callableObject(*args)
        _oldDisconnect(*args)
    return call


def enableSignalDebugging(**kwargs):
    """Call this to enable Qt Signal debugging. This will trap all
    connect, and disconnect calls."""

    f = lambda *args: None
    connectCall = kwargs.get('connectCall', f)
    disconnectCall = kwargs.get('disconnectCall', f)
    emitCall = kwargs.get('emitCall', f)

    QtCore.QObject.connect = _wrapConnect(connectCall)
    QtCore.QObject.disconnect = _wrapDisconnect(disconnectCall)

    def new_emit(self, *args):
        emitCall(self, *args)
        _oldEmit(self, *args)

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


def enableSignalDebuggingSimply():
    enableSignalDebugging(connectCall=simple_connect_debugger,
                          emitCall=simple_emit_debugger)


def debug_object(obj):
    logger.debug("Object {} belongs to QThread {}".format(obj, obj.thread()))
    # Does nothing if library compiled in release mode:
    # logger.debug("... dumpObjectInfo: {}".format(obj.dumpObjectInfo()))
    # logger.debug("... dumpObjectTree: {}".format(obj.dumpObjectTree()))


def debug_thread(thread):
    logger.debug("QThread {}".format(thread))
