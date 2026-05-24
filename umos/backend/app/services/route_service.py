from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.campus import Campus
from app.models.route_edge import RouteEdge
from app.schemas.route import (
    RouteRequest, RouteResponse, RouteAlternative, RouteStep
)
from app.services.aco import AntColonyOptimizer, ACOConfig
from app.services.weather_service import get_current_rain
from app.services.traffic_service import compute_edge_factor
from app.services.osrm_service import get_road_info


class RouteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_optimal_route(self, req: RouteRequest) -> RouteResponse:
        # ── 1. Cargar datos base ──────────────────────────────────────────────
        campuses = {
            c.id: c
            for c in (await self.db.execute(select(Campus))).scalars().all()
        }
        edges = (await self.db.execute(select(RouteEdge))).scalars().all()
        edge_map = {(e.origin_id, e.dest_id): e for e in edges}

        if req.origin_id not in campuses or req.destination_id not in campuses:
            raise ValueError("Campus de origen o destino no encontrado")

        # ── 2. Calcular factores de tráfico por arista ────────────────────────
        edge_traffic: dict = {}
        graph:        dict = {cid: {} for cid in campuses}
        pheromones:   dict = {cid: {} for cid in campuses}

        for edge in edges:
            co = campuses[edge.origin_id]
            cd = campuses[edge.dest_id]

            factor, affecting = await compute_edge_factor(
                self.db,
                co.latitude, co.longitude,
                cd.latitude, cd.longitude,
            )
            edge_traffic[(edge.origin_id, edge.dest_id)] = {
                "factor":  factor,
                "events":  affecting,
            }
            graph[edge.origin_id][edge.dest_id] = {
                "cost":      edge.travel_time,
                "transport": edge.transport,
            }
            pheromones[edge.origin_id][edge.dest_id] = edge.pheromone

        # ── 3. Condición de lluvia ────────────────────────────────────────────
        weather    = await get_current_rain()
        apply_rain = req.rain or weather["is_raining"]

        # ── 4. Ejecutar ACO ───────────────────────────────────────────────────
        cfg = ACOConfig(n_ants=40, n_iterations=120, n_best=3)
        result = AntColonyOptimizer(cfg).optimize(
            graph,
            req.origin_id,
            req.destination_id,
            pheromones,
            apply_rain,
            req.transport_mode,
        )

        # ── 5. Actualizar feromonas en BD (aprendizaje ACO) ───────────────────
        best_path, best_cost = result["routes"][0]
        delta = cfg.Q / best_cost if best_cost > 0 else 0

        for i in range(len(best_path) - 1):
            e = edge_map.get((best_path[i], best_path[i + 1]))
            if e:
                e.pheromone = max(
                    e.pheromone * (1 - cfg.evaporation) + delta,
                    cfg.min_pheromone,
                )
        await self.db.commit()

        # ── 6. Construir alternativas con geometría real de calles ────────────
        all_events_seen: dict = {}
        alternatives: list[RouteAlternative] = []

        for alt_idx, (path, score) in enumerate(result["routes"]):
            alt = await self._build_alternative(
                alt_idx, path, score,
                campuses, edge_map, edge_traffic,
                apply_rain, cfg, req.transport_mode,
            )
            alternatives.append(alt)
            for ev in alt._raw_events:
                all_events_seen[ev.get("id")] = ev

        selected   = alternatives[0]
        alt_list   = alternatives[1:]
        all_ev_list = list(all_events_seen.values())

        return RouteResponse(
            origin=campuses[req.origin_id].name,
            destination=campuses[req.destination_id].name,
            selected=selected,
            alternatives=alt_list,
            aco_iterations=result["iterations"],
            rain_penalty_applied=apply_rain,
            active_traffic_events=all_ev_list,
            transport_mode=req.transport_mode,
        )

    # ─────────────────────────────────────────────────────────────────────────
    async def _build_alternative(
        self,
        idx:           int,
        path:          list[int],
        score:         float,
        campuses:      dict,
        edge_map:      dict,
        edge_traffic:  dict,
        apply_rain:    bool,
        cfg:           ACOConfig,
        mode:          str,
    ) -> RouteAlternative:

        # ── Geometría real de calles via OSRM ─────────────────────────────────
        full_geometry: list[list[float]] = []

        for i in range(len(path) - 1):
            ca = campuses[path[i]]
            cb = campuses[path[i + 1]]

            info = await get_road_info(
                ca.latitude,  ca.longitude,
                cb.latitude,  cb.longitude,
                mode,
            )
            seg = info["geometry"]

            # Evitar duplicar el punto de unión entre segmentos consecutivos
            if full_geometry and seg:
                seg = seg[1:]
            full_geometry.extend(seg)

        # ── Pasos y métricas acumuladas ───────────────────────────────────────
        steps:     list[RouteStep] = []
        cum_t  = 0.0
        cum_d  = 0.0
        modes_set:  set  = set()
        raw_events: list = []

        for i, nid in enumerate(path):
            c   = campuses[nid]
            tr  = ""
            tf  = 1.0
            evs = []

            if i > 0:
                e = edge_map.get((path[i - 1], nid))
                if e:
                    td     = edge_traffic.get((path[i - 1], nid), {})
                    tf     = td.get("factor", 1.0)
                    evs    = td.get("events", [])
                    raw_events.extend(evs)

                    rain_f = (
                        cfg.rain_penalty
                        if apply_rain and e.transport in ("CAR", "SITP", "TM")
                        else 1.0
                    )
                    cum_t += e.travel_time * tf * rain_f
                    cum_d += e.distance_km
                    tr     = e.transport
                    modes_set.add(e.transport)

            steps.append(RouteStep(
                campus_id=c.id,
                campus_name=c.name,
                latitude=c.latitude,
                longitude=c.longitude,
                transport=tr,
                cumulative_time=round(cum_t, 1),
                cumulative_distance=round(cum_d, 2),
                traffic_factor=round(tf, 2),
                traffic_events=[x["label"] for x in evs if "label" in x],
            ))

        labels = {
            0: "🥇 Ruta óptima",
            1: "🥈 Alternativa A",
            2: "🥉 Alternativa B",
        }

        alt = RouteAlternative(
            index=idx,
            label=labels.get(idx, f"Ruta {idx + 1}"),
            total_time=round(cum_t, 1),
            total_distance=round(cum_d, 2),
            geometry=full_geometry,
            steps=steps,
            transport_modes=list(modes_set),
            score=round(score, 2),
        )
        # atributo extra para que el caller pueda leer los eventos sin schema
        alt._raw_events = raw_events
        return alt