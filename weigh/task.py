#!/usr/bin/env python
# weigh/task.py

import logging
logger = logging.getLogger(__name__)

from weigh.db import session_thread_scope
# from weigh.debug_qt import debug_object
from weigh.models import (
    MassEventRecord,
    MasterConfig,
    RfidEventRecord,
)
from weigh.qt import exit_on_exception
from weigh.version import VERSION
from weigh.whisker_qt import WhiskerTask


class WeightWhiskerTask(WhiskerTask):
    """Doesn't define an end, deliberately."""

    def __init__(self, wcm_prefix="", parent=None, name="whisker_task",
                 **kwargs):
        super().__init__(parent=parent, name=name)
        self.wcm_prefix = wcm_prefix

    def start(self):
        with session_thread_scope() as session:
            config = MasterConfig.get_singleton(session)
            self.rfid_effective_time_s = config.rfid_effective_time_s

    @exit_on_exception
    def on_connect(self):
        # self.debug("DERIVED on_connect")
        # debug_object(self)
        # self.whisker.command("TimerSetEvent 2000 5 bop")
        self.whisker.command("ReportName Starfeeder {}".format(VERSION))

    @exit_on_exception
    def on_event(self, event, timestamp, whisker_timestamp_ms):
        pass
        # if event == "bop":
        #     self.status("boop")

    def broadcast(self, msg):
        if self.wcm_prefix:
            msg + "{}{}".format(self.wcm_prefix, msg)
        self.whisker.broadcast(msg)

    @exit_on_exception
    def on_rfid(self, rfid_event):
        """
        Record an RFID event.

        Since this task runs in a non-GUI thread, it's a good place to do the
        main RFID processing.

        Only one thread should be writing to the database, to avoid locks.

        Don't hold the session too long, on general principles.
        """
        with session_thread_scope() as session:
            RfidEventRecord.record_rfid_detection(
                session, rfid_event, self.rfid_effective_time_s)
        # self.status("RFID received: {}".format(rfid_event))
        if self.whisker.is_connected():
            self.broadcast("reader {}, RFID {}, timestamp {}".format(
                rfid_event.rfid,
                rfid_event.reader_name,
                rfid_event.timestamp))

    @exit_on_exception
    def on_mass(self, mass_event):
        """
        Receive a mass event. Ask the MassIdentifiedEvent class to Work out if
        it represents an identified mass event (and store it, if so).
        Broadcast the information to the Whisker client.
        """
        if not mass_event.locked or mass_event.rfid is None:
            return
        with session_thread_scope() as session:
            MassEventRecord.record_mass_detection(session, mass_event)
        if self.whisker.is_connected():
            self.broadcast(
                "reader {}, RFID {}, balance {}, mass {} kg, "
                "at {}".format(
                    mass_event.reader_name,
                    mass_event.rfid,
                    mass_event.balance_name,
                    mass_event.mass_kg,
                    mass_event.timestamp))
