"""Métricas de equidad — costo/km y brecha Norte vs Sur (W1: 38.5%)."""

from app.models.campus import Campus

FARE_COP = {
    "TM": 3550,
    "SITP": 2800,
    "CABLE": 3550,
    "BIKE": 0,
    "WALK": 0,
    "CAR": 0,
    "transmilenio": 3550,
    "sitp": 2800,
    "walking": 0,
    "cycling": 0,
    "driving": 0,
}

SOUTHERN_LOCALITIES = frozenset({
    "Bosa", "Ciudad Bolívar", "Kennedy", "Usme", "San Cristóbal",
})
NORTHERN_LOCALITIES = frozenset({
    "Suba", "Usaquén", "Chapinero", "Teusaquillo",
})

EQUITY_GAP_BASELINE = 0.385  # W4 measured gap Norte vs Sur


def detect_zone(campus: Campus) -> str:
    desc = (campus.description or "").strip()
    if desc in SOUTHERN_LOCALITIES or campus.latitude < 4.59:
        return "Sur"
    if desc in NORTHERN_LOCALITIES or campus.latitude > 4.65:
        return "Norte"
    if campus.longitude > -74.05:
        return "Este"
    return "Centro"


def segment_cost_cop(transport: str, distance_km: float) -> int:
    key = (transport or "SITP").upper()
    base = FARE_COP.get(key, FARE_COP.get(transport.lower(), 2800))
    if key in ("WALK", "BIKE", "CAR") or transport.lower() in ("walking", "cycling", "driving"):
        return 0 if key != "CAR" else int(distance_km * 800)
    return base


def route_cost_metrics(
    path: list[int],
    edge_map: dict,
    campuses: dict[int, Campus],
) -> dict:
    total_cost = 0
    total_dist = 0.0
    modes: set[str] = set()

    for i in range(len(path) - 1):
        e = edge_map.get((path[i], path[i + 1]))
        if not e:
            continue
        tr = getattr(e, "transport", e.get("transport", "SITP") if isinstance(e, dict) else "SITP")
        dist = getattr(e, "distance_km", 0) or 0
        total_dist += dist
        total_cost += segment_cost_cop(tr, dist)
        modes.add(tr)

    cost_per_km = round(total_cost / total_dist, 0) if total_dist > 0 else 0
    origin_zone = detect_zone(campuses[path[0]]) if path else "Centro"

    return {
        "total_cost_cop": total_cost,
        "total_distance_km": round(total_dist, 2),
        "cost_per_km": int(cost_per_km),
        "modes_used": list(modes),
        "origin_zone": origin_zone,
    }


def equity_level(cost_per_km: float, origin_zone: str) -> str:
    north_avg = 120
    if origin_zone == "Sur":
        ratio = cost_per_km / north_avg if north_avg else 1
        if ratio >= 2.5:
            return "red"
        if ratio >= 1.5:
            return "amber"
    return "green"


def eta_confidence_interval(
    total_time_min: float,
    rain_mmh: float,
    is_peak: bool,
) -> dict:
    """Chaos-aware ETAs W4 — intervalo durante pico + lluvia."""
    if is_peak and rain_mmh > 2.0:
        margin = max(7.0, total_time_min * 0.2)
    elif is_peak or rain_mmh > 2.0:
        margin = max(4.0, total_time_min * 0.12)
    else:
        margin = max(2.0, total_time_min * 0.05)
    return {"lower": round(total_time_min - margin, 1), "upper": round(total_time_min + margin, 1)}


def equity_comparison(origin_zone: str) -> dict:
    north_avg_time = 42.0
    south_avg_time = north_avg_time * (1 + EQUITY_GAP_BASELINE)
    return {
        "equity_gap_percent": round(EQUITY_GAP_BASELINE * 100, 1),
        "north_avg_time_min": north_avg_time,
        "south_avg_time_min": round(south_avg_time, 1),
        "origin_zone": origin_zone,
        "disparity_flag": origin_zone == "Sur",
    }
