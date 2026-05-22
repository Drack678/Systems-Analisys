from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class RouteEdge(Base):
    """Arista dirigida entre dos nodos del grafo de movilidad."""
    __tablename__ = "route_edges"

    id          = Column(Integer, primary_key=True, index=True)
    origin_id   = Column(Integer, ForeignKey("campuses.id"), nullable=False)
    dest_id     = Column(Integer, ForeignKey("campuses.id"), nullable=False)
    distance_km = Column(Float, nullable=False)
    travel_time = Column(Float, nullable=False)   # minutos en condición normal
    transport   = Column(String(30), default="SITP")  # SITP | TM | BIKE | WALK | CABLE
    pheromone   = Column(Float, default=1.0)           # nivel de feromona ACO

    origin = relationship(
        "Campus", back_populates="origin_edges", foreign_keys=[origin_id]
    )
    destination = relationship(
        "Campus", back_populates="dest_edges", foreign_keys=[dest_id]
    )