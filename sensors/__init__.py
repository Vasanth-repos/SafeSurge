"""
Sensors Subsystem (Layers 11-12):
Hardware measurements, ultrasonic filtering, float switch verification,
identity validation, temporal rate-of-rise checking, and sensor health tracking.
"""

from sensors.models import (
    SensorState,
    MeasurementStatus,
    RejectionReason,
    SensorEnvelope,
    UltrasonicMeasurement,
    ValidationResult,
)
from sensors.registry import SensorRegistry, SensorConfig
from sensors.filtering import filter_echoes
from sensors.ultrasonic import distance_to_water_level, process_measurement
from sensors.float_switch import validate_float_consistency
from sensors.health import SensorHealthTracker, evaluate_sensor_health
from sensors.validation import SensorValidator, validate_rate_of_rise
from sensors.simulator import load_sensor_replay

__all__ = [
    "SensorState",
    "MeasurementStatus",
    "RejectionReason",
    "SensorEnvelope",
    "UltrasonicMeasurement",
    "ValidationResult",
    "SensorRegistry",
    "SensorConfig",
    "filter_echoes",
    "distance_to_water_level",
    "process_measurement",
    "validate_float_consistency",
    "SensorHealthTracker",
    "evaluate_sensor_health",
    "SensorValidator",
    "validate_rate_of_rise",
    "load_sensor_replay",
]
