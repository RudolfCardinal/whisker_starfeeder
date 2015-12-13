#!/usr/bin/env python3
# weigh/models.py

import datetime
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import serial

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship

from weigh.lang import trunc_if_integer

# =============================================================================
# Constants for Alembic
# =============================================================================
# https://alembic.readthedocs.org/en/latest/naming.html

ALEMBIC_NAMING_CONVENTION = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # "ck": "ck_%(table_name)s_%(constraint_name)s",  # too long?
    # ... https://groups.google.com/forum/#!topic/sqlalchemy/SIT4D8S9dUg
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
MASTER_META = MetaData(naming_convention=ALEMBIC_NAMING_CONVENTION)

# =============================================================================
# Base
# =============================================================================
# Now we declare our SQLAlchemy base.
# Derived classes will share the specified metadata.

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
    port = Column(String)
    baudrate = Column(Integer)
    bytesize = Column(Integer)
    parity = Column(String(length=1))
    stopbits = Column(Float)
    xonxoff = Column(Boolean)
    rtscts = Column(Boolean)
    dsrdtr = Column(Boolean)

    def __init__(self, port='', baudrate=9600, bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                 xonxoff=False, rtscts=True, dsrdtr=False):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.xonxoff = xonxoff
        self.rtscts = rtscts
        self.dsrdtr = dsrdtr

    def repr_component_serial_port(self):
        return (
            "port={}, bytesize={}, parity={}, stopbits={}, "
            "xonxoff={}, rtscts={}, dsrdtr={}".format(
                repr(self.port), self.bytesize, self.parity,
                trunc_if_integer(self.stopbits),
                self.xonxoff, self.rtscts, self.dsrdtr,
            )
        )

    def str_component_serial_port(self):
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

    def get_serial_args(self):
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
# RFID
# =============================================================================

class RfidConfig(SerialPortConfigMixin, Base):
    __tablename__ = 'rfid_config'
    id = Column(Integer, primary_key=True)
    master_config_id = Column(Integer, ForeignKey('master_config.id'))
    name = Column(String)
    keep = Column(Boolean)
    enabled = Column(Boolean)

    def __init__(self, **kwargs):
        self.name = kwargs.pop('name', '')
        self.master_config_id = kwargs.pop('master_config_id')
        self.keep = kwargs.pop('keep', False)
        self.enabled = kwargs.pop('enabled', True)
        kwargs.setdefault('baudrate', 9600)
        kwargs.setdefault('bytesize', serial.EIGHTBITS)
        kwargs.setdefault('parity', serial.PARITY_NONE)
        kwargs.setdefault('stopbits', serial.STOPBITS_ONE)
        kwargs.setdefault('xonxoff', False)
        kwargs.setdefault('rtscts', True)
        kwargs.setdefault('dsrdtr', False)
        SerialPortConfigMixin.__init__(self, **kwargs)

    def __repr__(self):
        return "<RfidConfig(name={}, {})>".format(
            repr(self.name),
            self.repr_component_serial_port())

    def __str__(self):
        return "{}{}: {}".format(
            "[DISABLED] " if not self.enabled else "",
            self.name or "[no name]",
            self.str_component_serial_port())

    @classmethod
    def get_name_from_id(cls, session, id):
        obj = session.query(cls).get(id)
        if obj is None:
            return None
        return obj.name


# =============================================================================
# Balance
# =============================================================================

