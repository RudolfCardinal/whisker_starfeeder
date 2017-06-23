#!/usr/bin/env python
# starfeeder/task.py

"""
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

import logging

import arrow
# from whisker.debug_qt import debug_object
from whisker.sqlalchemy import session_thread_scope
from whisker.qt import exit_on_exception
from whisker.qtclient import WhiskerTask

from PyQt5.QtCore import QObject, pyqtSlot
from starfeeder.models import (
    MassEvent,  # for type hints
    MassEventRecord,
    MasterConfig,
    RfidEvent,  # for type hints
    RfidEventRecord,
)
from starfeeder.settings import get_database_settings
from starfeeder.version import VERSION

log = logging.getLogger(__name__)


class WeightWhiskerTask(WhiskerTask):  # Whisker thread B
    """Doesn't define an end, deliberately."""

    def __init__(self, wcm_prefix: str = "", parent: QObject = None,
                 name: str = "whisker_task", **kwargs) -> None:
        super().__init__(parent=parent, name=name, **kwargs)
        self.wcm_prefix = wcm_prefix
        self.dbsettings = get_database_settings()
        self.rfid_effective_time_s = None

    @pyqtSlot()
    def thread_started(self) -> None:
        with session_thread_scope(self.dbsettings) as session:
            config = MasterConfig.get_singleton(session)
            self.rfid_effective_time_s = config.rfid_effective_time_s

    @pyqtSlot()
    @exit_on_exception
    def on_connect(self) -> None:
        # self.debug("DERIVED on_connect")
        # debug_object(self)
        # self.whisker.command("TimerSetEvent 2000 5 bop")
        self.whisker.report_name("Starfeeder {}".format(VERSION))

    @pyqtSlot(str, arrow.Arrow, int)
    @exit_on_exception
    def on_event(self, event, timestamp, whisker_timestamp_ms):
        pass
        # if event == "bop":
        #     self.status("boop")

    def broadcast(self, msg: str) -> None:
        if self.wcm_prefix:
            msg = "{}{}".format(self.wcm_prefix, msg)
        self.whisker.broadcast(msg)

    @pyqtSlot(RfidEvent)
    @exit_on_exception
    def on_rfid(self, rfid_event: RfidEvent) -> None:
        """
        Record an RFID event.

        Since this task runs in a non-GUI thread, it's a good place to do the
        main RFID processing.

        Only one thread should be writing to the database, to avoid locks.

        Don't hold the session too long, on general principles.
        """
        if not isinstance(rfid_event, RfidEvent):
            log.critical("Bad rfid_event: {}".format(rfid_event))
            return
        with session_thread_scope(self.dbsettings) as session:
            RfidEventRecord.record_rfid_detection(
                session, rfid_event, self.rfid_effective_time_s)
        # self.status("RFID received: {}".format(rfid_event))
        if self.whisker.is_connected():
            self.broadcast(
                "RFID_EVENT: reader {reader}, RFID {rfid}, "
                "timestamp {timestamp}".format(
                    rfid=rfid_event.rfid,
                    reader=rfid_event.reader_name,
                    timestamp=rfid_event.timestamp,
                )
            )

    @pyqtSlot(MassEvent)
    @exit_on_exception
    def on_mass(self, mass_event: MassEvent) -> None:
        """
        Receive a mass event. Ask the MassIdentifiedEvent class to work out if
        it represents an identified mass event (and store it, if so).
        Broadcast the information to the Whisker client.
        """
        if not isinstance(mass_event, MassEvent):
            log.critical("Bad mass_event: {}".format(mass_event))
            return
        if not mass_event.locked or mass_event.rfid is None:
            return
        with session_thread_scope(self.dbsettings) as session:
            MassEventRecord.record_mass_detection(session, mass_event)
        if self.whisker.is_connected():
            self.broadcast(
                "MASS_EVENT: reader {reader}, RFID {rfid}, balance {balance}, "
                "mass {mass_kg} kg, timestamp {timestamp}".format(
                    reader=mass_event.reader_name,
                    rfid=mass_event.rfid,
                    balance=mass_event.balance_name,
                    mass_kg=mass_event.mass_kg,
                    timestamp=mass_event.timestamp,
                )
            )
