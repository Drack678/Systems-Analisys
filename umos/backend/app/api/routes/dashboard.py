from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.data_integration import (
    get_transmilenio_data,
    get_sdm_data,
    get_ideam_data,
    get_idu_data,
    get_udfjc_data,
    get_all_freshness,
)
from app.services.transmilenio_service import simulated_vehicles
from app.services.traffic_service import get_traffic_summary
from app.core.config import settings

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/status")
async def dashboard_status(db: AsyncSession = Depends(get_db)):
    tm = await get_transmilenio_data()
    ideam = await get_ideam_data()
    sdm = await get_sdm_data()
    traffic = await get_traffic_summary(db)

    tm_data = tm.get("data", {})
    ideam_data = ideam.get("data", {})
    routes = tm_data.get("routes", []) if isinstance(tm_data.get("routes"), list) else []

    occupancy = tm_data.get("universidades_occupancy", 0.5)
    universidades_congested = occupancy >= settings.CONGESTION_THRESHOLD

    return {
        "vehicle_count": tm_data.get("vehicle_positions", 0),
        "universidades_occupancy": round(occupancy * 100, 1),
        "universidades_congested": universidades_congested,
        "weather": {
            "rain_mmh": ideam_data.get("rain_mmh", 0),
            "forecast_30min_mmh": ideam_data.get("forecast_30min_mmh", 0),
        },
        "traffic_summary": traffic,
        "sdm_congestion": sdm.get("data", {}).get("congestion_index", 0),
        "data_freshness": await get_all_freshness(),
        "bus_bunching_routes": [],
    }


@router.get("/freshness")
async def data_freshness():
    return await get_all_freshness()
