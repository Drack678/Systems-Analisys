import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.traffic_event import TrafficEvent


# ── Metadatos visuales por tipo de evento ────────────────────────────────────
EVENT_META = {
    "PROTEST":     {"icon": "📢", "color": "#f85149", "label": "Protesta"},
    "ACCIDENT":    {"icon": "🚨", "color": "#ff7b00", "label": "Accidente"},
    "MINOR_CRASH": {"icon": "💥", "color": "#e3b341", "label": "Choque leve"},
    "ROAD_CLOSED": {"icon": "🚧", "color": "#8b949e", "label": "Vía cerrada"},
    "CONGESTION":  {"icon": "🚗", "color": "#d29922", "label": "Congestión"},
    "RAIN":        {"icon": "🌧", "color": "#58a6ff", "label": "Lluvia intensa"},
}

# ── Factor de demora por severidad ───────────────────────────────────────────
SEVERITY_FACTOR = {
    "LOW":      1.2,   # +20%
    "MEDIUM":   1.5,   # +50%
    "HIGH":     2.0,   # +100%
    "CRITICAL": 3.0,   # +200%
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia en metros entre dos coordenadas geográficas
    usando la fórmula de Haversine.
    """
    R = 6_371_000  # radio de la Tierra en metros
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def get_active_events(db: AsyncSession) -> list[TrafficEvent]:
    """Retorna todos los eventos de tráfico activos de la BD."""
    result = await db.execute(
        select(TrafficEvent).where(TrafficEvent.active == True)
    )
    return result.scalars().all()


async def compute_edge_factor(
    db:   AsyncSession,
    olat: float,
    olon: float,
    dlat: float,
    dlon: float,
) -> tuple[float, list[dict]]:
    """
    Calcula el factor de demora total para un segmento de ruta
    verificando si algún evento activo está dentro del radio de influencia
    de alguno de sus tres puntos clave: origen, destino y punto medio.

    Retorna:
        factor     — multiplicador de tiempo (1.0 = sin demora)
        affecting  — lista de eventos que afectan el segmento
    """
    events   = await get_active_events(db)
    mid_lat  = (olat + dlat) / 2
    mid_lon  = (olon + dlon) / 2

    total_factor = 1.0
    affecting: list[dict] = []

    for ev in events:
        # Distancia mínima del evento a cualquiera de los 3 puntos del segmento
        dist = min(
            _haversine(ev.latitude, ev.longitude, olat,    olon),
            _haversine(ev.latitude, ev.longitude, dlat,    dlon),
            _haversine(ev.latitude, ev.longitude, mid_lat, mid_lon),
        )

        if dist <= ev.radius_m:
            factor = SEVERITY_FACTOR.get(ev.severity, 1.5)
            # Tomamos el factor más alto entre todos los eventos que afectan
            total_factor = max(total_factor, factor)

            meta = EVENT_META.get(ev.event_type, {})
            affecting.append({
                "id":          ev.id,
                "event_type":  ev.event_type,
                "severity":    ev.severity,
                "factor":      factor,
                "distance_m":  round(dist),
                "icon":        meta.get("icon",  "⚠️"),
                "color":       meta.get("color", "#ff7b00"),
                "label":       meta.get("label", ev.event_type),
            })

    return total_factor, affecting


async def get_traffic_summary(db: AsyncSession) -> dict:
    """
    Resumen global del estado del tráfico en Bogotá.
    Útil para mostrar un indicador en el frontend.
    """
    events = await get_active_events(db)

    if not events:
        return {
            "status":  "LIBRE",
            "color":   "#6daa45",
            "icon":    "🟢",
            "message": "Sin eventos activos",
            "total":   0,
        }

    severities = [ev.severity for ev in events]

    if "CRITICAL" in severities:
        return {"status": "CRITICO",  "color": "#f85149", "icon": "🔴",
                "message": f"{len(events)} evento(s) crítico(s)", "total": len(events)}
    if "HIGH" in severities:
        return {"status": "ALTO",     "color": "#ff7b00", "icon": "🟠",
                "message": f"{len(events)} evento(s) de alto impacto", "total": len(events)}
    if "MEDIUM" in severities:
        return {"status": "MODERADO", "color": "#e3b341", "icon": "🟡",
                "message": f"{len(events)} evento(s) activo(s)", "total": len(events)}

    return {"status": "LEVE",   "color": "#d29922", "icon": "🟡",
            "message": f"{len(events)} evento(s) menor(es)", "total": len(events)}