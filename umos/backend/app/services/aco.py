import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ACOConfig:
    """Parámetros configurables del algoritmo ACO."""
    n_ants: int = 30
    n_iterations: int = 100
    alpha: float = 1.0       # peso de feromonas
    beta: float = 2.5        # peso de heurística (1/costo)
    evaporation: float = 0.3 # tasa de evaporación
    Q: float = 100.0         # constante de depósito de feromonas
    rain_penalty: float = 1.632  # +63.2% por lluvia (dato real W1)


class AntColonyOptimizer:
    """
    Optimizador de rutas multimodales usando Ant Colony Optimization.
    Basado en el sistema AS (Ant System) de Dorigo et al.
    Parámetros calibrados con datos reales del proyecto UMOS (Workshop 1).
    """

    def __init__(self, config: ACOConfig = ACOConfig()):
        self.cfg = config

    def optimize(
        self,
        graph: dict[int, dict[int, float]],
        origin: int,
        destination: int,
        pheromones: Optional[dict] = None,
        rain: bool = False,
    ) -> dict:
        """
        Encuentra la ruta óptima entre origin y destination.

        Args:
            graph: {node_id: {neighbor_id: cost}} — grafo de adyacencia
            origin: nodo de inicio
            destination: nodo de destino
            pheromones: feromonas iniciales (None = todas en 1.0)
            rain: si True aplica penalización por lluvia (+63.2% al tiempo)

        Returns:
            dict con best_path, best_cost, iterations usadas
        """
        nodes = list(graph.keys())
        if origin not in nodes or destination not in nodes:
            raise ValueError("Nodo de origen o destino no existe en el grafo")

        # Inicializar feromonas
        pher = pheromones or {
            i: {j: 1.0 for j in graph[i]} for i in graph
        }

        best_path: list[int] = []
        best_cost: float = float("inf")

        for iteration in range(self.cfg.n_iterations):
            paths = []
            costs = []

            for _ in range(self.cfg.n_ants):
                path, cost = self._construct_solution(
                    graph, pher, origin, destination, rain
                )
                if path:
                    paths.append(path)
                    costs.append(cost)

            # Actualizar mejor solución global
            if costs:
                idx = int(np.argmin(costs))
                if costs[idx] < best_cost:
                    best_cost = costs[idx]
                    best_path = paths[idx]

            # Evaporación de feromonas
            for i in pher:
                for j in pher[i]:
                    pher[i][j] *= (1 - self.cfg.evaporation)
                    pher[i][j] = max(pher[i][j], 0.01)  # mínimo para evitar estancamiento

            # Depósito de feromonas de las mejores hormigas
            for path, cost in zip(paths, costs):
                delta = self.cfg.Q / cost if cost > 0 else 0
                for k in range(len(path) - 1):
                    a, b = path[k], path[k + 1]
                    if b in pher.get(a, {}):
                        pher[a][b] += delta

        return {
            "best_path": best_path,
            "best_cost": best_cost,
            "iterations": self.cfg.n_iterations,
            "rain_applied": rain,
        }

    def _construct_solution(
        self,
        graph: dict,
        pheromones: dict,
        origin: int,
        destination: int,
        rain: bool,
    ) -> tuple[list[int], float]:
        """Una hormiga construye su camino usando regla de transición probabilística."""
        current = origin
        visited = {current}
        path = [current]
        total_cost = 0.0
        max_steps = len(graph) * 2

        for _ in range(max_steps):
            if current == destination:
                break

            neighbors = [
                n for n in graph.get(current, {}) if n not in visited
            ]

            if not neighbors:
                return [], float("inf")

            next_node = self._probabilistic_choice(
                current, neighbors, graph, pheromones, rain
            )
            edge_cost = graph[current][next_node]

            if rain:
                edge_cost *= self.cfg.rain_penalty

            path.append(next_node)
            visited.add(next_node)
            total_cost += edge_cost
            current = next_node

        if path[-1] != destination:
            return [], float("inf")

        return path, total_cost

    def _probabilistic_choice(
        self,
        current: int,
        neighbors: list[int],
        graph: dict,
        pheromones: dict,
        rain: bool,
    ) -> int:
        """Regla de transición ACO: τ^α × η^β / Σ(τ^α × η^β)."""
        scores = []
        for n in neighbors:
            tau = pheromones.get(current, {}).get(n, 1.0)
            cost = graph[current][n]
            if rain:
                cost *= self.cfg.rain_penalty
            eta = 1.0 / cost if cost > 0 else 1.0
            scores.append((tau ** self.cfg.alpha) * (eta ** self.cfg.beta))

        total = sum(scores)
        if total == 0:
            return neighbors[0]

        probs = [s / total for s in scores]
        return int(np.random.choice(neighbors, p=probs))
