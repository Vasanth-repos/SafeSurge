"""
Unit & Integration Tests for Complex Road Network Allocation & Inundation Edge Cases.
"""

import pytest
from shapely.geometry import LineString, Polygon
from routing.graph import DirectedRoadGraph
from routing.router import EmergencyRouter
from routing.models import RoadEdge, RoadEdgeState, RouteResult
from roads.models import Road
from roads.mapping import RoadSpatialMapper
from roads.risk import RoadRiskEngine


def test_multi_stage_cascading_rerouting_edge_case():
    """
    Tests 3-stage dynamic cascading diversion:
    Phase 1: Dry -> Fastest Diagonal A -> M -> D (70s)
    Phase 2: Midtown R007 flooded -> Diverts to Northern Arterial A -> B -> E -> D (100s)
    Phase 3: East Underpass R005 also flooded -> Diverts to Western Safe Elevated Corridor A -> W -> C -> D (100s)
    """
    edges = [
        RoadEdge("R001", "A", "B", 45.0, 90.0),
        RoadEdge("R002", "B", "E", 30.0, 50.0),
        RoadEdge("R003", "A", "W", 30.0, 50.0),
        RoadEdge("R004", "C", "D", 45.0, 90.0),
        RoadEdge("R005", "E", "D", 25.0, 40.0),
        RoadEdge("R006", "A", "M", 35.0, 65.0),
        RoadEdge("R007", "M", "D", 35.0, 65.0),
        RoadEdge("R008", "W", "M", 30.0, 50.0),
        RoadEdge("R009", "M", "E", 25.0, 40.0),
        RoadEdge("R010", "W", "C", 25.0, 40.0),
    ]
    graph = DirectedRoadGraph(edges)
    router = EmergencyRouter(graph)

    # Phase 1: All Dry
    states_p1 = {e.road_id: RoadEdgeState(e.road_id, e.from_node, e.to_node, e.travel_time_seconds, 0.0, "SAFE", 1.0) for e in edges}
    r_p1 = router.find_route("A", "D", "storm_01", 0, states_p1)
    assert r_p1.road_path == ("R006", "R007")  # A -> M -> D (70s)
    assert r_p1.node_path == ("A", "M", "D")

    # Phase 2: R007 Flooded (UNSAFE) -> Diverts to A -> M -> E -> D (85s)
    states_p2 = dict(states_p1)
    states_p2["R007"] = RoadEdgeState("R007", "M", "D", 35.0, 30.0, "UNSAFE", 0.9)
    r_p2 = router.find_route("A", "D", "storm_01", 1800, states_p2)
    assert r_p2.road_path == ("R006", "R009", "R005")  # A -> M -> E -> D
    assert r_p2.node_path == ("A", "M", "E", "D")
    assert any(a.road_id == "R007" for a in r_p2.avoided_roads)

    # Phase 3: Both R007 and R005 Flooded (UNSAFE) -> Diverts to A -> W -> C -> D
    states_p3 = dict(states_p2)
    states_p3["R005"] = RoadEdgeState("R005", "E", "D", 25.0, 32.0, "UNSAFE", 0.95)
    r_p3 = router.find_route("A", "D", "storm_01", 3600, states_p3)
    assert r_p3.road_path == ("R003", "R010", "R004")  # A -> W -> C -> D
    assert r_p3.node_path == ("A", "W", "C", "D")
    assert len(r_p3.avoided_roads) == 2


def test_complete_downstream_blockage_trap_fallback():
    """
    Tests graceful fallback when all ingress corridors to hospital destination D are severed.
    """
    edges = [
        RoadEdge("R001", "A", "B", 45.0, 90.0),
        RoadEdge("R002", "B", "E", 30.0, 50.0),
        RoadEdge("R003", "A", "W", 30.0, 50.0),
        RoadEdge("R004", "C", "D", 45.0, 90.0),
        RoadEdge("R005", "E", "D", 25.0, 40.0),
        RoadEdge("R006", "A", "M", 35.0, 65.0),
        RoadEdge("R007", "M", "D", 35.0, 65.0),
        RoadEdge("R010", "W", "C", 25.0, 40.0),
    ]
    graph = DirectedRoadGraph(edges)
    router = EmergencyRouter(graph)

    # Ingress to D: R004 (C->D), R005 (E->D), R007 (M->D) all flooded >= 25cm
    states_blocked = {e.road_id: RoadEdgeState(e.road_id, e.from_node, e.to_node, e.travel_time_seconds, 0.0, "SAFE", 1.0) for e in edges}
    states_blocked["R004"] = RoadEdgeState("R004", "C", "D", 45.0, 28.0, "UNSAFE", 0.9)
    states_blocked["R005"] = RoadEdgeState("R005", "E", "D", 25.0, 35.0, "UNSAFE", 0.9)
    states_blocked["R007"] = RoadEdgeState("R007", "M", "D", 35.0, 30.0, "UNSAFE", 0.9)

    result = router.find_route("A", "D", "storm_01", 3600, states_blocked)
    assert not result.route_available
    assert result.reason == "NO_SAFE_ROUTE"
    assert len(result.avoided_roads) == 3
