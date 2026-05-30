"""
Recomendación TransMilenio/SITP con ACO sobre grafo GTFS.
"""

from __future__ import annotations

import math

from app.services.aco import AntColonyOptimizer, ACOConfig
from app.services.gtfs_service import get_gtfs, make_ants, ANTS_PER_ROUTE


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _walk_min(dist_m: float) -> float:
    return max(dist_m / 83.3, 1.0)


class TransitACOService:
    def __init__(self):
        self.gtfs = get_gtfs()
        self.cfg = ACOConfig(n_ants=30, n_iterations=80, n_best=5)

    def _build_graph(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> tuple[dict, dict, dict, list[dict], list[dict]]:
        origin_stops = self.gtfs.nearest_stops(origin_lat, origin_lon, 8, 3500)
        dest_stops = self.gtfs.nearest_stops(dest_lat, dest_lon, 8, 3500)
        if not origin_stops or not dest_stops:
            raise ValueError("No hay paradas GTFS cerca del origen o destino")

        stop_to_node: dict[str, int] = {}
        node_meta: dict[int, dict] = {
            0: {"type": "origin", "lat": origin_lat, "lon": origin_lon},
            9999: {"type": "dest", "lat": dest_lat, "lon": dest_lon},
        }
        n = 1000
        for s in origin_stops[:6] + dest_stops[:6]:
            if s["id"] not in stop_to_node:
                stop_to_node[s["id"]] = n
                node_meta[n] = {"type": "stop", **s}
                n += 1

        graph: dict[int, dict[int, dict]] = {k: {} for k in node_meta}
        edge_meta: dict[tuple[int, int], dict] = {}

        for s in origin_stops[:6]:
            nid = stop_to_node[s["id"]]
            graph[0][nid] = {"cost": _walk_min(s["distance_m"]), "transport": "WALK"}
            edge_meta[(0, nid)] = {"mode": "WALK", "route_id": None}

        for s in dest_stops[:6]:
            nid = stop_to_node[s["id"]]
            d = _haversine(s["lat"], s["lon"], dest_lat, dest_lon)
            graph[nid][9999] = {"cost": _walk_min(d), "transport": "WALK"}
            edge_meta[(nid, 9999)] = {"mode": "WALK", "route_id": None}

        candidate_routes: set[str] = set()
        for os in origin_stops[:6]:
            for ds in dest_stops[:6]:
                candidate_routes.update(self.gtfs.routes_connecting(os["id"], ds["id"]))

        if not candidate_routes:
            for os in origin_stops[:6]:
                candidate_routes.update(list(self.gtfs.routes_serving_stop(os["id"]))[:25])

        for rid in list(candidate_routes)[:100]:
            seq = self.gtfs.route_stops.get(rid, [])
            indexed = [(stop_to_node[s], s) for s in seq if s in stop_to_node]
            for i in range(len(indexed) - 1):
                na, sa = indexed[i]
                nb, sb = indexed[i + 1]
                seg = self.gtfs.stop_sequence_segment(rid, sa, sb)
                cost = self.gtfs.segment_travel_min(seg) if len(seg) >= 2 else 3.0
                if nb not in graph[na] or cost < graph[na][nb]["cost"]:
                    graph[na][nb] = {"cost": cost, "transport": "TM"}
                    edge_meta[(na, nb)] = {
                        "mode": "TM",
                        "route_id": rid,
                        "from_stop": sa,
                        "to_stop": sb,
                    }

        return graph, edge_meta, node_meta, origin_stops, dest_stops

    def _route_payload(
        self,
        rid: str,
        score: float,
        board_stop_id: str,
        alight_stop_id: str,
        dest_faculty_name: str,
    ) -> dict | None:
        route = self.gtfs.routes.get(rid, {})
        geometry = self.gtfs.route_geometry(rid)
        if len(geometry) < 3:
            return None

        board = self.gtfs.stops.get(board_stop_id, {})
        alight = self.gtfs.stops.get(alight_stop_id, {})
        short = route.get("short_name", rid)
        long = route.get("long_name", "")

        return {
            "route_id": rid,
            "short_name": short,
            "long_name": long,
            "color": f"#{route.get('color', 'e11d48')}",
            "geometry": geometry,
            "aco_score": round(min(1.0, 100 / score), 3) if score > 0 else 1.0,
            "travel_time_min": round(score, 1),
            "board_at": board.get("name", "Parada origen"),
            "alight_at": alight.get("name", "Parada destino"),
            "board_stop_id": board_stop_id,
            "alight_stop_id": alight_stop_id,
            "instruction": (
                f"Sube en la ruta {short} ({long}) en {board.get('name', '?')}. "
                f"Baja en {alight.get('name', '?')} y camina a {dest_faculty_name or 'la facultad destino'}."
            ),
            "ants": make_ants(rid, ANTS_PER_ROUTE),
            "simulation_period_sec": 12,
        }

    def recommend(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        dest_faculty_name: str = "",
        origin_faculty_name: str = "",
    ) -> dict:
        self.gtfs.load_shapes()

        try:
            graph, edge_meta, _, origin_stops, dest_stops = self._build_graph(
                origin_lat, origin_lon, dest_lat, dest_lon
            )
        except ValueError as e:
            return {"error": str(e), "recommended_routes": []}

        result = AntColonyOptimizer(self.cfg).optimize(graph, 0, 9999, max_alternatives=5)
        o_stop = origin_stops[0]["id"]
        d_stop = dest_stops[0]["id"]

        recommended: list[dict] = []
        seen: set[str] = set()

        paths = result.get("routes") or [(result.get("best_path"), result.get("best_cost"))]
        for path, score in paths:
            if not path:
                continue
            route_ids_in_path: list[str] = []
            for i in range(len(path) - 1):
                em = edge_meta.get((path[i], path[i + 1]))
                if em and em.get("route_id"):
                    route_ids_in_path.append(em["route_id"])
                    if em.get("from_stop"):
                        o_stop = em["from_stop"]
                    if em.get("to_stop"):
                        d_stop = em["to_stop"]

            for rid in route_ids_in_path or list(self.gtfs.routes_connecting(o_stop, d_stop)):
                if rid in seen:
                    continue
                seen.add(rid)
                payload = self._route_payload(rid, score or 1, o_stop, d_stop, dest_faculty_name)
                if payload:
                    recommended.append(payload)

        if not recommended:
            recommended = self._nearby_routes(origin_stops, dest_stops, dest_faculty_name)

        direct = []
        for os in origin_stops[:4]:
            for ds in dest_stops[:4]:
                direct.extend(self.gtfs.routes_connecting(os["id"], ds["id"]))

        return {
            "source": "GTFS-2026-04-29 + ACO",
            "origin_faculty": origin_faculty_name,
            "destination_faculty": dest_faculty_name,
            "origin_stop": origin_stops[0],
            "destination_stop": dest_stops[0],
            "origin_nearby_stations": origin_stops,
            "destination_nearby_stations": dest_stops,
            "direct_route_ids": list(dict.fromkeys(direct))[:12],
            "direct_match": bool(direct),
            "recommended_routes": recommended[:4],
            "routes": recommended[:4],
            "summary": self._summary(recommended, dest_faculty_name),
            "vehicles": self._ant_positions(recommended[:4]),
        }

    def _nearby_routes(
        self, origin_stops: list, dest_stops: list, faculty: str
    ) -> list[dict]:
        out = []
        if not origin_stops:
            return out
        o_stop = origin_stops[0]["id"]
        d_stop = dest_stops[0]["id"] if dest_stops else o_stop
        for rid in self.gtfs.routes_serving_stop(o_stop)[:8]:
            p = self._route_payload(rid, 50, o_stop, d_stop, faculty)
            if p:
                out.append(p)
        return out[:4]

    def _summary(self, routes: list[dict], faculty: str) -> str:
        if not routes:
            return "No hay rutas GTFS cercanas. Acércate a una estación TransMilenio."
        r = routes[0]
        return (
            f"Para llegar a {faculty or 'destino'}, la ruta más conveniente es "
            f"{r['short_name']} ({r['long_name']}). Sube en {r['board_at']}."
        )

    def _ant_positions(self, routes: list[dict]) -> list[dict]:
        from app.services.gtfs_service import point_at_progress
        import time

        t = time.time()
        vehicles = []
        for route in routes:
            geom = route.get("geometry") or []
            period = route.get("simulation_period_sec", 12)
            for ant in route.get("ants", []):
                progress = (t / period + ant["offset"]) % 1
                pt = point_at_progress(geom, progress)
                if pt:
                    vehicles.append({
                        "id": ant["id"],
                        "route_id": route["route_id"],
                        "label": route["short_name"],
                        "latitude": pt[0],
                        "longitude": pt[1],
                        "progress": round(progress, 3),
                    })
        return vehicles
