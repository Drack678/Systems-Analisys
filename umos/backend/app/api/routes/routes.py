from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.route import RouteRequest, RouteResponse
from app.services.route_service import RouteService
from app.services.weather_service import get_current_rain

router = APIRouter(prefix="/routes", tags=["Routes"])

@router.post("/optimize", response_model=RouteResponse)
async def optimize(req: RouteRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await RouteService(db).get_optimal_route(req)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/weather")
async def weather():
    return await get_current_rain()