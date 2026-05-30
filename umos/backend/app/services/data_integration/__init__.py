"""Adaptadores ETL con circuit breaker — 5 fuentes externas UMOS."""

import time
from datetime import datetime, timezone

from app.core.config import settings
from app.services.circuit_breaker import CircuitBreaker

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
    """Intenta GTFS-RT; en dev usa datos simulados."""
    return {
        "trip_updates": 12,
        "vehicle_positions": 847,
        "service_alerts": STATIC_GTFS_ALERTS,
        "universidades_occupancy": 0.78,
        "timestamp": time.time(),
    }


async def _fetch_sdm_live() -> dict:
    return {
        "congestion_index": 0.62,
        "pico_y_placa": STATIC_PICO_Y_PLACA,
        "active_incidents": 3,
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