class BalanceConfig(SerialPortConfigMixin, Base):
    __tablename__ = 'balance_config'
    id = Column(Integer, primary_key=True)
    master_config_id = Column(Integer, ForeignKey('master_config.id'))
    reader_id = Column(Integer, ForeignKey('rfid_config.id'))
    name = Column(String)
    keep = Column(Boolean)
    enabled = Column(Boolean)

    # One-to-one relationship:
    reader = relationship("RfidConfig",
                          backref=backref("balance", uselist=False))

    def __init__(self, **kwargs):
        self.name = kwargs.pop('name', '')
        self.master_config_id = kwargs.pop('master_config_id')
        self.keep = kwargs.pop('keep', False)
        self.enabled = kwargs.pop('enabled', True)
        kwargs.setdefault('baudrate', 9600)
        kwargs.setdefault('bytesize', serial.EIGHTBITS)
        kwargs.setdefault('parity', serial.PARITY_EVEN)
        kwargs.setdefault('stopbits', serial.STOPBITS_ONE)
        kwargs.setdefault('xonxoff', True)
        kwargs.setdefault('rtscts', False)
        kwargs.setdefault('dsrdtr', False)
        SerialPortConfigMixin.__init__(self, **kwargs)

    def __repr__(self):
        return "<BalanceConfig(name={}, {})>".format(
            repr(self.name),
            self.repr_component_serial_port())

    def __str__(self):
        return "{}{}: {}".format(
            "[DISABLED] " if not self.enabled else "",
            self.name or "[no name]",
            self.str_component_serial_port())

    @classmethod
    def get_name_from_id(cls, session, id):
        obj = session.query(cls).get(id)
        if obj is None:
            return None
        return obj.name


# =============================================================================
# Program configuration
# =============================================================================

class MasterConfig(Base):
    __tablename__ = 'master_config'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)
    server = Column(String)
    port = Column(Integer)
    wcm_prefix = Column(String)
    rfid_effective_time_s = Column(Float)
    rfid_configs = relationship("RfidConfig")
    balance_configs = relationship("BalanceConfig")

    def __init__(self, **kwargs):
        self.server = kwargs.pop('server', 'localhost')
        self.port = kwargs.pop('port', 3233)
        self.wcm_prefix = kwargs.pop('wcm_prefix', 'starfeeder')
        self.rfid_effective_time_s = kwargs.pop('rfid_effective_time_s', 5.0)

    def __repr__(self):
        return (
            "<Config("
            "name={}, modified_at='{}', server={}, "
            "port={})>".format(
                repr(self.name), str(self.created_at), repr(self.server),
                self.port,
            )
        )

    @classmethod
    def get_latest_or_create(cls, session):
        config = session.query(cls).order_by(cls.modified_at.desc()).first()
        if config is None:
            config = cls()
            session.add(config)
        return config

    @classmethod
    def get_singleton(cls, session, singleton_pk=1):
        config = session.query(cls).get(singleton_pk)
        if config is None:
            config = cls(id=singleton_pk)
            session.add(config)
        return config


# =============================================================================
# RFID detected
# =============================================================================

class RfidSingleEvent(object):
    """
    This is NOT a database object; it's a simple Python object to get passed
    around between threads (we can't use raw Python numbers for this because
    we have to pass around a 64-bit integer).
    It represents a SINGLE detection event of an RFID.
    This is not of much behavioural interest, or interest for recording, since
    dozens of these get generated in a very short space of time.
    What is of more behavioural interest is the RfidEvent, below.
    """
    def __init__(self, reader_id, rfid, timestamp):
        self.reader_id = reader_id
        self.rfid = rfid
        self.timestamp = timestamp

    def __repr__(self):
        return (
            "<RfidSingleEvent(reader_id={}, rfid={}, timestamp='{}')>".format(
                self.reader_id, self.rfid, str(self.timestamp)))


# =============================================================================
# RFID recording class, glossing over irrelevant duplication
# =============================================================================

