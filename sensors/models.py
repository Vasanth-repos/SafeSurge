"""
Layer 11-12 — Sensor Telemetry Models:
Enums and dataclasses for ultrasonic burst sampling, float switch readings,
validation verdicts, device health states, and audit packets.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict


class SensorState(str, Enum):
    ONLINE = "ONLINE"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    INVALID = "INVALID"


class MeasurementStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class RejectionReason(str, Enum):
    NONE = "NONE"
    UNKNOWN_SENSOR = "UNKNOWN_SENSOR"
    DISABLED_SENSOR = "DISABLED_SENSOR"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MISSING_ECHO = "MISSING_ECHO"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    RANGE_ERROR = "RANGE_ERROR"
    RATE_SPIKE = "RATE_SPIKE"
    FLOAT_CONFLICT = "FLOAT_CONFLICT"


@dataclass(frozen=True)
class SensorEnvelope:
    sensor_id: str
    boot_id: str
    sequence: int
    measured_at_seconds: int
    received_at_seconds: int
    distance_samples_cm: Tuple[Optional[float], ...]
    float_triggered: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "boot_id": self.boot_id,
            "sequence": self.sequence,
            "measured_at_seconds": self.measured_at_seconds,
            "received_at_seconds": self.received_at_seconds,
            "distance_samples_cm": list(self.distance_samples_cm),
            "float_triggered": self.float_triggered,
        }


@dataclass(frozen=True)
class UltrasonicMeasurement:
    sensor_id: str
    boot_id: str
    sequence: int
    measured_at_seconds: int
    received_at_seconds: int
    distance_cm: Optional[float]
    water_level_cm: Optional[float]
    valid_echo_count: int
    float_triggered: Optional[bool] = None


@dataclass(frozen=True)
class ValidationResult:
    sensor_id: str
    boot_id: str
    sequence: int
    measured_at_seconds: int
    received_at_seconds: int
    distance_cm: Optional[float]
    water_level_cm: Optional[float]
    sensor_state: SensorState
    measurement_status: MeasurementStatus
    rejection_reason: RejectionReason
    quality_flags: Tuple[str, ...] = ()
    location_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "location_id": self.location_id,
            "boot_id": self.boot_id,
            "sequence": self.sequence,
            "measured_at_seconds": self.measured_at_seconds,
            "received_at_seconds": self.received_at_seconds,
            "distance_cm": round(self.distance_cm, 2) if self.distance_cm is not None else None,
            "water_level_cm": round(self.water_level_cm, 2) if self.water_level_cm is not None else None,
            "sensor_state": self.sensor_state.value,
            "measurement_status": self.measurement_status.value,
            "rejection_reason": self.rejection_reason.value,
            "quality_flags": list(self.quality_flags),
        }
