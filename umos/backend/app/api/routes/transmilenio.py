from fastapi import APIRouter, HTTPException, Query

from app.services.transmilenio_service import (
    nearby_stations,
    nearby_trunk_routes,
    recommendation_for_trip,
    simulated_vehicles,
)

router = APIRouter(prefix="/transmilenio", tags=["TransMilenio"])


@router.get("/stations/nearby")
async def stations_nearby(
    lat: float,
    lon: float,
    radius_m: int = Query(default=900, ge=100, le=3000),
):
    try:
        return await nearby_stations(lat, lon, radius_m)
    except Exception as exc:
        raise HTTPException(502, f"No se pudo consultar estaciones de TransMilenio: {exc}") from exc


@router.get("/routes/nearby")
async def routes_nearby(
    lat: float,
    lon: float,
    radius_m: int = Query(default=1000, ge=100, le=3000),
):
    try:
        routes = await nearby_trunk_routes(lat, lon, radius_m)
        return {"routes": routes, "vehicles": simulated_vehicles(routes, 2)}
    except Exception as exc:
        raise HTTPException(502, f"No se pudo consultar rutas de TransMilenio: {exc}") from exc


@router.get("/recommendations")
async def recommendations(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
):
    try:
        return await recommendation_for_trip(origin_lat, origin_lon, dest_lat, dest_lon)
    except Exception as exc:
        raise HTTPException(502, f"No se pudo generar recomendacion SITP/TM: {exc}") from exc
