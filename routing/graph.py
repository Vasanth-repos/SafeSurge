"""
Layer 18 — Directed Road Network Graph:
Maintains directed topology and edge states updated dynamically from flood risk snapshots.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import networkx as nx

from roads.models import RoadRisk
from routing.models import RoadEdge, RoadEdgeState


class DirectedRoadGraph:
    def __init__(self, edges: Sequence[RoadEdge] | None = None):
        self.graph = nx.DiGraph()
        self.edge_by_id: dict[str, RoadEdge] = {}
        if edges:
            for e in edges:
                self.add_edge(e)

    def add_edge(self, edge: RoadEdge) -> None:
        self.edge_by_id[edge.road_id] = edge
        self.graph.add_edge(
            edge.from_node,
            edge.to_node,
            road_id=edge.road_id,
            travel_time=edge.travel_time_seconds,
            length=edge.length_m,
        )

    def get_edge(self, road_id: str) -> RoadEdge | None:
        return self.edge_by_id.get(road_id)

    def build_dynamic_states(
        self,
        road_risks: Mapping[str, RoadRisk],
    ) -> dict[str, RoadEdgeState]:
        states = {}
        for r_id, edge in self.edge_by_id.items():
            risk_obj = road_risks.get(r_id)
            if risk_obj is not None:
                d = risk_obj.mean_depth_cm
                r = risk_obj.risk
                c = risk_obj.confidence
            else:
                d = 0.0
                r = "SAFE"
                c = 1.0

            states[r_id] = RoadEdgeState(
                road_id=r_id,
                from_node=edge.from_node,
                to_node=edge.to_node,
                travel_time_seconds=edge.travel_time_seconds,
                flood_depth_cm=d,
                risk=r,
                confidence=c,
            )
        return states
