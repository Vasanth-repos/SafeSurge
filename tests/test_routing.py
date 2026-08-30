"""
Layer 18 — Dynamic Risk-Aware Routing Tests:
Verifies dynamic policy costs, Dijkstra shortest path finding, and path adaptation:
A -> B -> D (safe baseline) -> A -> C -> D (when B->D unsafe) -> NO_SAFE_ROUTE (when C->D unsafe).
"""

import pytest

from routing.costs import calculate_cost
from routing.graph import DirectedRoadGraph
from routing.models import RoadEdge, RoadEdgeState
from routing.router import EmergencyRouter


def test_routing_cost_calculation():
    """Verifies cost function with risk penalties and uncertainty weighting."""
    penalties = {"SAFE": 0.0, "WATCH": 120.0, "HIGH": 600.0}

    # SAFE, high confidence (1.0) -> cost = travel_time = 60
    c_safe = calculate_cost(60.0, "SAFE", 1.0, penalties, uncertainty_weight=120.0)
    assert c_safe == pytest.approx(60.0)

    # HIGH, partial confidence (0.5) -> cost = 60 + 600 + 120*(0.5) = 720
    c_high = calculate_cost(60.0, "HIGH", 0.5, penalties, uncertainty_weight=120.0)
    assert c_high == pytest.approx(720.0)

    # UNSAFE with blocking -> float('inf')
    c_unsafe = calculate_cost(60.0, "UNSAFE", 1.0, penalties, unsafe_edges_blocked=True)
    assert c_unsafe == float("inf")


def test_dynamic_path_adaptation_and_avoidance():
    """
    Topology:
      R1: A -> B (60s)
      R2: B -> D (60s)
      R3: A -> C (60s)
      R4: C -> D (60s)

    Step 1: All roads SAFE -> Path = A -> B -> D (time=120s)
    Step 2: R2 (B->D) becomes UNSAFE -> Path = A -> C -> D (time=120s)
    Step 3: R4 (C->D) also becomes UNSAFE -> NO_SAFE_ROUTE
    """
    edges = [
        RoadEdge("R1", "A", "B", 60.0),
        RoadEdge("R2", "B", "D", 60.0),
        RoadEdge("R3", "A", "C", 60.0),
        RoadEdge("R4", "C", "D", 60.0),
    ]
    graph = DirectedRoadGraph(edges)
    router = EmergencyRouter(graph)

    # Step 1: All SAFE
    states1 = {
        "R1": RoadEdgeState("R1", "A", "B", 60.0, 0.0, "SAFE", 1.0),
        "R2": RoadEdgeState("R2", "B", "D", 60.0, 0.0, "SAFE", 1.0),
        "R3": RoadEdgeState("R3", "A", "C", 60.0, 0.0, "SAFE", 1.0),
        "R4": RoadEdgeState("R4", "C", "D", 60.0, 0.0, "SAFE", 1.0),
    }
    r1 = router.find_route("A", "D", "sim_001", 0, states1)
    assert r1.route_available is True
    assert r1.node_path == ("A", "B", "D")
    assert r1.road_path == ("R1", "R2")

    # Step 2: R2 (B->D) becomes UNSAFE
    states2 = dict(states1)
    states2["R2"] = RoadEdgeState("R2", "B", "D", 60.0, 30.0, "UNSAFE", 0.9)
    r2 = router.find_route("A", "D", "sim_001", 600, states2)
    assert r2.route_available is True
    assert r2.node_path == ("A", "C", "D")
    assert r2.road_path == ("R3", "R4")
    assert len(r2.avoided_roads) == 1
    assert r2.avoided_roads[0].road_id == "R2"

    # Step 3: R4 (C->D) also becomes UNSAFE
    states3 = dict(states2)
    states3["R4"] = RoadEdgeState("R4", "C", "D", 60.0, 35.0, "UNSAFE", 0.9)
    r3 = router.find_route("A", "D", "sim_001", 1200, states3)
    assert r3.route_available is False
    assert r3.reason == "NO_SAFE_ROUTE"
    assert len(r3.avoided_roads) == 2
