"""Adaptadores ETL con circuit breaker — 5 fuentes externas UMOS."""

import time
from datetime import datetime, timezone

from app.core.config import settings
from app.services.circuit_breaker import CircuitBreaker

# ─── Estado de simulación de tráfico ───
# Se modifica desde el endpoint POST /api/v1/dashboard/simulate.
# Aplica multiplicadores temporales sobre los datos baseline.
_simulation_state = {
    "mode": "clear",  # peak | rain | incident | clear
    "started_at": 0.0,
}


def set_simulation_mode(mode: str) -> None:
    """Cambia el modo de simulación. Llamado desde el endpoint."""
    if mode in ("peak", "rain", "incident", "clear"):
        _simulation_state["mode"] = mode
        _simulation_state["started_at"] = time.time()


def get_simulation_mode() -> str:
    return _simulation_state["mode"]


# Multiplicadores por modo. Pueden ajustarse para más drama visual.
SIM_MULTIPLIERS = {
    "clear":    {"occupancy": 0.45, "congestion": 0.35, "buses": 1.0},
    "peak":     {"occupancy": 0.92, "congestion": 0.88, "buses": 1.15},
    "rain":     {"occupancy": 0.80, "congestion": 0.95, "buses": 0.85},
    "incident": {"occupancy": 0.65, "congestion": 0.98, "buses": 0.70},
}

# ── Fixtures estáticos (desarrollo / fallback) ───────────────────────────────
STATIC_GTFS_ALERTS = [
    {"id": "A1", "route": "B74", "effect": "DELAY", "description": "Demora en Av. Caracas"},
]

STATIC_PICO_Y_PLACA = {
    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "restricted_last_digits": [1, 2],
    "hours": "06:00-21:00",
    "zone": "Bogotá",
}

STATIC_IDU_CLOSURES = [
    {"id": "IDU-001", "street": "Av. El Dorado", "status": "partial", "lat": 4.651, "lng": -74.078},
]

STATIC_UDFJC_SCHEDULE = {
    "peak_windows": ["07:00", "08:00"],
    "classes_starting_0700_pct": 0.42,
    "classes_starting_0800_pct": 0.26,
    "demand_spike_factor": 1.35,
}


async def _fetch_transmilenio_live() -> dict:
    """Intenta GTFS-RT; en dev usa datos simulados modulados por el modo activo."""
    mult = SIM_MULTIPLIERS.get(_simulation_state["mode"], SIM_MULTIPLIERS["clear"])
    # Variación natural ±5% para que la gráfica nunca sea totalmente plana
    import random
    jitter = random.uniform(-0.03, 0.03)
    return {
        "trip_updates": 12,
        "vehicle_positions": int(847 * mult["buses"]),
        "service_alerts": STATIC_GTFS_ALERTS,
        "universidades_occupancy": round(max(0.05, min(0.99, mult["occupancy"] + jitter)), 3),
        "timestamp": time.time(),
    }


async def _fetch_sdm_live() -> dict:
    mult = SIM_MULTIPLIERS.get(_simulation_state["mode"], SIM_MULTIPLIERS["clear"])
    import random
    jitter = random.uniform(-0.04, 0.04)
    return {
        "congestion_index": round(max(0.05, min(0.99, mult["congestion"] + jitter)), 3),
        "pico_y_placa": STATIC_PICO_Y_PLACA,
        "active_incidents": 3 if _simulation_state["mode"] != "incident" else 7,
        "timestamp": time.time(),
    }


async def _fetch_ideam_live() -> dict:
    """IDEAM real requiere clave; sin ella usamos OpenWeather como proxy de lluvia."""
    from app.services.weather_service import get_current_rain

    weather = await get_current_rain()
    rain = weather.get("rain_mm", 0.0)
    return {
        "rain_mmh": rain,
        "forecast_30min_mmh": rain * 0.8 if rain > 0 else 0.5,
        "grid_point": {"lat": 4.711, "lng": -74.072},
        "source": "openweather" if settings.OPENWEATHER_API_KEY else "mock",
        "timestamp": time.time(),
    }


async def _fetch_idu_live() -> dict:
    return {"closures": STATIC_IDU_CLOSURES, "timestamp": time.time()}


async def _fetch_udfjc_live() -> dict:
    return {**STATIC_UDFJC_SCHEDULE, "timestamp": time.time()}


async def get_transmilenio_data() -> dict:
    cb = CircuitBreaker("transmilenio")
    return await cb.call(_fetch_transmilenio_live, lambda: {
        "trip_updates": 0,
        "vehicle_positions": 0,
        "service_alerts": STATIC_GTFS_ALERTS,
        "universidades_occupancy": 0.5,
        "timestamp": time.time(),
    })


async def get_sdm_data() -> dict:
    cb = CircuitBreaker("sdm")
    return await cb.call(_fetch_sdm_live, lambda: {
        "congestion_index": 0.5,
        "pico_y_placa": STATIC_PICO_Y_PLACA,
        "active_incidents": 0,
        "timestamp": time.time(),
    })


async def get_ideam_data() -> dict:
    cb = CircuitBreaker("ideam")
    return await cb.call(_fetch_ideam_live, lambda: {
        "rain_mmh": 0.0,
        "forecast_30min_mmh": 0.0,
        "grid_point": {"lat": 4.711, "lng": -74.072},
        "timestamp": time.time(),
    })


async def get_idu_data() -> dict:
    cb = CircuitBreaker("idu")
    return await cb.call(_fetch_idu_live, lambda: {
        "closures": STATIC_IDU_CLOSURES,
        "timestamp": time.time(),
    })


async def get_udfjc_data() -> dict:
    cb = CircuitBreaker("udfjc")
    return await cb.call(_fetch_udfjc_live, lambda: STATIC_UDFJC_SCHEDULE)


async def get_all_freshness() -> list[dict]:
    sources = [
        ("transmilenio", get_transmilenio_data),
        ("sdm", get_sdm_data),
        ("ideam", get_ideam_data),
        ("idu", get_idu_data),
        ("udfjc", get_udfjc_data),
    ]
    result = []
    for name, fn in sources:
        try:
            resp = await fn()
            result.append({
                "source": name,
                "age_seconds": resp.get("age_seconds", 0),
                "stale": resp.get("stale", False),
                "circuit_state": resp.get("circuit_state", "closed"),
            })
        except Exception:
            result.append({
                "source": name,
                "age_seconds": None,
                "stale": True,
                "circuit_state": "open",
            })
    return result
