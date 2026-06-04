from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class LatLng(BaseModel):
    lat: float
    lng: float


class RoutePreferences(BaseModel):
    avoid_rain_modes: bool = True
    max_transfers: int = 3
    equity_mode: bool = False


class ComputeRouteRequest(BaseModel):
    """Contrato API spec POST /api/v1/routes/compute."""
    origin: LatLng | None = None
    destination: LatLng | None = None
    origin_id: int | None = None
    destination_id: int | None = None
    departure_time: datetime | None = None
    preferences: RoutePreferences = Field(default_factory=RoutePreferences)
    rain_intensity: float | None = None
transport_mode: Literal["driving", "transit", "sitp", "tm", "cycling", "walking"] = "transit"


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
    traffic_events: list[str] = []


class Segment(BaseModel):
    mode: str
    from_name: str
    to_name: str
    duration_min: float
    distance_km: float
    cost_cop: int = 0
    geometry: list[list[float]] = []
    icon: str = ""
    instruction: str = ""
    color: str = "#64748b"


class ETAConfidence(BaseModel):
    lower: float
    upper: float


class RouteVariant(BaseModel):
    label: str
    total_time: float
    total_distance: float
    total_cost_cop: int = 0
    cost_per_km: float = 0
    transfers: int = 0
    transport_modes: list[str]
    modes_used: list[str] = []
    steps: list[RouteStep]
    segments: list[Segment] = []
    geometry: list[list[float]]
    path: list[int] = []
    eta_confidence_interval: ETAConfidence | None = None
    weather_adjusted: bool = False
    equity_level: str = "green"
    aco_score: float = 0.0


class RouteAlternative(RouteVariant):
    index: int
    score: float


class ACOMetadata(BaseModel):
    iterations: int
    convergence_step: int
    pheromone_snapshot: dict[str, float] = {}


class ComputeRouteResponse(BaseModel):
    optimal_route: RouteVariant
    alternatives: list[RouteVariant] = []
    computation_time_ms: float
    aco_metadata: ACOMetadata
    rain_penalty_applied: bool = False
    equity_alert: str | None = None


class RouteResponse(BaseModel):
    origin: str
    destination: str
    transport_mode: str
    selected: RouteVariant
    alternatives: list[RouteVariant] = []
    active_traffic_events: list[dict] = []
    aco_iterations: int
    rain_penalty_applied: bool
    computation_time_ms: float = 0
    aco_metadata: ACOMetadata | None = None
    equity_alert: str | None = None
