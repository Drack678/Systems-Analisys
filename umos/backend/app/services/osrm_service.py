"""
Geometría de rutas sobre calles reales (Bogotá).
Cadena de fallback: ORS GeoJSON → ORS JSON → OSRM público.
Nunca devuelve línea recta si algún servicio responde con geometría válida.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("umos.routing")

OSRM_BASE = "https://router.project-osrm.org"
ORS_BASE = "https://api.openrouteservice.org/v2/directions"

OSRM_PROFILE = {
    "driving": "driving",
    "transit": "driving",
    "cycling": "cycling",
    "walking": "foot",
}

ORS_PROFILE = {
    "driving": "driving-car",
    "transit": "driving-car",
    "cycling": "cycling-regular",
    "walking": "foot-walking",
}

TRANSPORT_TO_MODE = {
    "WALK": "walking",
    "BIKE": "cycling",
    "TM": "transit",
    "SITP": "transit",
    "CABLE": "transit",
    "CAR": "driving",
}


def _valid_geometry(geometry: list, min_points: int = 3) -> bool:
    return bool(geometry) and len(geometry) >= min_points


def _decode_ors_polyline(encoded: str) -> list[list[float]]:
    """Decodifica polyline ORS (precision 1e5) → [[lat, lon], ...]."""
    if not encoded:
        return []
    coords: list[list[float]] = []
    index = lat_i = lng_i = 0
    while index < len(encoded):
        shift = result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat_i += ~(result >> 1) if result & 1 else (result >> 1)

        shift = result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lng_i += ~(result >> 1) if result & 1 else (result >> 1)

        coords.append([lat_i / 1e5, lng_i / 1e5])
    return coords


async def _fetch_ors_geojson(coordinates: list[list[float]], mode: str) -> dict | None:
    """coordinates: [[lon, lat], ...]"""
    if not settings.ORS_API_KEY:
        return None
    profile = ORS_PROFILE.get(mode, "driving-car")
    url = f"{ORS_BASE}/{profile}/geojson"
    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json={"coordinates": coordinates}, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features") or []
        if not features:
            return None
        geom = features[0].get("geometry", {})
        raw = geom.get("coordinates") or []
        geometry = [[lat, lon] for lon, lat in raw]
        summary = features[0].get("properties", {}).get("summary", {})
        return {
            "geometry": geometry,
            "distance_m": summary.get("distance", 0),
            "duration_s": summary.get("duration", 0),
        }


async def _fetch_ors_json(coordinates: list[list[float]], mode: str) -> dict | None:
    if not settings.ORS_API_KEY:
        return None
    profile = ORS_PROFILE.get(mode, "driving-car")
    url = f"{ORS_BASE}/{profile}"
    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json={"coordinates": coordinates}, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get("routes") or []
        if not routes:
            return None
        route = routes[0]
        geometry = _decode_ors_polyline(route.get("geometry", ""))
        summary = route.get("summary", {})
        return {
            "geometry": geometry,
            "distance_m": summary.get("distance", 0),
            "duration_s": summary.get("duration", 0),
        }


async def _fetch_osrm(coordinates: list[list[float]], mode: str) -> dict | None:
    """coordinates: [[lon, lat], ...]"""
    profile = OSRM_PROFILE.get(mode, "driving")
    coord_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
    url = (
        f"{OSRM_BASE}/route/v1/{profile}/{coord_str}"
        f"?overview=full&geometries=geojson&alternatives=false&steps=false"
    )
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        raw = route["geometry"]["coordinates"]
        return {
            "geometry": [[lat, lon] for lon, lat in raw],
            "distance_m": route["distance"],
            "duration_s": route["duration"],
        }


async def _route_coordinates(coordinates: list[list[float]], mode: str) -> dict:
    """
    Resuelve ruta siguiendo calles para una lista de puntos [[lon,lat],...].
    Prueba varios perfiles si el primero falla.
    """
    modes_to_try = [mode]
    if mode != "driving":
        modes_to_try.append("driving")

    for try_mode in modes_to_try:
        for fetcher in (_fetch_ors_geojson, _fetch_ors_json, _fetch_osrm):
            try:
                result = await fetcher(coordinates, try_mode)
                if result and _valid_geometry(result["geometry"]):
                    result["source"] = fetcher.__name__
                    return result
            except Exception as exc:
                logger.debug("Routing %s failed (%s): %s", fetcher.__name__, try_mode, exc)

    # Último intento: OSRM driving aunque el modo sea otro
    try:
        result = await _fetch_osrm(coordinates, "driving")
        if result and _valid_geometry(result["geometry"]):
            result["source"] = "osrm_fallback"
            return result
    except Exception as exc:
        logger.warning("All routing services failed: %s", exc)

    # Solo si todo falla — línea recta (evitar en producción)
    lon0, lat0 = coordinates[0]
    lon1, lat1 = coordinates[-1]
    logger.error("Using straight-line fallback — check ORS/OSRM connectivity")
    return {
        "geometry": [[lat0, lon0], [lat1, lon1]],
        "distance_m": 0,
        "duration_s": 0,
        "source": "straight_fallback",
    }


async def get_path_geometry(
    waypoints: list[tuple[float, float]],
    mode: str = "driving",
) -> list[list[float]]:
    """
    Geometría completa de una ruta multi-parada siguiendo calles.
    waypoints: [(lat, lon), ...] en orden de recorrido.
    """
    if len(waypoints) < 2:
        return []
    coordinates = [[lon, lat] for lat, lon in waypoints]
    result = await _route_coordinates(coordinates, mode)
    return result["geometry"]


async def get_road_geometry(
    olat: float, olon: float,
    dlat: float, dlon: float,
    mode: str = "driving",
) -> list[list[float]]:
    info = await get_road_info(olat, olon, dlat, dlon, mode)
    return info["geometry"]


async def get_road_info(
    olat: float, olon: float,
    dlat: float, dlon: float,
    mode: str = "driving",
) -> dict:
    return await _route_coordinates([[olon, olat], [dlon, dlat]], mode)


def mode_for_transport(transport: str, fallback: str = "transit") -> str:
    return TRANSPORT_TO_MODE.get((transport or "").upper(), fallback)
