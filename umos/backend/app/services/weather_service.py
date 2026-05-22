import httpx
from app.core.config import settings

BOGOTA_COORDS = {"lat": 4.7110, "lon": -74.0721}
RAIN_THRESHOLD_MM = 2.0  # mm/h desde análisis W1


async def get_current_rain() -> dict:
    """Consulta lluvia actual en Bogotá via OpenWeatherMap."""
    if not settings.OPENWEATHER_API_KEY:
        return {"rain_mm": 0.0, "is_raining": False, "description": "Sin clave API"}

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": BOGOTA_COORDS["lat"],
        "lon": BOGOTA_COORDS["lon"],
        "appid": settings.OPENWEATHER_API_KEY,
        "units": "metric",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url, params=params)
            data = resp.json()
            rain_mm = data.get("rain", {}).get("1h", 0.0)
            return {
                "rain_mm": rain_mm,
                "is_raining": rain_mm >= RAIN_THRESHOLD_MM,
                "description": data.get("weather", [{}])[0].get("description", ""),
                "temp": data.get("main", {}).get("temp", 0),
            }
        except Exception:
            return {"rain_mm": 0.0, "is_raining": False, "description": "Error API"}