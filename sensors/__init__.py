"""
Sensors Subsystem (Layers 11-12):
Hardware measurements, ultrasonic filtering, float switch verification,
identity validation, temporal rate-of-rise checking, and sensor health tracking.
"""

from sensors.filtering import filter_echoes
from sensors.float_switch import validate_float_consistency
from sensors.health import SensorHealthTracker, evaluate_sensor_health
from sensors.models import (
    MeasurementStatus,
    RejectionReason,
    SensorEnvelope,
    SensorState,
    UltrasonicMeasurement,
    ValidationResult,
)
from sensors.registry import SensorConfig, SensorRegistry
from sensors.simulator import load_sensor_replay
from sensors.ultrasonic import distance_to_water_level, process_measurement
from sensors.validation import SensorValidator, validate_rate_of_rise

__all__ = [
    "MeasurementStatus",
    "RejectionReason",
    "SensorConfig",
    "SensorEnvelope",
    "SensorHealthTracker",
    "SensorRegistry",
    "SensorState",
    "SensorValidator",
    "UltrasonicMeasurement",
    "ValidationResult",
    "distance_to_water_level",
    "evaluate_sensor_health",
    "filter_echoes",
    "load_sensor_replay",
    "process_measurement",
    "validate_float_consistency",
    "validate_rate_of_rise",
]
