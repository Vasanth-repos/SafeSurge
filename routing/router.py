"""
Layer 18 — Risk-Aware Emergency Router:
Computes shortest paths via Dijkstra using dynamic risk penalties and uncertainty weighting,
with automated avoided-road diagnostics and graceful fallback when no safe route exists.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple
import networkx as nx
from routing.models import RoadEdge, RoadEdgeState, AvoidedRoad, RouteResult
from routing.graph import DirectedRoadGraph
from routing.costs import calculate_cost


class EmergencyRouter:
    def __init__(
        self,
        road_graph: DirectedRoadGraph,
        risk_penalties: Optional[Mapping[str, float]] = None,
        uncertainty_weight: float = 120.0,
        unsafe_edges_blocked: bool = True,
    ):
        self.road_graph = road_graph
        self.risk_penalties = dict(risk_penalties) if risk_penalties else {"SAFE": 0.0, "WATCH": 120.0, "HIGH": 600.0}
        self.uncertainty_weight = float(uncertainty_weight)
        self.unsafe_edges_blocked = bool(unsafe_edges_blocked)

    def find_route(
        self,
        origin: str,
        destination: str,
        simulation_id: str,
        timestamp_seconds: int,
        edge_states: Mapping[str, RoadEdgeState],
    ) -> RouteResult:
        """
        Finds optimal route between origin and destination using dynamic costs.
        """
        # Build weighted networkx graph
        g = nx.DiGraph()
        avoided_roads: List[AvoidedRoad] = []

        # Ensure all graph nodes are initialized
        for n in self.road_graph.graph.nodes():
            g.add_node(n)

        for r_id, state in edge_states.items():
            cost = calculate_cost(
                travel_time_seconds=state.travel_time_seconds,
                risk=state.risk,
                confidence=state.confidence,
                risk_penalties=self.risk_penalties,
                uncertainty_weight=self.uncertainty_weight,
                unsafe_edges_blocked=self.unsafe_edges_blocked,
            )

            if state.risk == "UNSAFE":
                avoided_roads.append(
                    AvoidedRoad(
                        road_id=r_id,
                        reason="UNSAFE",
                        risk=state.risk,
                        depth_cm=state.flood_depth_cm,
                    )
                )

            if cost < float("inf"):
                g.add_edge(
                    state.from_node,
                    state.to_node,
                    road_id=r_id,
                    weight=cost,
                    travel_time=state.travel_time_seconds,
                    confidence=state.confidence,
                )

        if not self.road_graph.graph.has_node(origin) or not self.road_graph.graph.has_node(destination):
            return RouteResult(
                route_available=False,
                simulation_id=simulation_id,
                timestamp_seconds=timestamp_seconds,
                origin=origin,
                destination=destination,
                road_path=(),
                node_path=(),
                total_travel_time_seconds=0.0,
                total_cost=0.0,
                minimum_confidence=0.0,
                avoided_roads=tuple(avoided_roads),
                reason="ORIGIN_OR_DESTINATION_UNREACHABLE",
            )

        if not nx.has_path(g, source=origin, target=destination):
            return RouteResult(
                route_available=False,
                simulation_id=simulation_id,
                timestamp_seconds=timestamp_seconds,
                origin=origin,
                destination=destination,
                road_path=(),
                node_path=(),
                total_travel_time_seconds=0.0,
                total_cost=0.0,
                minimum_confidence=0.0,
                avoided_roads=tuple(avoided_roads),
                reason="NO_SAFE_ROUTE",
            )

        try:
            node_path = nx.shortest_path(g, source=origin, target=destination, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return RouteResult(
                route_available=False,
                simulation_id=simulation_id,
                timestamp_seconds=timestamp_seconds,
                origin=origin,
                destination=destination,
                road_path=(),
                node_path=(),
                total_travel_time_seconds=0.0,
                total_cost=0.0,
                minimum_confidence=0.0,
                avoided_roads=tuple(avoided_roads),
                reason="NO_SAFE_ROUTE",
            )

        # Extract edge sequence and calculate aggregates
        road_path = []
        total_travel_time = 0.0
        total_cost = 0.0
        min_conf = 1.0

        for u, v in zip(node_path[:-1], node_path[1:]):
            edge_data = g.get_edge_data(u, v)
            road_path.append(edge_data["road_id"])
            total_travel_time += edge_data["travel_time"]
            total_cost += edge_data["weight"]
            min_conf = min(min_conf, edge_data["confidence"])

        return RouteResult(
            route_available=True,
            simulation_id=simulation_id,
            timestamp_seconds=timestamp_seconds,
            origin=origin,
            destination=destination,
            road_path=tuple(road_path),
            node_path=tuple(node_path),
            total_travel_time_seconds=total_travel_time,
            total_cost=total_cost,
            minimum_confidence=min_conf,
            avoided_roads=tuple(avoided_roads),
            reason=None,
        )
