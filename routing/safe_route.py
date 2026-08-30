"""
Multi-criteria safe route navigation considering travel time, flood risk, and model uncertainty.
"""

from typing import Any

import networkx as nx

from routing.road_graph import RoadNetwork, RoadSegment


def compute_edge_cost(
    road: RoadSegment,
    mode: str = "emergency",  # 'vehicle', 'emergency', 'pedestrian'
    lambda_risk: float = 10.0,
    mu_uncertainty: float = 5.0,
) -> float:
    """
    Computes generalized routing traversal cost:
    Cost = Base_Time + lambda * Risk + mu * (1 - Confidence)
    Hard blocks UNSAFE roads for vehicle and emergency routing.
    """
    if mode in ("emergency", "vehicle") and road.risk_level == "UNSAFE":
        return float("inf")

    if mode == "pedestrian" and road.predicted_depth_cm > 15.0:
        return float("inf")

    base = road.base_travel_time_min
    risk_penalty = lambda_risk * road.risk_score
    uncertainty_penalty = mu_uncertainty * (1.0 - road.confidence)

    return base + risk_penalty + uncertainty_penalty


def find_safe_route(
    network: RoadNetwork,
    origin: str,
    destination: str,
    mode: str = "emergency",
    lambda_risk: float = 10.0,
    mu_uncertainty: float = 5.0,
) -> dict[str, Any]:
    """
    Finds the optimal path avoiding high flood risks using Dijkstra's algorithm.
    """
    if origin not in network.nodes or destination not in network.nodes:
        return {
            "success": False,
            "error": f"Invalid origin '{origin}' or destination '{destination}'",
            "path": [],
            "eta_minutes": 0.0,
            "flood_exposure": 0.0,
            "confidence": 0.0,
        }

    # Assign dynamic edge weights
    weighted_graph = nx.Graph()
    for u, v, data in network.graph.edges(data=True):
        road: RoadSegment = data["road"]
        cost = compute_edge_cost(road, mode=mode, lambda_risk=lambda_risk, mu_uncertainty=mu_uncertainty)
        if cost < float("inf"):
            weighted_graph.add_edge(u, v, weight=cost, road=road)

    try:
        path = nx.shortest_path(weighted_graph, source=origin, target=destination, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {
            "success": False,
            "error": "No safe route available due to severe flooding along all corridors.",
            "path": [],
            "eta_minutes": 0.0,
            "flood_exposure": 0.0,
            "confidence": 0.0,
        }

    # Aggregate path metrics
    total_travel_time = 0.0
    max_risk_score = 0.0
    min_confidence = 1.0
    road_sequence: list[dict[str, Any]] = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = weighted_graph.get_edge_data(u, v)
        road: RoadSegment = edge_data["road"]
        total_travel_time += road.base_travel_time_min
        max_risk_score = max(max_risk_score, road.risk_score)
        min_confidence = min(min_confidence, road.confidence)
        road_sequence.append({
            "road_id": road.road_id,
            "name": road.name,
            "from": u,
            "to": v,
            "depth_cm": round(road.predicted_depth_cm, 1),
            "risk_level": road.risk_level,
            "confidence": round(road.confidence, 2),
        })

    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "path_nodes": path,
        "segments": road_sequence,
        "eta_minutes": round(total_travel_time, 1),
        "flood_exposure_score": round(max_risk_score, 2),
        "confidence": round(min_confidence, 2),
    }
