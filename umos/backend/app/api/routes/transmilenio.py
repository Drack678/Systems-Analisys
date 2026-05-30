from fastapi import APIRouter, HTTPException, Query

from app.services.gtfs_service import get_gtfs, point_at_progress, make_ants, ANTS_PER_ROUTE
from app.services.transit_aco_service import TransitACOService

router = APIRouter(prefix="/transmilenio", tags=["TransMilenio"])


@router.get("/stations/nearby")
async def stations_nearby(
    lat: float,
    lon: float,
    radius_m: int = Query(default=900, ge=100, le=5000),
):
    try:
        gtfs = get_gtfs()
        return gtfs.nearest_stops(lat, lon, limit=10, max_m=radius_m)
    except Exception as exc:
        raise HTTPException(502, f"Error GTFS estaciones: {exc}") from exc


@router.get("/routes/nearby")
async def routes_nearby(
    lat: float,
    lon: float,
    radius_m: int = Query(default=1500, ge=100, le=5000),
):
    try:
        gtfs = get_gtfs()
        gtfs.load_shapes()
        stops = gtfs.nearest_stops(lat, lon, 3, radius_m)
        routes = []
        seen = set()
        for s in stops:
            for rid in gtfs.routes_serving_stop(s["id"])[:15]:
                if rid in seen:
                    continue
                seen.add(rid)
                r = gtfs.routes.get(rid, {})
                geom = gtfs.route_geometry(rid)
                if len(geom) < 3:
                    continue
                routes.append({
                    "id": rid,
                    "name": r.get("short_name", rid),
                    "long_name": r.get("long_name", ""),
                    "geometry": geom,
                    "ants": make_ants(rid, ANTS_PER_ROUTE),
                })
        return {"routes": routes[:12]}
    except Exception as exc:
        raise HTTPException(502, f"Error GTFS rutas: {exc}") from exc


@router.get("/recommendations")
async def recommendations(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    origin_name: str = "",
    dest_name: str = "",
):
    try:
        return TransitACOService().recommend(
            origin_lat, origin_lon, dest_lat, dest_lon, dest_name, origin_name
        )
    except Exception as exc:
        raise HTTPException(502, f"No se pudo generar recomendación GTFS/ACO: {exc}") from exc


@router.get("/simulation/tick")
async def simulation_tick(
    route_ids: str = Query(..., description="IDs separados por coma"),
):
    """Posiciones actuales de 5 hormigas por ruta (simulación periódica)."""
    import time

    gtfs = get_gtfs()
    gtfs.load_shapes()
    t = time.time()
    period = 12
    out = []
    for rid in route_ids.split(","):
        rid = rid.strip()
        if not rid:
            continue
        geom = gtfs.route_geometry(rid)
        r = gtfs.routes.get(rid, {})
        for ant in make_ants(rid, ANTS_PER_ROUTE):
            progress = (t / period + ant["offset"]) % 1
            pt = point_at_progress(geom, progress)
            if pt:
                out.append({
                    "id": ant["id"],
                    "route_id": rid,
                    "label": r.get("short_name", rid),
                    "latitude": pt[0],
                    "longitude": pt[1],
                    "progress": round(progress, 3),
                })
    return {"vehicles": out, "period_sec": period}
