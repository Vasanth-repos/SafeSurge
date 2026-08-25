"""
Layers 13–15 — Sensor Fusion & Confidence Models:
Data contracts for validated sensor observations, bias estimation states,
historical observation windows, spatial confidence metrics, and fused cell fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass(frozen=True)
class SensorObservation:
    sensor_id: str
    cell_id: str
    timestamp_seconds: int
    observed_depth_cm: float
    sensor_state: str  # e.g., "ONLINE", "STALE", "OFFLINE"
    measurement_status: str  # e.g., "ACCEPTED", "REJECTED"
    quality: float = 1.0


@dataclass
class SensorBiasState:
    sensor_id: str
    bias_cm: float = 0.0
    observation_count: int = 0
    last_updated_seconds: Optional[int] = None
    last_residual_cm: Optional[float] = None
    is_eligible: bool = False


@dataclass(frozen=True)
class ObservationHistoryRecord:
    timestamp_seconds: int
    model_depth_cm: float
    observed_depth_cm: float
    residual_cm: float


@dataclass(frozen=True)
class CellConfidence:
    cell_id: str
    score: float
    coverage: float
    freshness: float
    agreement: float
    history_factor: float
    nearest_sensor_id: Optional[str] = None
    sensor_age_seconds: Optional[int] = None
    agreement_observation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "coverage": round(self.coverage, 4),
            "freshness": round(self.freshness, 4),
            "agreement": round(self.agreement, 4),
            "history_factor": round(self.history_factor, 4),
            "nearest_sensor_id": self.nearest_sensor_id,
            "sensor_age_seconds": self.sensor_age_seconds,
            "agreement_observations": self.agreement_observation_count,
        }


@dataclass(frozen=True)
class FusedCellResult:
    cell_id: str
    model_depth_cm: float
    correction_cm: float
    corrected_depth_cm: float
    confidence: CellConfidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "depth": {
                "model_cm": round(self.model_depth_cm, 4),
                "correction_cm": round(self.correction_cm, 4),
                "corrected_cm": round(self.corrected_depth_cm, 4),
            },
            "confidence": self.confidence.to_dict(),
            "provenance": {
                "nearest_sensor_id": self.confidence.nearest_sensor_id,
                "sensor_age_seconds": self.confidence.sensor_age_seconds,
                "agreement_observations": self.confidence.agreement_observation_count,
            },
        }


@dataclass(frozen=True)
class FusionStepResult:
    timestamp_seconds: int
    cells: Dict[str, FusedCellResult]
    sensor_biases: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_seconds": self.timestamp_seconds,
            "sensor_biases": {sid: round(b, 4) for sid, b in self.sensor_biases.items()},
            "cells": {cid: cr.to_dict() for cid, cr in self.cells.items()},
        }
