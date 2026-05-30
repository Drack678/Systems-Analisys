from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.services.data_integration import get_ideam_data, get_sdm_data
from app.services.weather_service import get_current_rain
from app.services.traffic_service import get_active_events, EVENT_META

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/")
async def list_alerts(db: AsyncSession = Depends(get_db)):
    alerts = []

    weather = await get_current_rain()
    ideam = await get_ideam_data()
    rain_mmh = max(
        weather.get("rain_mm", 0),
        ideam.get("data", {}).get("rain_mmh", 0),
    )
    forecast = ideam.get("data", {}).get("forecast_30min_mmh", 0)

    if rain_mmh >= settings.RAIN_ALERT_THRESHOLD_MMH:
        alerts.append({
            "id": "rain-current",
            "type": "RAIN",
            "severity": "HIGH" if rain_mmh > 4 else "MEDIUM",
            "title": "Lluvia activa en Bogotá",
            "message": f"Precipitación {rain_mmh:.1f} mm/h — rutas ajustadas por clima",
            "lead_time_minutes": 0,
            "weather_adjusted": True,
        })
    elif forecast >= settings.RAIN_ALERT_THRESHOLD_MMH:
        alerts.append({
            "id": "rain-forecast",
            "type": "RAIN",
            "severity": "MEDIUM",
            "title": "Alerta de lluvia",
            "message": f"Lluvia prevista en ~{settings.RAIN_LEAD_TIME_MINUTES} min ({forecast:.1f} mm/h)",
            "lead_time_minutes": settings.RAIN_LEAD_TIME_MINUTES,
            "weather_adjusted": False,
        })

    sdm = await get_sdm_data()
    pyp = sdm.get("data", {}).get("pico_y_placa", {})
    if pyp:
        alerts.append({
            "id": "pico-y-placa",
            "type": "PICO_Y_PLACA",
            "severity": "LOW",
            "title": "Pico y Placa hoy",
            "message": f"Restricción dígitos {pyp.get('restricted_last_digits', [])} — {pyp.get('hours', '')}",
            "lead_time_minutes": None,
        })

    events = await get_active_events(db)
    for ev in events:
        meta = EVENT_META.get(ev.event_type, {})
        alerts.append({
            "id": f"traffic-{ev.id}",
            "type": ev.event_type,
            "severity": ev.severity,
            "title": meta.get("label", ev.event_type),
            "message": ev.description or f"Evento activo cerca de ({ev.latitude:.4f}, {ev.longitude:.4f})",
            "lead_time_minutes": None,
            "latitude": ev.latitude,
            "longitude": ev.longitude,
        })

    return {
        "alerts": alerts,
        "count": len(alerts),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
