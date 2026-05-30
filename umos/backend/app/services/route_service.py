import time
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.campus import Campus
from app.models.route_edge import RouteEdge
from app.schemas.route import (
    RouteRequest,
    RouteResponse,
    RouteAlternative,
    RouteStep,
    RouteVariant,
    ComputeRouteRequest,
    ComputeRouteResponse,
    ACOMetadata,
    Segment,
    ETAConfidence,
    LatLng,
)
from app.services.aco import AntColonyOptimizer, ACOConfig
from app.services.weather_service import get_current_rain
from app.services.traffic_service import compute_edge_factor
from app.services.osrm_service import get_path_geometry, mode_for_transport
from app.services.equity_service import (
    route_cost_metrics,
    equity_level,
    eta_confidence_interval,
    detect_zone,
)
from app.services.data_integration import get_transmilenio_data, get_ideam_data
from app.core.config import settings


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _nearest_campus(campuses: dict[int, Campus], lat: float, lng: float) -> int:
    best_id, best_d = None, float("inf")
    for cid, c in campuses.items():
        d = _haversine(lat, lng, c.latitude, c.longitude)
        if d < best_d:
            best_d, best_id = d, cid
    return best_id


def _count_transfers(path: list[int], edge_map: dict) -> int:
    modes = []
    for i in range(len(path) - 1):
        e = edge_map.get((path[i], path[i + 1]))
        if e:
            modes.append(getattr(e, "transport", "WALK"))
    transfers = 0
    for i in range(1, len(modes)):
        if modes[i] != modes[i - 1] and modes[i] not in ("WALK",) and modes[i - 1] not in ("WALK",):
            transfers += 1
    return transfers


def _is_peak_hour() -> bool:
    h = datetime.now().hour
    return 7 <= h < 9 or 17 <= h < 20


class RouteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_graph(self) -> tuple:
        campuses = {
            c.id: c for c in (await self.db.execute(select(Campus))).scalars().all()
        }
        edges = (await self.db.execute(select(RouteEdge))).scalars().all()
        edge_map = {(e.origin_id, e.dest_id): e for e in edges}
        edge_traffic: dict = {}
        graph: dict = {cid: {} for cid in campuses}
        pheromones: dict = {cid: {} for cid in campuses}
        congestion_by_edge: dict = {}

        for edge in edges:
            co, cd = campuses[edge.origin_id], campuses[edge.dest_id]
            factor, affecting = await compute_edge_factor(
                self.db, co.latitude, co.longitude, cd.latitude, cd.longitude
            )
            edge_traffic[(edge.origin_id, edge.dest_id)] = {
                "factor": factor,
                "events": affecting,
            }
            congestion_by_edge[(edge.origin_id, edge.dest_id)] = factor
            graph[edge.origin_id][edge.dest_id] = {
                "cost": edge.travel_time,
                "transport": edge.transport,
            }
            pheromones[edge.origin_id][edge.dest_id] = edge.pheromone

        for origin_id, origin_c in campuses.items():
            for dest_id, dest_c in campuses.items():
                if origin_id == dest_id or dest_id in graph[origin_id]:
                    continue
                dist = _haversine(
                    origin_c.latitude, origin_c.longitude,
                    dest_c.latitude, dest_c.longitude,
                )
                travel_time = dist * 6.0
                graph[origin_id][dest_id] = {"cost": travel_time, "transport": "CAR"}
                pheromones[origin_id][dest_id] = 1.0
                edge_map[(origin_id, dest_id)] = SimpleNamespace(
                    origin_id=origin_id, dest_id=dest_id,
                    travel_time=travel_time, distance_km=dist,
                    transport="CAR", pheromone=1.0,
                )
                edge_traffic[(origin_id, dest_id)] = {"factor": 1.0, "events": []}
                congestion_by_edge[(origin_id, dest_id)] = 1.0

        return campuses, edge_map, edge_traffic, graph, pheromones, congestion_by_edge

    async def _resolve_ids(
        self, req: ComputeRouteRequest, campuses: dict[int, Campus]
    ) -> tuple[int, int]:
        if req.origin_id and req.destination_id:
            return req.origin_id, req.destination_id
        if req.origin and req.destination:
            return (
                _nearest_campus(campuses, req.origin.lat, req.origin.lng),
                _nearest_campus(campuses, req.destination.lat, req.destination.lng),
            )
        raise ValueError("Debe proporcionar origin_id/destination_id o coordenadas lat/lng")

    async def _run_aco(
        self,
        origin_id: int,
        destination_id: int,
        rain_mmh: float,
        graph: dict,
        pheromones: dict,
        congestion_by_edge: dict,
    ) -> dict:
        tm_data = await get_transmilenio_data()
        occupancy = tm_data.get("data", {}).get("universidades_occupancy", 0.5)
        bus_bunching_edges: set = set()
        if occupancy >= settings.CONGESTION_THRESHOLD:
            for (o, d), _ in congestion_by_edge.items():
                bus_bunching_edges.add((o, d))

        cfg = ACOConfig.from_settings()
        t0 = time.perf_counter()
        result = AntColonyOptimizer(cfg).optimize(
            graph,
            origin_id,
            destination_id,
            pheromones,
            rain_mmh=rain_mmh,
            congestion_by_edge=congestion_by_edge,
            bus_bunching_edges=bus_bunching_edges,
            max_alternatives=3,
        )
        result["computation_time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return result

    async def compute_route(self, req: ComputeRouteRequest) -> ComputeRouteResponse:
        campuses, edge_map, edge_traffic, graph, pheromones, congestion_by_edge = (
            await self._load_graph()
        )
        origin_id, dest_id = await self._resolve_ids(req, campuses)

        if origin_id not in campuses or dest_id not in campuses:
            raise ValueError("Campus no encontrado")

        if req.rain_intensity is not None:
            rain_mmh = req.rain_intensity
        else:
            ideam = await get_ideam_data()
            rain_mmh = ideam.get("data", {}).get("rain_mmh", 0.0)
            weather = await get_current_rain()
            if weather.get("rain_mm", 0) > rain_mmh:
                rain_mmh = weather["rain_mm"]

        result = await self._run_aco(
            origin_id, dest_id, rain_mmh, graph, pheromones, congestion_by_edge
        )

        routes = result.get("routes") or []
        if not routes:
            raise ValueError("No se pudo encontrar una ruta óptima")

        await self._persist_pheromones(result, edge_map)

        variants = []
        for idx, (path, score) in enumerate(routes):
            v = await self._build_variant(
                idx, path, score, campuses, edge_map, edge_traffic,
                rain_mmh, req.transport_mode, result["best_cost"],
            )
            variants.append(v)

        equity_alert = None
        origin_zone = detect_zone(campuses[origin_id])
        if origin_zone == "Sur" and rain_mmh > settings.ACO_RAIN_THRESHOLD_MMH:
            alt_count = len([v for v in variants if len(v.transport_modes) > 1])
            if alt_count < 2:
                equity_alert = (
                    "Limited alternatives during rain — depart before 07:15 recommended."
                )

        meta = ACOMetadata(
            iterations=result["iterations"],
            convergence_step=result["convergence_step"],
            pheromone_snapshot=result.get("pheromone_snapshot", {}),
        )

        return ComputeRouteResponse(
            optimal_route=variants[0],
            alternatives=variants[1:],
            computation_time_ms=result["computation_time_ms"],
            aco_metadata=meta,
            rain_penalty_applied=result["rain_applied"],
            equity_alert=equity_alert,
        )

    async def get_optimal_route(self, req: RouteRequest) -> RouteResponse:
        compute_req = ComputeRouteRequest(
            origin_id=req.origin_id,
            destination_id=req.destination_id,
            transport_mode=req.transport_mode,
        )
        if req.rain:
            weather = await get_current_rain()
            compute_req.rain_intensity = max(weather.get("rain_mm", 3.0), 3.0)

        result = await self.compute_route(compute_req)
        campuses, _, _, _, _, _ = await self._load_graph()

        all_events: dict = {}
        for step in result.optimal_route.steps:
            pass

        return RouteResponse(
            origin=campuses[req.origin_id].name,
            destination=campuses[req.destination_id].name,
            transport_mode=req.transport_mode,
            selected=result.optimal_route,
            alternatives=result.alternatives,
            active_traffic_events=list(all_events.values()),
            aco_iterations=result.aco_metadata.iterations,
            rain_penalty_applied=result.rain_penalty_applied,
            computation_time_ms=result.computation_time_ms,
            aco_metadata=result.aco_metadata,
            equity_alert=result.equity_alert,
        )

    async def _persist_pheromones(self, result: dict, edge_map: dict):
        cfg = ACOConfig.from_settings()
        best_path = result.get("best_path") or []
        best_cost = result.get("best_cost") or 1
        delta = cfg.Q / best_cost if best_cost > 0 else 0
        for i in range(len(best_path) - 1):
            e = edge_map.get((best_path[i], best_path[i + 1]))
            if e and hasattr(e, "pheromone"):
                e.pheromone = max(
                    e.pheromone * (1 - cfg.evaporation) + delta,
                    cfg.min_pheromone,
                )
        await self.db.commit()

    async def _build_variant(
        self,
        idx: int,
        path: list[int],
        score: float,
        campuses: dict,
        edge_map: dict,
        edge_traffic: dict,
        rain_mmh: float,
        mode: str,
        best_cost: float,
    ) -> RouteVariant:
        # Geometría multi-parada en una sola petición (sigue calles reales)
        waypoints = [(campuses[nid].latitude, campuses[nid].longitude) for nid in path]
        full_geometry = await get_path_geometry(waypoints, mode)

        # Si la ruta global falló, intentar tramo a tramo con perfil según transporte
        if len(full_geometry) < 3 and len(path) > 1:
            full_geometry = []
            for i in range(len(path) - 1):
                ca, cb = campuses[path[i]], campuses[path[i + 1]]
                edge = edge_map.get((path[i], path[i + 1]))
                seg_mode = mode_for_transport(
                    getattr(edge, "transport", "CAR") if edge else "CAR",
                    fallback=mode,
                )
                seg_geom = await get_path_geometry(
                    [(ca.latitude, ca.longitude), (cb.latitude, cb.longitude)],
                    seg_mode,
                )
                if full_geometry and seg_geom:
                    seg_geom = seg_geom[1:]
                full_geometry.extend(seg_geom)

        steps: list[RouteStep] = []
        segments: list[Segment] = []
        cum_t = cum_d = 0.0
        modes_set: set = set()
        cfg = ACOConfig.from_settings()
        apply_rain = rain_mmh > cfg.rain_threshold_mmh
        is_peak = _is_peak_hour()

        for i, nid in enumerate(path):
            c = campuses[nid]
            tr, tf, evs = "", 1.0, []
            if i > 0:
                e = edge_map.get((path[i - 1], nid))
                if e:
                    td = edge_traffic.get((path[i - 1], nid), {})
                    tf = td.get("factor", 1.0)
                    evs = td.get("events", [])
                    rain_f = cfg.rain_multiplier if apply_rain and e.transport in ("CAR", "SITP", "TM") else 1.0
                    if 0 < rain_mmh <= cfg.rain_threshold_mmh:
                        from app.services.aco.rain_modifier import piecewise_travel_multiplier
                        rain_f = piecewise_travel_multiplier(1.0, rain_mmh)
                    seg_time = e.travel_time * tf * rain_f
                    cum_t += seg_time
                    cum_d += e.distance_km
                    tr = e.transport
                    modes_set.add(e.transport)
                    prev = campuses[path[i - 1]]
                    segments.append(Segment(
                        mode=tr,
                        from_name=prev.name,
                        to_name=c.name,
                        duration_min=round(seg_time, 1),
                        distance_km=e.distance_km,
                        cost_cop=0,
                    ))

            steps.append(RouteStep(
                campus_id=c.id,
                campus_name=c.name,
                latitude=c.latitude,
                longitude=c.longitude,
                transport=tr,
                cumulative_time=round(cum_t, 1),
                cumulative_distance=round(cum_d, 2),
                traffic_factor=round(tf, 2),
                traffic_events=[x.get("label", "") for x in evs if x.get("label")],
            ))

        metrics = route_cost_metrics(path, edge_map, campuses)
        eta = eta_confidence_interval(cum_t, rain_mmh, is_peak)
        labels = {0: "Ruta óptima", 1: "Alternativa A", 2: "Alternativa B"}

        return RouteVariant(
            label=labels.get(idx, f"Ruta {idx + 1}"),
            total_time=round(cum_t, 1),
            total_distance=round(cum_d, 2),
            total_cost_cop=metrics["total_cost_cop"],
            cost_per_km=float(metrics["cost_per_km"]),
            transfers=_count_transfers(path, edge_map),
            transport_modes=list(modes_set),
            modes_used=metrics["modes_used"],
            steps=steps,
            segments=segments,
            geometry=full_geometry,
            path=path,
            eta_confidence_interval=ETAConfidence(**eta),
            weather_adjusted=apply_rain,
            equity_level=equity_level(metrics["cost_per_km"], metrics["origin_zone"]),
            aco_score=round(best_cost / score, 3) if score > 0 else 1.0,
        )
