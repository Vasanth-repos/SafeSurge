"""
Layer 18 — Emergency Routing Models:
Data contracts for directed graph edges, dynamic flooded edge states, and shortest-path route results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


@dataclass(frozen=True)
class RoadEdge:
    road_id: str
    from_node: str
    to_node: str
    travel_time_seconds: float
    length_m: float = 100.0


@dataclass(frozen=True)
class RoadEdgeState:
    road_id: str
    from_node: str
    to_node: str
    travel_time_seconds: float
    flood_depth_cm: float
    risk: str
    confidence: float


@dataclass(frozen=True)
class AvoidedRoad:
    road_id: str
    reason: str
    risk: str
    depth_cm: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "road_id": self.road_id,
            "reason": self.reason,
            "risk": self.risk,
            "depth_cm": round(self.depth_cm, 2),
        }


@dataclass(frozen=True)
class RouteResult:
    route_available: bool
    simulation_id: str
    timestamp_seconds: int
    origin: str
    destination: str
    road_path: Tuple[str, ...]
    node_path: Tuple[str, ...]
    total_travel_time_seconds: float
    total_cost: float
    minimum_confidence: float
    avoided_roads: Tuple[AvoidedRoad, ...]
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_available": self.route_available,
            "simulation_id": self.simulation_id,
            "timestamp_seconds": self.timestamp_seconds,
            "origin": self.origin,
            "destination": self.destination,
            "road_path": list(self.road_path),
            "node_path": list(self.node_path),
            "total_travel_time_seconds": round(self.total_travel_time_seconds, 2),
            "total_cost": round(self.total_cost, 2),
            "minimum_confidence": round(self.minimum_confidence, 4),
            "avoided_roads": [a.to_dict() for a in self.avoided_roads],
            "reason": self.reason,
        }
