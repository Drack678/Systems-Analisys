from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.route import RouteRequest, RouteResponse
from app.services.route_service import RouteService
from app.services.weather_service import get_current_rain

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post("/optimize", response_model=RouteResponse)
async def optimize_route(req: RouteRequest, db: AsyncSession = Depends(get_db)):
    try:
        service = RouteService(db)
        return await service.get_optimal_route(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/weather")
async def current_weather():
    return await get_current_rain()