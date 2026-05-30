from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.route import RouteRequest, RouteResponse, ComputeRouteRequest, ComputeRouteResponse
from app.services.route_service import RouteService
from app.services.weather_service import get_current_rain

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
    return await get_current_rain()
