from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TrafficType = Literal[
    "PROTEST",
    "ACCIDENT",
    "MINOR_CRASH",
    "ROAD_CLOSED",
    "CONGESTION",
    "RAIN",
]
TrafficSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class TrafficEventCreate(BaseModel):
    event_type: TrafficType = "CONGESTION"
    severity: TrafficSeverity = "MEDIUM"
    latitude: float
    longitude: float
    radius_m: int = Field(default=500, ge=50, le=5000)
    description: str | None = None


class TrafficEventResponse(TrafficEventCreate):
    id: int
    delay_factor: float
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
