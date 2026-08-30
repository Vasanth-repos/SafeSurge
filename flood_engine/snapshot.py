"""
Layers 20–25 — Central Immutable SimulationSnapshot Contract:
The single source of truth for time-indexed simulation state across GIS maps,
mass balance accounting, sensor telemetry, anomaly diagnostics, and dynamic routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SystemStatus(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class RainfallStatus(str, Enum):
    ZERO = "ZERO"
    VALID = "VALID"
    STALE = "STALE"
    MISSING = "MISSING"
    INVALID = "INVALID"


@dataclass(frozen=True)
class CellSnapshot:
    cell_id: str
    row: int
    col: int
    elevation_m: float
    model_depth_cm: float
    correction_cm: float
    corrected_depth_cm: float
    risk: str
    confidence: float
    status: str = "VALID"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "elevation_m": round(self.elevation_m, 2),
            "model_depth_cm": round(self.model_depth_cm, 2),
            "correction_cm": round(self.correction_cm, 2),
            "depth_cm": round(self.corrected_depth_cm, 2),
            "risk": self.risk,
            "confidence": round(self.confidence, 4),
            "status": self.status,
        }


@dataclass(frozen=True)
class RoadSnapshot:
    road_id: str
    from_node: str
    to_node: str
    mean_depth_cm: float
    max_relevant_depth_cm: float
    affected_fraction: float
    risk: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "road_id": self.road_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "mean_depth_cm": round(self.mean_depth_cm, 2),
            "max_relevant_depth_cm": round(self.max_relevant_depth_cm, 2),
            "affected_fraction": round(self.affected_fraction, 4),
            "risk": self.risk,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class SensorSnapshot:
    sensor_id: str
    location_id: str
    status: str
    last_valid_reading_cm: float | None
    last_valid_timestamp_seconds: int | None
    age_seconds: int
    bias_cm: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "location_id": self.location_id,
            "status": self.status,
            "last_valid_reading_cm": round(self.last_valid_reading_cm, 2) if self.last_valid_reading_cm is not None else None,
            "last_valid_timestamp_seconds": self.last_valid_timestamp_seconds,
            "age_seconds": self.age_seconds,
            "bias_cm": round(self.bias_cm, 2),
        }


@dataclass(frozen=True)
class ForecastSnapshot:
    status: str
    depth_cm: float
    lower_depth_cm: float
    upper_depth_cm: float
    confidence: float
    uncertainty_status: str = "PROTOTYPE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "depth_cm": round(self.depth_cm, 2),
            "lower_depth_cm": round(self.lower_depth_cm, 2),
            "upper_depth_cm": round(self.upper_depth_cm, 2),
            "confidence": round(self.confidence, 4),
            "uncertainty_status": self.uncertainty_status,
        }


@dataclass(frozen=True)
class MassBalanceSnapshot:
    runoff_input_m3: float
    previous_storage_m3: float
    current_storage_m3: float
    drainage_m3: float
    boundary_outflow_m3: float
    balance_error_m3: float
    relative_error: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "runoff_input_m3": round(self.runoff_input_m3, 4),
            "previous_storage_m3": round(self.previous_storage_m3, 4),
            "current_storage_m3": round(self.current_storage_m3, 4),
            "drainage_m3": round(self.drainage_m3, 4),
            "boundary_outflow_m3": round(self.boundary_outflow_m3, 4),
            "balance_error_m3": round(self.balance_error_m3, 6),
            "relative_error": round(self.relative_error, 6),
            "status": self.status,
        }


@dataclass(frozen=True)
class SimulationSnapshot:
    simulation_id: str
    timestamp_seconds: int
    simulation_status: str
    system_status: str
    rainfall_status: str
    flood_cells: tuple[CellSnapshot, ...]
    road_risks: tuple[RoadSnapshot, ...]
    drainage_states: tuple[dict[str, Any], ...]
    sensor_states: tuple[SensorSnapshot, ...]
    anomalies: tuple[dict[str, Any], ...]
    forecast: ForecastSnapshot | None
    mass_balance: MassBalanceSnapshot
    active_faults: tuple[str, ...] = ()
    degraded_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "timestamp_seconds": self.timestamp_seconds,
            "simulation_status": self.simulation_status,
            "system_status": self.system_status,
            "rainfall_status": self.rainfall_status,
            "degraded_reasons": list(self.degraded_reasons),
            "forecast": self.forecast.to_dict() if self.forecast else None,
            "cells": [c.to_dict() for c in self.flood_cells],
            "roads": [r.to_dict() for r in self.road_risks],
            "drainage": list(self.drainage_states),
            "sensors": [s.to_dict() for s in self.sensor_states],
            "anomalies": list(self.anomalies),
            "mass_balance": self.mass_balance.to_dict(),
            "active_faults": list(self.active_faults),
        }
