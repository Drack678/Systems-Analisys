"""Modificadores de peso por lluvia — modelo piecewise W4."""

CYCLING_MODES = frozenset({"BIKE", "cycling", "CYCLE"})


def rain_intensity_normalized(rain_mmh: float) -> float:
    """Normaliza mm/h a escala ρ ∈ [0, 1] (4 mm/h ≈ ρ=0.4 inflection)."""
    return min(rain_mmh / 10.0, 1.0)


def piecewise_travel_multiplier(base_time: float, rain_mmh: float) -> float:
    """
    Modelo piecewise W4:
    ρ ∈ [0.0, 0.4]: t = base + 8.1ρ
    ρ ∈ [0.4, 1.0]: t = (base + 3.3) + 15.3(ρ - 0.4)
    Retorna multiplicador sobre base_time.
    """
    if rain_mmh <= 0:
        return 1.0
    rho = rain_intensity_normalized(rain_mmh)
    if rho <= 0.4:
        adjusted = base_time + 8.1 * rho
    else:
        adjusted = (base_time + 3.3) + 15.3 * (rho - 0.4)
    return adjusted / base_time if base_time > 0 else 1.0


def edge_weight_multiplier(
    rain_mmh: float,
    mode: str,
    congestion_factor: float = 1.0,
    bus_bunching: bool = False,
    bus_bunching_beta: float = 1.8,
    rain_multiplier: float = 1.63,
    rain_threshold: float = 2.0,
) -> float:
    """Peso de arista = travel_time × (1 + congestion) × rain_modifier × bunching."""
    if rain_mmh > rain_threshold and mode.upper() in CYCLING_MODES:
        return float("inf")

    mult = 1.0 + max(congestion_factor - 1.0, 0.0)

    if rain_mmh > rain_threshold:
        mult *= rain_multiplier
    elif rain_mmh > 0:
        mult *= piecewise_travel_multiplier(1.0, rain_mmh)

    if bus_bunching:
        mult *= bus_bunching_beta

    return mult


def suppress_cycling_edges(graph: dict, rain_mmh: float, threshold: float = 2.0) -> dict:
    """Elimina aristas de ciclismo cuando lluvia supera umbral."""
    if rain_mmh <= threshold:
        return graph
    filtered = {}
    for node, neighbors in graph.items():
        filtered[node] = {
            n: data
            for n, data in neighbors.items()
            if (data.get("transport") or "").upper() not in CYCLING_MODES
        }
    return filtered
