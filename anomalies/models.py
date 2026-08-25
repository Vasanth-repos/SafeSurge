"""
Layer 16 — Anomaly Detection Models:
Enums and dataclasses for deterministic physical and operational anomaly assessments.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional


class AnomalyType(str, Enum):
    NORMAL = "NORMAL"
    RAPID_RISE = "RAPID_RISE"
    MODEL_DISAGREEMENT = "MODEL_DISAGREEMENT"
    SENSOR_INCONSISTENCY = "SENSOR_INCONSISTENCY"
    POSSIBLE_CAPACITY_ANOMALY = "POSSIBLE_CAPACITY_ANOMALY"


class AnomalySeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class AnomalyAssessment:
    cell_id: str
    timestamp_seconds: int
    detected: Tuple[AnomalyType, ...]
    primary: AnomalyType
    severity: AnomalySeverity
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "timestamp_seconds": self.timestamp_seconds,
            "detected": [a.value for a in self.detected],
            "primary": self.primary.value,
            "severity": self.severity.value,
            "details": self.details,
        }