class RfidEvent(Base):
    """
    See rfid.py for a discussion of the RFID tag format.
    Upshot: it'll fit into a 64-bit integer, so we use BigInteger.
    """
    __tablename__ = 'rfid_event'
    id = Column(Integer, primary_key=True)
    reader_id = Column(Integer, ForeignKey('rfid_config.id'))
    rfid = Column(BigInteger)
    first_detected_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_detected_at = Column(DateTime, default=datetime.datetime.utcnow)
    n_events = Column(Integer, default=1)

    @classmethod
    def get_ongoing_event_by_reader_rfid(cls, session, reader_id, rfid, now,
                                         rfid_effective_time_s):
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
    def get_ongoing_event_at_reader(cls, session, reader_id, now,
                                    rfid_effective_time_s):
        """Used for mass recording. Looks up the RFID, which is unknown."""
        most_recent_of_interest = (
            now - datetime.timedelta(seconds=rfid_effective_time_s)
        )
        return (
            session.query(cls).filter(
                cls.reader_id == reader_id,
                cls.last_detected_at >= most_recent_of_interest
            ).first()  # There should be no more than one!
        )

    @classmethod
    def record_rfid_detection(cls, session, rfid_single_event,
                              rfid_effective_time_s):
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
            reader = session.query(RfidConfig).get(reader_id)
            reader.keep = True  # never delete it now
        session.commit()
        return event

    def __repr__(self):
        return (
            "<RfidEvent(reader_id={}, rfid={}, first_detected_at='{}', "
            "last_detected_at='{}', n_events={}".format(
                self.reader_id,
                self.rfid,
                str(self.first_detected_at),
                str(self.last_detected_at),
                self.n_events,
            )
        )


# While a free-floating ID at a particular reader may be of interest,
# a free-floating mass with no ID attached is not of interest.


# =============================================================================
# Raw mass from balance; not a database object
# =============================================================================

class MassSingleEvent(object):
    def __init__(self, balance_id, mass, units, timestamp):
        self.balance_id = balance_id
        self.mass = mass
        self.units = units
        self.timestamp = timestamp

    def get_kg(self):
        if self.units == "mg":
            return self.mass / 1000000
        elif self.units == "g":
            return self.mass / 1000
        elif self.units == "kg":
            return self.mass
        else:
            raise ValueError("Unknown mass units: {}".format(self.units))

    def __repr__(self):
        return (
            "<MassSingleEvent(balance_id={}, mass={}, units={}, "
            "timestamp='{}')>".format(
                self.balance_id, self.mass, self.units))

    def __str__(self):
        return "Balance {}: {} {} = {} kg".format(
            self.balance_id, self.mass, self.units, self.get_kg())


# =============================================================================
# Mass detected from a specific RFID-identified individual
# =============================================================================

class MassIdentifiedEvent(Base):
    __tablename__ = 'mass_event'

    id = Column(Integer, primary_key=True)
    # Who?
    rfid = Column(BigInteger)
    # Where?
    reader_id = Column(Integer, ForeignKey('rfid_config.id'))
    balance_id = Column(Integer, ForeignKey('balance_config.id'))
    # When? (Default precision is microseconds, even on SQLite.)
    at = Column(DateTime, default=datetime.datetime.utcnow)
    # ... avoid 'timestamp' as a column name; it's an SQL keyword (adds hassle)
    # How heavy?
    mass_kg = Column(Float)

    def __repr__(self):
        return (
            "<Weight("
            "id={}, reader={}, rfid='{}', at='{}', "
            "mass={}, units='{}', mass_kg={})>".format(
                self.id, self.reader, self.rfid, self.at,
                self.mass, self.units, self.mass_kg,
            )
        )

    @classmethod
    def record_mass_detection(cls, session, mass_single_event,
                              rfid_effective_time_s):
        balance_id = mass_single_event.balance_id
        balance = session.query(BalanceConfig).get(balance_id)
        if balance is None:
            logger.critical("No such balance ID {}".format(balance_id))
            return None
        if balance.reader is None:
            logger.critical("Balance {} has no RFID reader paired".format(
                mass_single_event.balance_id))
            return None
        reader_id = balance.reader.id
        rfid_event = RfidEvent.get_ongoing_event_at_reader(
            session,
            reader_id,
            mass_single_event.timestamp,
            rfid_effective_time_s)
        if rfid_event is None:
            # No RFID has been detected on the balance's RFID reader recently.
            return None
        mass_identified_event = MassIdentifiedEvent(
            rfid=rfid_event.rfid,
            reader_id=reader_id,
            balance_id=mass_single_event.balance_id,
            at=mass_single_event.timestamp,
            mass_kg=mass_single_event.get_kg(),
        )
        session.add(mass_identified_event)
        balance.keep = True  # never delete it now
        session.commit()
        return mass_identified_event
