from sqlalchemy import Column, Integer, String, Float, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Campus(Base):
    __tablename__ = "campuses"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    code        = Column(String(20), unique=True, nullable=False)
    address     = Column(String(200))
    latitude    = Column(Float, nullable=False)
    longitude   = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    origin_edges = relationship(
        "RouteEdge", back_populates="origin",
        foreign_keys="RouteEdge.origin_id"
    )
    dest_edges = relationship(
        "RouteEdge", back_populates="destination",
        foreign_keys="RouteEdge.dest_id"
    )