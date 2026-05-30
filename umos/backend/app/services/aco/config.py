from dataclasses import dataclass
from app.core.config import settings


@dataclass
class ACOConfig:
    """Parámetros ACO calibrados con datos W1/W4."""
    n_ants: int = 50
    n_iterations: int = 100
    n_best: int = 5
    alpha: float = 1.0
    beta: float = 2.0
    evaporation: float = 0.1
    min_pheromone: float = 0.01
    Q: float = 100.0
    rain_multiplier: float = 1.63
    rain_threshold_mmh: float = 2.0
    bus_bunching_beta: float = 1.8
    congestion_threshold: float = 0.75

    @classmethod
    def from_settings(cls) -> "ACOConfig":
        return cls(
            n_ants=settings.ACO_N_ANTS,
            n_iterations=settings.ACO_MAX_ITERATIONS,
            alpha=settings.ACO_ALPHA,
            beta=settings.ACO_BETA,
            evaporation=settings.ACO_RHO,
            rain_multiplier=settings.ACO_RAIN_MULTIPLIER,
            rain_threshold_mmh=settings.ACO_RAIN_THRESHOLD_MMH,
        )
