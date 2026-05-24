import asyncio
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.route_edge import RouteEdge
from app.schemas.route import RouteRequest, RouteResponse, RouteStep, RouteVariant
from app.services.aco import ACOConfig, AntColonyOptimizer
from app.services.osrm_service import get_road_info
from app.services.traffic_service import compute_edge_factor
from app.services.weather_service import get_current_rain


class RouteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_optimal_route(self, req: RouteRequest) -> RouteResponse:
        campuses = {
            c.id: c for c in (await self.db.execute(select(Campus))).scalars().all()
        }
        edges = list((await self.db.execute(select(RouteEdge))).scalars().all())

        if req.origin_id == req.destination_id:
            raise ValueError("El origen y el destino deben ser diferentes")
        if req.origin_id not in campuses or req.destination_id not in campuses:
            raise ValueError("Origen o destino no existe")

        weather = await get_current_rain()
        apply_rain = req.rain or weather["is_raining"]
        cfg = ACOConfig(n_ants=35, n_iterations=100, alpha=1.0, beta=2.7)

        graph: dict[int, dict[int, float]] = {cid: {} for cid in campuses}
        pheromones: dict[int, dict[int, float]] = {cid: {} for cid in campuses}
        edge_info: dict[tuple[int, int], dict] = {}

        # Si una sede nueva no esta conectada en el grafo calibrado del workshop,
        # agregamos una arista virtual directa para que siempre pueda rutearse.
        edge_pairs = {(edge.origin_id, edge.dest_id) for edge in edges}
        for origin_id, dest_id in [
            (req.origin_id, req.destination_id),
            (req.destination_id, req.origin_id),
        ]:
            if (origin_id, dest_id) not in edge_pairs:
                origin = campuses[origin_id]
                dest = campuses[dest_id]
                edges.append(
                    SimpleNamespace(
                        id=None,
                        origin_id=origin_id,
                        dest_id=dest_id,
                        distance_km=0.0,
                        travel_time=35.0,
                        transport="TM" if req.transport_mode == "transit" else req.transport_mode.upper(),
                        pheromone=1.0,
                    )
                )
                edge_pairs.add((origin_id, dest_id))

        road_tasks = [
            get_road_info(
                campuses[edge.origin_id].latitude,
                campuses[edge.origin_id].longitude,
                campuses[edge.dest_id].latitude,
                campuses[edge.dest_id].longitude,
                req.transport_mode,
            )
            for edge in edges
        ]
        road_results = await asyncio.gather(*road_tasks)

        for edge, road in zip(edges, road_results):
            origin = campuses[edge.origin_id]
            dest = campuses[edge.dest_id]
            traffic_factor, affecting = await compute_edge_factor(
                self.db,
                origin.latitude,
                origin.longitude,
                dest.latitude,
                dest.longitude,
            )

            distance_km = (
                round(road["distance_m"] / 1000, 2)
                if road["distance_m"]
                else edge.distance_km
            )
            road_time = (
                round(road["duration_s"] / 60, 1)
                if road["duration_s"]
                else edge.travel_time
            )
            base_time = edge.travel_time if req.transport_mode == "transit" else road_time
            effective_time = base_time * traffic_factor
            if apply_rain:
                effective_time *= cfg.rain_penalty

            if req.mode == "shortest":
                cost = distance_km
            elif req.mode == "eco":
                clean_mode_bonus = 0.75 if edge.transport in {"WALK", "BIKE", "CABLE", "TM"} else 1.0
                cost = (effective_time * 0.7) + (distance_km * 0.3 * clean_mode_bonus)
            else:
                cost = effective_time

            graph[edge.origin_id][edge.dest_id] = max(cost, 0.01)
            pheromones[edge.origin_id][edge.dest_id] = edge.pheromone
            edge_info[(edge.origin_id, edge.dest_id)] = {
                "edge": edge,
                "geometry": road["geometry"],
                "distance_km": distance_km,
                "base_time": base_time,
                "effective_time": effective_time,
                "traffic_factor": traffic_factor,
                "events": affecting,
            }

        optimizer = AntColonyOptimizer(cfg)
        result = optimizer.optimize(
            graph,
            req.origin_id,
            req.destination_id,
            pheromones,
            False,
        )

        path = result["best_path"]
        if not path:
            raise ValueError("No se encontro ruta entre los nodos indicados")

        variants = [self._build_variant("Ruta optima ACO", path, campuses, edge_info)]
        seen_paths = {tuple(path)}

        for label in ["Alternativa 1", "Alternativa 2"]:
            penalized = {node: dict(neighbors) for node, neighbors in graph.items()}
            for a, b in zip(path, path[1:]):
                if b in penalized.get(a, {}):
                    penalized[a][b] *= 1.85

            alt = optimizer.optimize(
                penalized,
                req.origin_id,
                req.destination_id,
                pheromones,
                False,
            )
            alt_path = alt["best_path"]
            if alt_path and tuple(alt_path) not in seen_paths:
                seen_paths.add(tuple(alt_path))
                variants.append(self._build_variant(label, alt_path, campuses, edge_info))

        best_cost = result["best_cost"]
        delta = cfg.Q / best_cost if best_cost > 0 else 0
        for a, b in zip(path, path[1:]):
            edge_db = next((e for e in edges if e.origin_id == a and e.dest_id == b), None)
            if edge_db:
                edge_db.pheromone = edge_db.pheromone * (1 - cfg.evaporation) + delta
        await self.db.commit()

        selected = variants[0]
        return RouteResponse(
            origin=campuses[req.origin_id].name,
            destination=campuses[req.destination_id].name,
            total_time=selected.total_time,
            total_distance=selected.total_distance,
            transport_modes=selected.transport_modes,
            steps=selected.steps,
            selected=selected,
            alternatives=variants[1:],
            active_traffic_events=self._unique_events(edge_info, path),
            aco_iterations=result["iterations"],
            rain_penalty_applied=apply_rain,
        )

    def _build_variant(
        self,
        label: str,
        path: list[int],
        campuses: dict[int, Campus],
        edge_info: dict[tuple[int, int], dict],
    ) -> RouteVariant:
        steps: list[RouteStep] = []
        cum_time = 0.0
        cum_dist = 0.0
        transport_modes: set[str] = set()
        geometry: list[list[float]] = []

        for index, node_id in enumerate(path):
            campus = campuses[node_id]
            transport = ""
            traffic_factor = 1.0

            if index > 0:
                prev = path[index - 1]
                info = edge_info.get((prev, node_id))
                if info:
                    edge = info["edge"]
                    cum_time += info["effective_time"]
                    cum_dist += info["distance_km"]
                    transport = edge.transport
                    traffic_factor = info["traffic_factor"]
                    transport_modes.add(edge.transport)
                    segment = info["geometry"]
                    if segment:
                        geometry.extend(segment if not geometry else segment[1:])

            steps.append(
                RouteStep(
                    campus_id=campus.id,
                    campus_name=campus.name,
                    latitude=campus.latitude,
                    longitude=campus.longitude,
                    transport=transport,
                    cumulative_time=round(cum_time, 1),
                    cumulative_distance=round(cum_dist, 2),
                    traffic_factor=round(traffic_factor, 2),
                )
            )

        if not geometry:
            geometry = [
                [campuses[node_id].latitude, campuses[node_id].longitude]
                for node_id in path
            ]

        return RouteVariant(
            label=label,
            total_time=round(cum_time, 1),
            total_distance=round(cum_dist, 2),
            transport_modes=list(transport_modes),
            steps=steps,
            geometry=geometry,
            path=path,
        )

    def _unique_events(
        self,
        edge_info: dict[tuple[int, int], dict],
        path: list[int],
    ) -> list[dict]:
        events: dict[int, dict] = {}
        for a, b in zip(path, path[1:]):
            for event in edge_info.get((a, b), {}).get("events", []):
                events[event["id"]] = event
        return list(events.values())
