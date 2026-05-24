"""
OSRM wrapper — extrae geometría real de las calles de Bogotá.
API pública: router.project-osrm.org (sin key, sin límite razonable)
Perfiles: driving, cycling, foot (walking)
"""
import httpx
from app.core.config import settings

OSRM_BASE = "https://router.project-osrm.org"

OSRM_PROFILE = {
    "driving": "driving",
    "transit": "driving",   # SITP/TM circula por calles de carro
    "cycling": "cycling",
    "walking": "foot",
}

async def get_road_geometry(
    olat: float, olon: float,
    dlat: float, dlon: float,
    mode: str = "driving",
) -> list[list[float]]:
    """
    Devuelve la lista de puntos [[lat,lon], ...] que siguen
    exactamente las calles de Bogotá entre dos coordenadas.
    Si OSRM falla, retorna línea recta como fallback.
    """
    profile = OSRM_PROFILE.get(mode, "driving")
    url = (
        f"{OSRM_BASE}/route/v1/{profile}/"
        f"{olon},{olat};{dlon},{dlat}"
        f"?overview=full&geometries=geojson&alternatives=false&steps=false"
    )

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "Ok" or not data.get("routes"):
                return [[olat, olon], [dlat, dlon]]

            # GeoJSON devuelve [lon, lat] → invertimos a [lat, lon] para Leaflet
            coords = data["routes"][0]["geometry"]["coordinates"]
            return [[lat, lon] for lon, lat in coords]

        except Exception:
            # Fallback: línea recta si OSRM no responde
            return [[olat, olon], [dlat, dlon]]


async def get_road_info(
    olat: float, olon: float,
    dlat: float, dlon: float,
    mode: str = "driving",
) -> dict:
    """
    Devuelve geometría + distancia real + duración real de OSRM.
    """
    profile = OSRM_PROFILE.get(mode, "driving")
    url = (
        f"{OSRM_BASE}/route/v1/{profile}/"
        f"{olon},{olat};{dlon},{dlat}"
        f"?overview=full&geometries=geojson&alternatives=false&steps=false"
    )

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "Ok" or not data.get("routes"):
                return {"geometry": [[olat,olon],[dlat,dlon]],
                        "distance_m": 0, "duration_s": 0}

            route  = data["routes"][0]
            coords = route["geometry"]["coordinates"]
            return {
                "geometry":   [[lat, lon] for lon, lat in coords],
                "distance_m": route["distance"],
                "duration_s": route["duration"],
            }
        except Exception:
            return {"geometry": [[olat,olon],[dlat,dlon]],
                    "distance_m": 0, "duration_s": 0}
