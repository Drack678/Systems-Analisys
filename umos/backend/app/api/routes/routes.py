from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.route import RouteRequest, RouteResponse, ComputeRouteRequest, ComputeRouteResponse
from app.services.route_service import RouteService
from app.services.weather_service import get_current_rain
from app.services.data_integration import get_ideam_data

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post("/compute", response_model=ComputeRouteResponse)
async def compute(req: ComputeRouteRequest, db: AsyncSession = Depends(get_db)):
    """Contrato ACO spec — multimodal route computation."""
    try:
        return await RouteService(db).compute_route(req)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/optimize", response_model=RouteResponse)
async def optimize(req: RouteRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await RouteService(db).get_optimal_route(req)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/weather")
async def weather():
    current = await get_current_rain()
    ideam = await get_ideam_data()
    ideam_data = ideam.get("data", {})
    return {
        **current,
        "forecast_30min_mmh": ideam_data.get("forecast_30min_mmh", 0),
    }
