from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    district = Column(String, index=True)
    sensor_type = Column(String, index=True)
    value = Column(Float)
    unit = Column(String)
    severity = Column(String, index=True)
    timestamp = Column(String)
    topic = Column(String)
    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
    )

class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    source_district = Column(String, index=True)
    target_district = Column(String, index=True)
    action_type = Column(String, index=True)
    reason = Column(String)
    event_snapshot = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
    )