#!/usr/bin/env python3
# weigh/task.py

import logging
logger = logging.getLogger(__name__)

from weigh.db import session_thread_scope
# from weigh.debug_qt import debug_object
from weigh.models import (
    BalanceConfig,
    MassIdentifiedEvent,
    MasterConfig,
    RfidConfig,
    RfidEvent,
)
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

    # slot
    def on_connect(self):
        # self.debug("DERIVED on_connect")
        # debug_object(self)
        # self.whisker.command("TimerSetEvent 2000 5 bop")
        pass

    # slot
    def on_event(self, event, timestamp, whisker_timestamp_ms):
        pass
        # if event == "bop":
        #     self.status("boop")

    def broadcast(self, msg):
        if self.wcm_prefix:
            msg + "{}{}".format(self.wcm_prefix, msg)
        self.whisker.broadcast(msg)

    # slot
    def on_rfid(self, rfid_single_event):
        """
        Since this task runs in a non-GUI thread, and has its own database
        session, it's a good place to do the main RFID processing.
        """
        with session_thread_scope() as session:
            rfid_event = RfidEvent.record_rfid_detection(
                session, rfid_single_event, self.rfid_effective_time_s)
            self.status("RFID received: {}".format(rfid_event))
            reader_name = RfidConfig.get_name_from_id(
                session, rfid_single_event.reader_id)
            self.broadcast("reader {}, RFID {}, timestamp {}".format(
                rfid_single_event.rfid,
                reader_name,
                rfid_single_event.timestamp))

    # slot
    def on_mass(self, mass_single_event):
        self.status("Mass received: {}".format(mass_single_event))
        with session_thread_scope() as session:
            mass_identified_event = MassIdentifiedEvent.record_mass_detection(
                session, mass_single_event, self.rfid_effective_time_s)
            if mass_identified_event:
                reader_name = RfidConfig.get_name_from_id(
                    session, mass_identified_event.reader_id)
                balance_name = BalanceConfig.get_name_from_id(
                    session, mass_identified_event.balance_id)
                self.broadcast(
                    "reader {}, RFID {}, balance {}, mass {} kg, at {}".format(
                        reader_name,
                        mass_identified_event.rfid,
                        balance_name,
                        mass_identified_event.mass_kg,
                        mass_identified_event.at))
            else:
                self.debug("Mass measurement not identifiable to a subject")
