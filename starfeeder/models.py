#!/usr/bin/env python
# starfeeder/models.py

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

import datetime
import logging
import serial
from typing import Any, Dict, List, Optional

import arrow
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.session import Session
from whisker.sqlalchemy import (
    ALEMBIC_NAMING_CONVENTION,
    SqlAlchemyAttrDictMixin,
    ArrowMicrosecondType,
)
from whisker.lang import (
    ordered_repr,
    simple_repr,
    trunc_if_integer,
)

from starfeeder.constants import DEFAULT_BALANCE_READ_FREQUENCY_HZ

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_GENERIC_STRING_LENGTH = 255

# =============================================================================
# SQLAlchemy base.
# =============================================================================
# Derived classes will share the specified metadata.

MASTER_META = MetaData(naming_convention=ALEMBIC_NAMING_CONVENTION)
Base = declarative_base(metadata=MASTER_META)


# =============================================================================
# Mixin: serial port config
# =============================================================================
# http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html

class SerialPortConfigMixin(object):
    # Note that defaults apply at insertion. So a class constructed within
    # Python doesn't have defaults set (until you save AND RELOAD somehow),
    # so we are better off using the __init__ function for defaults.
    # The __init__ function is free-form:
    # http://docs.sqlalchemy.org/en/rel_0_8/orm/mapper_config.html#constructors-and-object-initialization  # noqa
    port = Column(String(MAX_GENERIC_STRING_LENGTH))
    baudrate = Column(Integer)
    bytesize = Column(Integer)
    parity = Column(String(length=1))
    stopbits = Column(Float)
    xonxoff = Column(Boolean)
    rtscts = Column(Boolean)
    dsrdtr = Column(Boolean)

    def __init__(self,
                 port: str = '',
                 baudrate: int = 9600,
                 bytesize: int = serial.EIGHTBITS,
                 parity: str = serial.PARITY_NONE,
                 stopbits: float = serial.STOPBITS_ONE,
                 xonxoff: bool = False,
                 rtscts: bool = True,
                 dsrdtr: bool = False,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.xonxoff = xonxoff
        self.rtscts = rtscts
        self.dsrdtr = dsrdtr

    @staticmethod
    def fields_component_serial_port() -> List[str]:
        return ['port', 'bytesize', 'parity', 'stopbits',
                'xonxoff', 'rtscts', 'dsrdtr']

    def str_component_serial_port(self) -> str:
        flowmethods = []
        if self.xonxoff:
            flowmethods.append("XON/OFF")
        if self.rtscts:
            flowmethods.append("RTS/CTS")
        if self.dsrdtr:
            flowmethods.append("DTR/DSR")
        if flowmethods:
            flow = "+".join(flowmethods)
        else:
            flow = "no flow control"
        return "{port}, {speed} {bits}{parity}{stop}, {flow}".format(
            port=self.port,
            speed=self.baudrate,
            bits=self.bytesize,
            parity=self.parity,
            stop=trunc_if_integer(self.stopbits),
            flow=flow,
        )

    def get_serial_args(self) -> Dict[str, Any]:
        return dict(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            xonxoff=self.xonxoff,
            rtscts=self.rtscts,
            dsrdtr=self.dsrdtr,
        )


# =============================================================================
# RFID reader
# =============================================================================

class RfidReaderConfig(SqlAlchemyAttrDictMixin, SerialPortConfigMixin, Base):
    __tablename__ = 'rfidreader_config'
    id = Column(Integer, primary_key=True)
    master_config_id = Column(Integer, ForeignKey('master_config.id'))
    name = Column(String(MAX_GENERIC_STRING_LENGTH))
    enabled = Column(Boolean)

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.pop('name', '')
        self.master_config_id = kwargs.pop('master_config_id')
        self.enabled = kwargs.pop('enabled', True)
        kwargs.setdefault('baudrate', 9600)
        kwargs.setdefault('bytesize', serial.EIGHTBITS)
        kwargs.setdefault('parity', serial.PARITY_NONE)
        kwargs.setdefault('stopbits', serial.STOPBITS_ONE)
        kwargs.setdefault('xonxoff', False)
        kwargs.setdefault('rtscts', False)  # works under Linux, not Windows
        kwargs.setdefault('dsrdtr', False)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return ordered_repr(
            self,
            ['id', 'master_config_id', 'name', 'enabled'] +
            self.fields_component_serial_port())

    def __str__(self) -> str:
        return "{}{}: {}".format(
            "[DISABLED] " if not self.enabled else "",
            self.name or "[no name]",
            self.str_component_serial_port())

    # noinspection PyShadowingBuiltins
    @classmethod
    def get_name_from_id(cls, session: Session, id: int) -> Optional[str]:
        obj = session.query(cls).get(id)
        if obj is None:
            return None
        return obj.name


# =============================================================================
# Balance
# =============================================================================

class CalibrationReport(object):
    def __init__(self,
                 balance_id: int,
                 balance_name: str,
                 zero_value: int,
                 refload_value: int,
                 refload_mass_kg: float) -> None:
        self.balance_id = balance_id
        self.balance_name = balance_name
        self.zero_value = zero_value
        self.refload_value = refload_value
        self.refload_mass_kg = refload_mass_kg

    def __str__(self) -> str:
        return (
            "Calibrated balance {}: zero value = {}, "
            "loaded value = {} (at {} kg)".format(
                self.balance_name, self.zero_value,
                self.refload_value, self.refload_mass_kg))


class BalanceConfig(SqlAlchemyAttrDictMixin, SerialPortConfigMixin, Base):
    __tablename__ = 'balance_config'
    id = Column(Integer, primary_key=True)
    master_config_id = Column(Integer, ForeignKey('master_config.id'))
    reader_id = Column(Integer, ForeignKey('rfidreader_config.id'))
    name = Column(String(MAX_GENERIC_STRING_LENGTH))
    enabled = Column(Boolean)
    measurement_rate_hz = Column(Integer)
    stability_n = Column(Integer)
    tolerance_kg = Column(Float)
    min_mass_kg = Column(Float)
    unlock_mass_kg = Column(Float)
    refload_mass_kg = Column(Float)
    zero_value = Column(Integer)
    refload_value = Column(Integer)
    read_continuously = Column(Boolean)
    amp_signal_filter_mode = Column(Integer)
    fast_response_filter = Column(Boolean)

    # One-to-one relationship:
    reader = relationship("RfidReaderConfig",
                          backref=backref("balance", uselist=False))

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.pop('name', '')
        self.master_config_id = kwargs.pop('master_config_id')
        self.enabled = kwargs.pop('enabled', True)
        self.measurement_rate_hz = kwargs.pop(
            'measurement_rate_hz', DEFAULT_BALANCE_READ_FREQUENCY_HZ)
        self.stability_n = kwargs.pop('stability_n', 5)
        self.tolerance_kg = kwargs.pop('tolerance_kg', 0.005)
        self.min_mass_kg = kwargs.pop('min_mass_kg', 0.050)
        self.unlock_mass_kg = kwargs.pop('unlock_mass_kg', 0.010)
        self.refload_mass_kg = kwargs.pop('refload_mass_kg', 0.1)
        self.read_continuously = kwargs.pop('read_continuously', False)
        self.amp_signal_filter_mode = kwargs.pop('amp_signal_filter_mode', 0)
        self.fast_response_filter = kwargs.pop('fast_response_filter', False)
        kwargs.setdefault('baudrate', 9600)
        kwargs.setdefault('bytesize', serial.EIGHTBITS)
        kwargs.setdefault('parity', serial.PARITY_EVEN)
        kwargs.setdefault('stopbits', serial.STOPBITS_ONE)
        kwargs.setdefault('xonxoff', True)  # p15
        kwargs.setdefault('rtscts', False)
        kwargs.setdefault('dsrdtr', False)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return ordered_repr(
            self,
            ['id', 'master_config_id', 'reader_id', 'name',
             'enabled', 'measurement_rate_hz', 'stability_n',
             'tolerance_kg', 'min_mass_kg', 'unlock_mass_kg',
             'refload_mass_kg', 'zero_value', 'refload_value',
             'read_continuously'
             ] + self.fields_component_serial_port())

    def __str__(self) -> str:
        return "{}{}: {}".format(
            "[DISABLED] " if not self.enabled else "",
            self.name or "[no name]",
            self.str_component_serial_port())

    # noinspection PyShadowingBuiltins
    @classmethod
    def get_name_from_id(cls, session: Session, id: int) -> Optional[str]:
        obj = session.query(cls).get(id)
        if obj is None:
            return None
        return obj.name


# =============================================================================
# Program configuration
# =============================================================================

class MasterConfig(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'master_config'

    id = Column(Integer, primary_key=True)
    name = Column(String(MAX_GENERIC_STRING_LENGTH))
    modified_at = Column(ArrowMicrosecondType, default=arrow.now,
                         onupdate=arrow.now)
    server = Column(String(MAX_GENERIC_STRING_LENGTH))
    port = Column(Integer)
    wcm_prefix = Column(String(MAX_GENERIC_STRING_LENGTH))
    rfid_effective_time_s = Column(Float)
    rfidreader_configs = relationship("RfidReaderConfig")
    balance_configs = relationship("BalanceConfig")

    def __init__(self, **kwargs) -> None:
        self.server = kwargs.pop('server', 'localhost')
        self.port = kwargs.pop('port', 3233)
        self.wcm_prefix = kwargs.pop('wcm_prefix', 'starfeeder')
        self.rfid_effective_time_s = kwargs.pop('rfid_effective_time_s', 5.0)

    @classmethod
    def get_latest_or_create(cls, session: Session) -> 'MasterConfig':
        config = session.query(cls).order_by(cls.modified_at.desc()).first()
        if config is None:
            config = cls()
            session.add(config)
        return config

    @classmethod
    def get_singleton(cls, session: Session,
                      singleton_pk: int = 1) -> 'MasterConfig':
        config = session.query(cls).get(singleton_pk)
        if config is None:
            config = cls(id=singleton_pk)
            session.add(config)
        return config


# =============================================================================
# RFID detected
# =============================================================================

class RfidEvent(object):
    """
    This is NOT a database object; it's a simple Python object to get passed
    around between threads (we can't use raw Python numbers for this because
    we have to pass around a 64-bit integer).
    It represents a SINGLE detection event of an RFID.
    This is not of much behavioural interest, or interest for recording, since
    dozens of these get generated in a very short space of time.
    What is of more behavioural interest is the RfidEventRecord, below.
    """
    def __init__(self,
                 reader_id: int, reader_name: str,
                 rfid: int, timestamp: arrow.Arrow) -> None:
        self.reader_id = reader_id
        self.reader_name = reader_name
        self.rfid = rfid
        self.timestamp = timestamp

    def __repr__(self) -> str:
        return simple_repr(self)


# =============================================================================
# RFID recording class, glossing over irrelevant duplication
# =============================================================================

class RfidEventRecord(SqlAlchemyAttrDictMixin, Base):
    """
    See rfid.py for a discussion of the RFID tag format.
    Upshot: it'll fit into a 64-bit integer, so we use BigInteger.
    """
    __tablename__ = 'rfid_event'
    id = Column(Integer, primary_key=True)
    reader_id = Column(Integer, ForeignKey('rfidreader_config.id'))
    rfid = Column(BigInteger)
    first_detected_at = Column(ArrowMicrosecondType, default=arrow.now)
    last_detected_at = Column(ArrowMicrosecondType, default=arrow.now)
    n_events = Column(Integer, default=1)

    @classmethod
    def get_ongoing_event_by_reader_rfid(
            cls, session: Session, reader_id: int, rfid: int, now: arrow.Arrow,
            rfid_effective_time_s: float) -> 'RfidEventRecord':
        """Used for RFID recording. Matches reader and RFID."""
        most_recent_of_interest = (
            now - datetime.timedelta(seconds=rfid_effective_time_s)
        )
        return (
            session.query(cls).filter(
                cls.reader_id == reader_id,
                cls.rfid == rfid,
                cls.last_detected_at >= most_recent_of_interest
            ).first()  # There should be no more than one!
        )

    @classmethod
    def record_rfid_detection(
            cls, session: Session, rfid_single_event: RfidEvent,
            rfid_effective_time_s: float) -> None:
        if not isinstance(rfid_single_event, RfidEvent):
            log.critical("Bad rfid_event: {}".format(rfid_single_event))
            return
        reader_id = rfid_single_event.reader_id
        event = cls.get_ongoing_event_by_reader_rfid(
            session,
            reader_id,
            rfid_single_event.rfid,
            rfid_single_event.timestamp,
            rfid_effective_time_s)
        if event:  # one exists already
            event.last_detected_at = rfid_single_event.timestamp
            event.n_events += 1
        else:  # make a new one
            event = cls(
                reader_id=reader_id,
                rfid=rfid_single_event.rfid,
                first_detected_at=rfid_single_event.timestamp,
                last_detected_at=rfid_single_event.timestamp,
                n_events=1,
            )
            session.add(event)
        session.commit()  # ASAP to unlock database


# While a free-floating ID at a particular reader may be of interest,
# a free-floating mass with no ID attached is not of interest.


# =============================================================================
# Raw mass from balance; not a database object
# =============================================================================

class MassEvent(object):
    def __init__(self,
                 balance_id: int, balance_name: str,
                 reader_id: int, reader_name: str,
                 rfid: int, mass_kg: float,
                 timestamp: arrow.Arrow, stable: bool, locked: bool) -> None:
        self.balance_id = balance_id
        self.balance_name = balance_name
        self.reader_id = reader_id
        self.reader_name = reader_name
        self.rfid = rfid
        self.mass_kg = mass_kg
        self.timestamp = timestamp
        self.stable = stable
        self.locked = locked

    def __repr__(self) -> str:
        return simple_repr(self)

    def __str__(self) -> str:
        return "Balance {}: {} kg (RFID: {})".format(
            self.balance_id, self.mass_kg, self.rfid)


# =============================================================================
# Mass detected from a specific RFID-identified individual
# =============================================================================

class MassEventRecord(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'mass_event'

    id = Column(Integer, primary_key=True)
    # Who?
    rfid = Column(BigInteger)
    # Where?
    reader_id = Column(Integer, ForeignKey('rfidreader_config.id'))
    balance_id = Column(Integer, ForeignKey('balance_config.id'))
    # When? (Default precision is microseconds, even on SQLite.)
    at = Column(ArrowMicrosecondType, default=arrow.now)
    # ... avoid 'timestamp' as a column name; it's an SQL keyword (adds hassle)
    # How heavy?
    mass_kg = Column(Float)

    @classmethod
    def record_mass_detection(cls, session: Session,
                              mass_single_event: MassEvent) -> None:
        """Returns an OrderedNamespace object, not an SQLAlchemy ORM object."""
        if not isinstance(mass_single_event, MassEvent):
            log.critical("Bad mass_single_event: {}".format(mass_single_event))
            return
        balance_id = mass_single_event.balance_id
        # noinspection PyArgumentList
        mass_identified_event = MassEventRecord(
            rfid=mass_single_event.rfid,
            reader_id=mass_single_event.reader_id,
            balance_id=balance_id,
            at=mass_single_event.timestamp,
            mass_kg=mass_single_event.mass_kg,
        )
        session.add(mass_identified_event)
        session.commit()  # ASAP to unlock database
        # return mass_identified_event.get_attrdict()
