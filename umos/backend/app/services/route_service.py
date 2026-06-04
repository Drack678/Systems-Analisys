import asyncio
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


# ─── Metadatos visuales por modo de transporte ──────────────────────
MODE_META: dict[str, dict[str, str]] = {
    "WALK":  {"icon": "🚶", "color": "#f59e0b", "verb": "Camina"},
    "BIKE":  {"icon": "🚲", "color": "#22c55e", "verb": "Pedalea"},
    "TM":    {"icon": "🚌", "color": "#e11d48", "verb": "Toma TransMilenio"},
    "SITP":  {"icon": "🚐", "color": "#14b8a6", "verb": "Toma SITP"},
    "CABLE": {"icon": "🚠", "color": "#a855f7", "verb": "Toma TransMiCable"},
    "CAR":   {"icon": "🚗", "color": "#64748b", "verb": "Maneja"},
}


# ─── Configuración por modo del usuario ─────────────────────────────
# Define qué tipos de transport son válidos para cada modo, y cómo
# auto-completar el grafo (cuando no hay edge declarado entre dos nodos).
MODE_CONFIG: dict[str, dict] = {

    "sitp": {
        # Solo SITP + caminar. Es lo que ya venías viendo.
        "allowed_transports": ("WALK", "SITP"),
        "include_transit_nodes": True,
        "autocomplete_transport": None,
        "autocomplete_speed_min_per_km": None,
    },

    "tm": {
        # TransMilenio + caminar. El SITP solo se permite como alimentador
        # de portal (cuando conecta con una estación troncal).
        "allowed_transports": ("WALK", "TM", "CABLE"),
        "include_transit_nodes": True,
        "autocomplete_transport": None,
        "autocomplete_speed_min_per_km": None,
        "sitp_portal_feeder": True,
    },

    "transit": {
        # Para TransMilenio se permiten WALK, TM, SITP, CABLE.
        # NO se auto-completa: la ruta DEBE pasar por paraderos/estaciones,
        # forzando segmentos tipo Moovit (camina → bus → transbordo → camina).
        "allowed_transports": ("WALK", "TM", "SITP", "CABLE", "BIKE"),
        "include_transit_nodes": True,
        "autocomplete_transport": None,
        "autocomplete_speed_min_per_km": None,
    },
    "driving": {
        # En carro solo se usan facultades (no tiene sentido pasar por paraderos).
        # Auto-completa con CAR a 6 min/km (velocidad urbana típica en Bogotá).
        "allowed_transports": ("CAR",),
        "include_transit_nodes": False,
        "autocomplete_transport": "CAR",
        "autocomplete_speed_min_per_km": 6.0,
    },
    "cycling": {
        # En bici se permite caminar tramos cortos. Auto-completa con BIKE
        # a 4 min/km (~15 km/h, velocidad típica de ciclista urbano).
        "allowed_transports": ("BIKE", "WALK"),
        "include_transit_nodes": False,
        "autocomplete_transport": "BIKE",
        "autocomplete_speed_min_per_km": 4.0,
    },
    "walking": {
        # A pie únicamente. Auto-completa con WALK a 12 min/km (~5 km/h).
        "allowed_transports": ("WALK",),
        "include_transit_nodes": False,
        "autocomplete_transport": "WALK",
        "autocomplete_speed_min_per_km": 12.0,
    },
}


def _format_distance(km: float) -> str:
    """320m si <1km, 1.4km si >=1km."""
    return f"{int(km * 1000)}m" if km < 1 else f"{km:.1f}km"


def _build_instruction(transport: str, distance_km: float, dest_name: str) -> str:
    """Genera la instrucción narrativa tipo Moovit del segmento."""
    meta = MODE_META.get(transport, MODE_META["CAR"])
    return f"{meta['verb']} {_format_distance(distance_km)} hacia {dest_name}"


def _is_transit_node(campus: Campus) -> bool:
    """Identifica paraderos/estaciones por convención del code (TM- o SITP-)."""
    code = (campus.code or "").upper()
    return code.startswith("TM-") or code.startswith("SITP-") or code.startswith("CABLE-")

def _is_tm_station(campus: Campus) -> bool:
    """Estación troncal de TransMilenio (código TM-)."""
    return (campus.code or "").upper().startswith("TM-")


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
    """
    Cada tramo SITP/TM/CABLE es subirse a un bus. Transbordos = cuántas veces
    te subes DESPUÉS del primero. Antes solo contaba cambios de tipo, por eso
    dos SITP seguidos daban 0.
    """
    TRANSIT = ("TM", "SITP", "CABLE")
    transfers = 0
    seen_transit = False
    for i in range(len(path) - 1):
        e = edge_map.get((path[i], path[i + 1]))
        m = getattr(e, "transport", "WALK") if e else "WALK"
        if m in TRANSIT:
            if seen_transit:
                transfers += 1
            seen_transit = True
    return transfers


def _is_peak_hour() -> bool:
    h = datetime.now().hour
    return 7 <= h < 9 or 17 <= h < 20


class RouteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_graph(
        self,
        mode: str = "transit",
        origin_id: int | None = None,
        dest_id: int | None = None,
    ) -> tuple:
        """
        Carga el grafo del modelo (Campus + RouteEdge) filtrando según el modo
        seleccionado por el usuario.

        - transit: usa facultades + paraderos + estaciones (sin auto-completar)
        - driving/cycling/walking: solo facultades, auto-completa con el
          transport correspondiente.
        """
        cfg_mode = MODE_CONFIG.get(mode, MODE_CONFIG["transit"])

        # Cargar todos los nodos del modelo
        all_campuses = {
            c.id: c for c in (await self.db.execute(select(Campus))).scalars().all()
        }

        # Filtrar paraderos/estaciones si el modo no los necesita
        if cfg_mode["include_transit_nodes"]:
            campuses = all_campuses
        else:
            campuses = {
                cid: c for cid, c in all_campuses.items()
                if not _is_transit_node(c)
            }

        edges = (await self.db.execute(select(RouteEdge))).scalars().all()
        edge_map: dict = {}
        edge_traffic: dict = {}
        graph: dict = {cid: {} for cid in campuses}
        pheromones: dict = {cid: {} for cid in campuses}
        congestion_by_edge: dict = {}

        # Cargar edges declarados en route_edges.json, filtrando por:
        #  1) Que ambos extremos estén entre los nodos permitidos por el modo
        #  2) Que el transport del edge esté permitido por el modo
        # Cargar edges declarados en route_edges.json, filtrando por:
        #  1) Que ambos extremos estén entre los nodos permitidos por el modo
        #  2) Que el transport del edge esté permitido por el modo
        # Penalización: si el destino del edge es una facultad intermedia (no origen ni destino del viaje),
        # multiplicamos su costo para que el ACO la evite. Esto previene rutas absurdas que pasan
        # por facultades que no son ni el origen ni el destino del usuario.
        FACULTY_INTERMEDIATE_PENALTY = 20.0
        # Costo por subirse a un bus. Hace que prefiera rutas con menos abordajes.
        BOARDING_PENALTY_MIN = 5.0
        TRANSIT_TRANSPORTS = ("TM", "SITP", "CABLE")

        for edge in edges:
            if edge.origin_id not in campuses or edge.dest_id not in campuses:
                continue
            if edge.transport not in cfg_mode["allowed_transports"]:
                # En modo TM dejamos pasar SITP solo si toca una estación troncal
                # (alimentador de portal). El resto de SITP se descarta.
                feeder_ok = (
                    edge.transport == "SITP"
                    and cfg_mode.get("sitp_portal_feeder")
                    and (
                        _is_tm_station(campuses[edge.origin_id])
                        or _is_tm_station(campuses[edge.dest_id])
                    )
                )
                if not feeder_ok:
                    continue

            co, cd = campuses[edge.origin_id], campuses[edge.dest_id]
            factor, affecting = await compute_edge_factor(
                self.db, co.latitude, co.longitude, cd.latitude, cd.longitude
            )

            # Calcular costo final con penalización si aplica
            cost = edge.travel_time
            dest_is_faculty = not _is_transit_node(cd)
            dest_is_endpoint = (cd.id == origin_id or cd.id == dest_id)
            if dest_is_faculty and not dest_is_endpoint and origin_id is not None:
                cost = cost * FACULTY_INTERMEDIATE_PENALTY

            # Si el tramo es de bus, súmale el costo de subirse
            if edge.transport in TRANSIT_TRANSPORTS:
                cost += BOARDING_PENALTY_MIN

            edge_map[(edge.origin_id, edge.dest_id)] = edge
            edge_traffic[(edge.origin_id, edge.dest_id)] = {
                "factor": factor,
                "events": affecting,
            }
            congestion_by_edge[(edge.origin_id, edge.dest_id)] = factor
            graph[edge.origin_id][edge.dest_id] = {
                "cost": cost,
                "transport": edge.transport,
            }
            pheromones[edge.origin_id][edge.dest_id] = edge.pheromone

        # Auto-completar grafo solo si el modo lo requiere (carro/bici/a pie).
        # En transit NO auto-completamos para forzar rutas multi-segmento por
        # paraderos. Si dos facultades no están conectadas vía paraderos, mejor
        # falla y se ve el error que dar una ruta directa irrealista.
        if cfg_mode["autocomplete_transport"] is not None:
            auto_transport = cfg_mode["autocomplete_transport"]
            speed = cfg_mode["autocomplete_speed_min_per_km"]

            for origin_id, origin_c in campuses.items():
                for dest_id, dest_c in campuses.items():
                    if origin_id == dest_id or dest_id in graph[origin_id]:
                        continue
                    dist = _haversine(
                        origin_c.latitude, origin_c.longitude,
                        dest_c.latitude, dest_c.longitude,
                    )
                    travel_time = dist * speed
                    graph[origin_id][dest_id] = {
                        "cost": travel_time,
                        "transport": auto_transport,
                    }
                    pheromones[origin_id][dest_id] = 1.0
                    edge_map[(origin_id, dest_id)] = SimpleNamespace(
                        origin_id=origin_id, dest_id=dest_id,
                        travel_time=travel_time, distance_km=dist,
                        transport=auto_transport, pheromone=1.0,
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
            None,
            rain_mmh=rain_mmh,
            congestion_by_edge=congestion_by_edge,
            bus_bunching_edges=bus_bunching_edges,
            max_alternatives=3,
        )
        result["computation_time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return result

    async def compute_route(self, req: ComputeRouteRequest) -> ComputeRouteResponse:
        # Primero resolvemos origin/dest cargando un grafo temporal sin penalizaciones
        temp_campuses, _, _, _, _, _ = await self._load_graph(mode=req.transport_mode)
        origin_id, dest_id = await self._resolve_ids(req, temp_campuses)

        # Luego cargamos el grafo definitivo con las penalizaciones aplicadas
        campuses, edge_map, edge_traffic, graph, pheromones, congestion_by_edge = (
            await self._load_graph(
                mode=req.transport_mode,
                origin_id=origin_id,
                dest_id=dest_id,
            )
        )

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
        campuses, _, _, _, _, _ = await self._load_graph(mode=req.transport_mode)

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
        """
        Construye una variante de ruta tramo-a-tramo (estilo Moovit).
        Cada Segment trae su propia geometría, instrucción y color,
        permitiendo al frontend dibujar cada tramo con su perfil real.
        """
        cfg = ACOConfig.from_settings()
        apply_rain = rain_mmh > cfg.rain_threshold_mmh
        is_peak = _is_peak_hour()

        # ── 1) Lanzar todas las llamadas a OSRM/ORS en paralelo ──
        geometry_tasks = []
        for i in range(len(path) - 1):
            ca = campuses[path[i]]
            cb = campuses[path[i + 1]]
            edge = edge_map.get((path[i], path[i + 1]))
            transport = getattr(edge, "transport", "CAR") if edge else "CAR"
            seg_mode = mode_for_transport(transport, fallback=mode)
            geometry_tasks.append(
                get_path_geometry(
                    [(ca.latitude, ca.longitude), (cb.latitude, cb.longitude)],
                    seg_mode,
                )
            )
        segment_geometries = await asyncio.gather(*geometry_tasks)

        # ── 2) Construir steps, segments y geometría global ──
        steps: list[RouteStep] = []
        segments: list[Segment] = []
        full_geometry: list[list[float]] = []
        cum_t = cum_d = 0.0
        modes_set: set = set()

        origin_c = campuses[path[0]]
        steps.append(RouteStep(
            campus_id=origin_c.id,
            campus_name=origin_c.name,
            latitude=origin_c.latitude,
            longitude=origin_c.longitude,
            transport="",
            cumulative_time=0.0,
            cumulative_distance=0.0,
            traffic_factor=1.0,
            traffic_events=[],
        ))

        for i in range(len(path) - 1):
            a_id, b_id = path[i], path[i + 1]
            ca, cb = campuses[a_id], campuses[b_id]
            edge = edge_map.get((a_id, b_id))
            transport = getattr(edge, "transport", "CAR") if edge else "CAR"

            td = edge_traffic.get((a_id, b_id), {})
            tf = td.get("factor", 1.0)
            evs = td.get("events", [])
            rain_f = (
                cfg.rain_multiplier
                if apply_rain and transport in ("CAR", "SITP", "TM")
                else 1.0
            )
            if 0 < rain_mmh <= cfg.rain_threshold_mmh:
                from app.services.aco.rain_modifier import piecewise_travel_multiplier
                rain_f = piecewise_travel_multiplier(1.0, rain_mmh)

            edge_time = edge.travel_time if edge else 0.0
            edge_dist = edge.distance_km if edge else 0.0
            seg_time = edge_time * tf * rain_f
            cum_t += seg_time
            cum_d += edge_dist
            modes_set.add(transport)

            seg_geom = segment_geometries[i] or [
                [ca.latitude, ca.longitude],
                [cb.latitude, cb.longitude],
            ]

            if full_geometry and seg_geom:
                full_geometry.extend(seg_geom[1:])
            else:
                full_geometry.extend(seg_geom)

            meta = MODE_META.get(transport, MODE_META["CAR"])
            segments.append(Segment(
                mode=transport,
                from_name=ca.name,
                to_name=cb.name,
                duration_min=round(seg_time, 1),
                distance_km=round(edge_dist, 2),
                cost_cop=0,
                geometry=seg_geom,
                icon=meta["icon"],
                instruction=_build_instruction(transport, edge_dist, cb.name),
                color=meta["color"],
            ))

            steps.append(RouteStep(
                campus_id=cb.id,
                campus_name=cb.name,
                latitude=cb.latitude,
                longitude=cb.longitude,
                transport=transport,
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