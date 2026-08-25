"""Sensors package for Urban Flood Nowcasting."""

from sensor.validation import validate_sensor_reading
from sensor.health import SensorNode
from sensor.fusion import update_sensor_bias, propagate_spatial_bias, apply_fused_depth_correction
from sensor.anomaly import detect_sensor_anomalies
from sensor.confidence import compute_confidence_score

__all__ = [
    "validate_sensor_reading",
    "SensorNode",
    "update_sensor_bias",
    "propagate_spatial_bias",
    "apply_fused_depth_correction",
    "detect_sensor_anomalies",
    "compute_confidence_score",
]
