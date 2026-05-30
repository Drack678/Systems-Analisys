import numpy as np
from typing import Optional

from app.services.aco.config import ACOConfig
from app.services.aco.rain_modifier import edge_weight_multiplier, suppress_cycling_edges


class AntColonyOptimizer:
    """
    ACO multimodal (Ant System + elitist ants).
    Parámetros calibrados UMOS W1/W4.
    """

    def __init__(self, config: Optional[ACOConfig] = None):
        self.cfg = config or ACOConfig.from_settings()

    def optimize(
        self,
        graph: dict[int, dict[int, dict]],
        origin: int,
        destination: int,
        pheromones: Optional[dict] = None,
        rain_mmh: float = 0.0,
        congestion_by_edge: Optional[dict] = None,
        bus_bunching_edges: Optional[set] = None,
        max_alternatives: int = 3,
    ) -> dict:
        nodes = list(graph.keys())
        if origin not in nodes or destination not in nodes:
            raise ValueError("Nodo de origen o destino no existe en el grafo")

        working_graph = suppress_cycling_edges(
            graph, rain_mmh, self.cfg.rain_threshold_mmh
        )
        pher = pheromones or {
            i: {j: 1.0 for j in working_graph.get(i, {})} for i in working_graph
        }
        congestion_by_edge = congestion_by_edge or {}
        bus_bunching_edges = bus_bunching_edges or set()

        best_path: list[int] = []
        best_cost: float = float("inf")
        convergence_step = self.cfg.n_iterations
        all_solutions: dict[tuple, float] = {}

        for iteration in range(self.cfg.n_iterations):
            paths: list[list[int]] = []
            costs: list[float] = []

            for _ in range(self.cfg.n_ants):
                path, cost = self._construct_solution(
                    working_graph,
                    pher,
                    origin,
                    destination,
                    rain_mmh,
                    congestion_by_edge,
                    bus_bunching_edges,
                )
                if path:
                    paths.append(path)
                    costs.append(cost)
                    key = tuple(path)
                    if key not in all_solutions or cost < all_solutions[key]:
                        all_solutions[key] = cost

            if costs:
                idx = int(np.argmin(costs))
                if costs[idx] < best_cost:
                    best_cost = costs[idx]
                    best_path = paths[idx]
                    convergence_step = iteration + 1

            for i in pher:
                for j in pher[i]:
                    pher[i][j] *= 1 - self.cfg.evaporation
                    pher[i][j] = max(pher[i][j], self.cfg.min_pheromone)

            ranked = sorted(zip(paths, costs), key=lambda x: x[1])[: self.cfg.n_best]
            for path, cost in ranked:
                delta = self.cfg.Q / cost if cost > 0 else 0
                for k in range(len(path) - 1):
                    a, b = path[k], path[k + 1]
                    if b in pher.get(a, {}):
                        pher[a][b] += delta

            if best_path:
                elite_delta = (self.cfg.n_best * self.cfg.Q) / best_cost
                for k in range(len(best_path) - 1):
                    a, b = best_path[k], best_path[k + 1]
                    if b in pher.get(a, {}):
                        pher[a][b] += elite_delta

        sorted_routes = sorted(all_solutions.items(), key=lambda x: x[1])
        routes = [(list(k), v) for k, v in sorted_routes[:max_alternatives]]
        if not routes and best_path:
            routes = [(best_path, best_cost)]

        pheromone_snapshot = {
            f"{a}->{b}": round(pher.get(a, {}).get(b, 0), 4)
            for a in pher
            for b in pher[a]
        }

        return {
            "best_path": best_path,
            "best_cost": best_cost,
            "routes": routes,
            "iterations": self.cfg.n_iterations,
            "convergence_step": convergence_step,
            "rain_applied": rain_mmh > self.cfg.rain_threshold_mmh,
            "pheromones": pher,
            "pheromone_snapshot": pheromone_snapshot,
        }

    def _edge_cost(
        self,
        graph: dict,
        current: int,
        nxt: int,
        rain_mmh: float,
        congestion_by_edge: dict,
        bus_bunching_edges: set,
    ) -> float:
        edge = graph[current][nxt]
        base = edge["cost"]
        mode = edge.get("transport", "")
        key = (current, nxt)
        congestion = congestion_by_edge.get(key, 1.0)
        bunching = key in bus_bunching_edges
        mult = edge_weight_multiplier(
            rain_mmh=rain_mmh,
            mode=mode,
            congestion_factor=congestion,
            bus_bunching=bunching,
            bus_bunching_beta=self.cfg.bus_bunching_beta,
            rain_multiplier=self.cfg.rain_multiplier,
            rain_threshold=self.cfg.rain_threshold_mmh,
        )
        if mult == float("inf"):
            return float("inf")
        return base * mult

    def _construct_solution(
        self,
        graph: dict,
        pheromones: dict,
        origin: int,
        destination: int,
        rain_mmh: float,
        congestion_by_edge: dict,
        bus_bunching_edges: set,
    ) -> tuple[list[int], float]:
        current = origin
        visited = {current}
        path = [current]
        total_cost = 0.0
        max_steps = len(graph) * 2

        for _ in range(max_steps):
            if current == destination:
                break

            neighbors = [n for n in graph.get(current, {}) if n not in visited]
            if not neighbors:
                return [], float("inf")

            next_node = self._probabilistic_choice(
                current,
                neighbors,
                graph,
                pheromones,
                rain_mmh,
                congestion_by_edge,
                bus_bunching_edges,
            )
            edge_cost = self._edge_cost(
                graph,
                current,
                next_node,
                rain_mmh,
                congestion_by_edge,
                bus_bunching_edges,
            )
            if edge_cost == float("inf"):
                return [], float("inf")

            path.append(next_node)
            visited.add(next_node)
            total_cost += edge_cost
            current = next_node

        if not path or path[-1] != destination:
            return [], float("inf")
        return path, total_cost

    def _probabilistic_choice(
        self,
        current: int,
        neighbors: list[int],
        graph: dict,
        pheromones: dict,
        rain_mmh: float,
        congestion_by_edge: dict,
        bus_bunching_edges: set,
    ) -> int:
        scores = []
        for n in neighbors:
            cost = self._edge_cost(
                graph, current, n, rain_mmh, congestion_by_edge, bus_bunching_edges
            )
            if cost == float("inf"):
                scores.append(0.0)
                continue
            tau = pheromones.get(current, {}).get(n, 1.0)
            eta = 1.0 / cost if cost > 0 else 1.0
            scores.append((tau ** self.cfg.alpha) * (eta ** self.cfg.beta))

        total = sum(scores)
        if total == 0:
            return neighbors[0]
        probs = [s / total for s in scores]
        return int(np.random.choice(neighbors, p=probs))
