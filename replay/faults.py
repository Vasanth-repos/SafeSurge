"""
Layer 24 — Fault Injection Engine & Scenario Disruption Framework:
Provides reproducible, non-destructive fault simulation (sensor dropout, rate spikes,
capacity reduction, extreme precipitation, and road blockage).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FaultType(str, Enum):
    SENSOR_OFFLINE = "SENSOR_OFFLINE"
    SENSOR_SPIKE = "SENSOR_SPIKE"
    DRAINAGE_CAPACITY = "DRAINAGE_CAPACITY"
    RAINFALL_MULTIPLIER = "RAINFALL_MULTIPLIER"
    RAINFALL_UNAVAILABLE = "RAINFALL_UNAVAILABLE"
    NO_SENSOR_COVERAGE = "NO_SENSOR_COVERAGE"
    ROAD_BLOCKAGE = "ROAD_BLOCKAGE"


@dataclass(frozen=True)
class Fault:
    fault_id: str
    fault_type: FaultType
    start_seconds: int
    end_seconds: int
    parameters: dict[str, Any] = field(default_factory=dict)

    def is_active(self, timestamp_seconds: int) -> bool:
        return self.start_seconds <= timestamp_seconds <= self.end_seconds


class FaultInjectionEngine:
    def __init__(self, faults: Sequence[Fault] | None = None):
        self.faults: list[Fault] = list(faults) if faults else []

    def add_fault(self, fault: Fault) -> None:
        self.faults.append(fault)

    def get_active_faults(self, timestamp_seconds: int) -> list[Fault]:
        return [f for f in self.faults if f.is_active(timestamp_seconds)]

    def apply_rainfall_multiplier(self, timestamp_seconds: int, base_rainfall_mm: float) -> float:
        for f in self.get_active_faults(timestamp_seconds):
            if f.fault_type == FaultType.RAINFALL_MULTIPLIER:
                mult = float(f.parameters.get("multiplier", 1.0))
                return base_rainfall_mm * mult
        return base_rainfall_mm

    def is_rainfall_unavailable(self, timestamp_seconds: int) -> bool:
        return any(
            f.fault_type == FaultType.RAINFALL_UNAVAILABLE
            for f in self.get_active_faults(timestamp_seconds)
        )

    def apply_sensor_override(
        self,
        sensor_id: str,
        timestamp_seconds: int,
        nominal_reading_cm: float,
        nominal_status: str,
    ) -> tuple[float | None, str, bool]:
        """
        Returns (reading_cm, status, is_modified)
        """
        for f in self.get_active_faults(timestamp_seconds):
            if f.fault_type == FaultType.NO_SENSOR_COVERAGE:
                return None, "OFFLINE", True

            if f.parameters.get("sensor_id") == sensor_id:
                if f.fault_type == FaultType.SENSOR_OFFLINE:
                    return None, "OFFLINE", True
                elif f.fault_type == FaultType.SENSOR_SPIKE:
                    spike_val = float(f.parameters.get("depth_cm", 90.0))
                    return spike_val, "ONLINE", True

        return nominal_reading_cm, nominal_status, False

    def get_capacity_factor(self, edge_id: str, timestamp_seconds: int, default_factor: float = 1.0) -> float:
        for f in self.get_active_faults(timestamp_seconds):
            if f.fault_type == FaultType.DRAINAGE_CAPACITY:
                target_edge = f.parameters.get("edge_id")
                if target_edge is None or target_edge == edge_id:
                    return float(f.parameters.get("capacity_factor", 0.3))
        return default_factor
