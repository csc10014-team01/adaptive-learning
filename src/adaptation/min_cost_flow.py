"""Small deterministic integral min-cost flow; no optimization dependency.

Successive shortest augmenting paths use Bellman-Ford because convex marginal
costs and residual edges can be negative. Stable insertion order breaks ties.
The planner sends at most ten units through these small networks.
"""

from collections.abc import Hashable
from dataclasses import dataclass


@dataclass
class Edge:
    target: int
    reverse: int
    capacity: int
    cost: int
    initial_capacity: int

    @property
    def flow(self) -> int:
        return self.initial_capacity - self.capacity


class MinCostFlow:
    def __init__(self):
        self.nodes: dict[Hashable, int] = {}
        self.graph: list[list[Edge]] = []

    @property
    def total_cost(self) -> int:
        return sum(
            edge.flow * edge.cost
            for edges in self.graph
            for edge in edges
            if edge.initial_capacity
        )

    def _node(self, name: Hashable) -> int:
        if name not in self.nodes:
            self.nodes[name] = len(self.graph)
            self.graph.append([])
        return self.nodes[name]

    def add_edge(
        self, source: Hashable, target: Hashable, capacity: int, cost: int = 0
    ) -> Edge:
        start, end = self._node(source), self._node(target)
        forward = Edge(end, len(self.graph[end]), capacity, cost, capacity)
        reverse = Edge(start, len(self.graph[start]), 0, -cost, 0)
        self.graph[start].append(forward)
        self.graph[end].append(reverse)
        return forward

    def send(self, source: Hashable, target: Hashable, total: int) -> bool:
        start, end = self._node(source), self._node(target)
        for _ in range(total):
            distances = [None] * len(self.graph)
            previous = [None] * len(self.graph)
            distances[start] = 0
            for _ in range(len(self.graph) - 1):
                changed = False
                for node, edges in enumerate(self.graph):
                    if distances[node] is None:
                        continue
                    for index, edge in enumerate(edges):
                        distance = distances[node] + edge.cost
                        if edge.capacity and (
                            distances[edge.target] is None
                            or distance < distances[edge.target]
                        ):
                            distances[edge.target] = distance
                            previous[edge.target] = (node, index)
                            changed = True
                if not changed:
                    break
            if previous[end] is None:
                return False
            node = end
            while node != start:
                parent, index = previous[node]
                edge = self.graph[parent][index]
                edge.capacity -= 1
                self.graph[node][edge.reverse].capacity += 1
                node = parent
        return True
