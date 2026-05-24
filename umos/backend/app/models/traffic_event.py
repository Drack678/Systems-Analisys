from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.database import Base


class TrafficEvent(Base):
    """User-created or simulated traffic incident in Bogota."""

    __tablename__ = "traffic_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(30), nullable=False, default="CONGESTION")
    severity = Column(String(20), nullable=False, default="MEDIUM")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Integer, nullable=False, default=500)
    description = Column(Text, nullable=True)
    delay_factor = Column(Float, nullable=False, default=1.5)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
