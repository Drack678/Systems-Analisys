from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.campus import Campus
from app.models.route_edge import RouteEdge
from app.schemas.route import RouteRequest, RouteResponse, RouteStep
from app.services.aco import AntColonyOptimizer, ACOConfig
from app.services.weather_service import get_current_rain


class RouteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_optimal_route(self, req: RouteRequest) -> RouteResponse:
        # 1. Cargar todos los campus y aristas
        campuses = {c.id: c for c in (await self.db.execute(select(Campus))).scalars().all()}
        edges = (await self.db.execute(select(RouteEdge))).scalars().all()

        # 2. Construir grafo de adyacencia {origen: {destino: costo}}
        graph: dict[int, dict[int, float]] = {cid: {} for cid in campuses}
        pheromones: dict[int, dict[int, float]] = {cid: {} for cid in campuses}

        for edge in edges:
            cost = edge.travel_time if req.mode == "fastest" else edge.distance_km
            graph[edge.origin_id][edge.dest_id] = cost
            pheromones[edge.origin_id][edge.dest_id] = edge.pheromone

        # 3. Detectar lluvia automáticamente
        weather = await get_current_rain()
        apply_rain = req.rain or weather["is_raining"]

        # 4. Ejecutar ACO
        cfg = ACOConfig(n_ants=25, n_iterations=80, alpha=1.0, beta=2.5)
        optimizer = AntColonyOptimizer(cfg)
        result = optimizer.optimize(graph, req.origin_id, req.destination_id,
                                    pheromones, apply_rain)

        path = result["best_path"]
        if not path:
            raise ValueError("No se encontró ruta entre los nodos indicados")

        # 5. Actualizar feromonas en base de datos (aprendizaje)
        best_cost = result["best_cost"]
        delta = cfg.Q / best_cost if best_cost > 0 else 0
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            edge_db = next((e for e in edges if e.origin_id == a and e.dest_id == b), None)
            if edge_db:
                edge_db.pheromone = edge_db.pheromone * (1 - cfg.evaporation) + delta
        await self.db.commit()

        # 6. Construir respuesta con pasos
        steps: list[RouteStep] = []
        cum_time = 0.0
        cum_dist = 0.0
        transport_modes: set[str] = set()

        for i, node_id in enumerate(path):
            campus = campuses[node_id]
            if i > 0:
                prev = path[i - 1]
                edge = next((e for e in edges if e.origin_id == prev and e.dest_id == node_id), None)
                if edge:
                    t = edge.travel_time * (cfg.rain_penalty if apply_rain else 1.0)
                    cum_time += t
                    cum_dist += edge.distance_km
                    transport_modes.add(edge.transport)

            steps.append(RouteStep(
                campus_id=campus.id,
                campus_name=campus.name,
                latitude=campus.latitude,
                longitude=campus.longitude,
                transport=edges[0].transport if i == 0 else (edge.transport if edge else ""),
                cumulative_time=round(cum_time, 1),
                cumulative_distance=round(cum_dist, 2),
            ))

        origin_name = campuses[req.origin_id].name
        dest_name = campuses[req.destination_id].name

        return RouteResponse(
            origin=origin_name,
            destination=dest_name,
            total_time=round(cum_time, 1),
            total_distance=round(cum_dist, 2),
            transport_modes=list(transport_modes),
            steps=steps,
            aco_iterations=result["iterations"],
            rain_penalty_applied=apply_rain,
        )