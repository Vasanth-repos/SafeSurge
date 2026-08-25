"""
Layer 17 — Road Exposure & Risk Models:
Data classes for road segments, cell intersection exposures, and risk assessments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class RoadCellExposure:
    road_id: str
    cell_id: str
    intersection_length_m: float
    exposure_fraction: float


@dataclass(frozen=True)
class Road:
    road_id: str
    from_node: str
    to_node: str
    geometry: Any  # shapely LineString or Polygon
    length_m: float
    nominal_travel_time_seconds: float = 60.0


@dataclass(frozen=True)
class RoadRisk:
    road_id: str
    timestamp_seconds: int
    mean_depth_cm: float
    max_relevant_depth_cm: float
    affected_fraction: float
    risk: str
    confidence: float
    minimum_cell_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "road_id": self.road_id,
            "timestamp_seconds": self.timestamp_seconds,
            "mean_depth_cm": round(self.mean_depth_cm, 2),
            "max_relevant_depth_cm": round(self.max_relevant_depth_cm, 2),
            "affected_fraction": round(self.affected_fraction, 4),
            "risk": self.risk,
            "confidence": round(self.confidence, 4),
            "minimum_cell_confidence": round(self.minimum_cell_confidence, 4),
        }
