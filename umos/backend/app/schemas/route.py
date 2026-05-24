from pydantic import BaseModel
from typing import Literal


class RouteRequest(BaseModel):
    origin_id: int
    destination_id: int
    mode: Literal["fastest", "shortest", "eco"] = "fastest"
    transport_mode: Literal["driving", "transit", "cycling", "walking"] = "driving"
    rain: bool = False


class RouteStep(BaseModel):
    campus_id: int
    campus_name: str
    latitude: float
    longitude: float
    transport: str
    cumulative_time: float
    cumulative_distance: float
    traffic_factor: float = 1.0


class RouteVariant(BaseModel):
    label: str
    total_time: float
    total_distance: float
    transport_modes: list[str]
    steps: list[RouteStep]
    geometry: list[list[float]]
    path: list[int]


class RouteResponse(BaseModel):
    origin: str
    destination: str
    total_time: float
    total_distance: float
    transport_modes: list[str]
    steps: list[RouteStep]
    selected: RouteVariant
    alternatives: list[RouteVariant] = []
    active_traffic_events: list[dict] = []
    aco_iterations: int
    rain_penalty_applied: bool
