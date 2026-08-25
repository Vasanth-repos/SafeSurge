"""
Anomaly Engine (Layer 16):
Multi-source deterministic anomaly detection, timestamp-aware rate-of-rise calculation,
anti-circular model disagreement tracking, and drainage capacity anomaly alerts.
"""

from anomalies.models import (
    AnomalyType,
    AnomalySeverity,
    AnomalyAssessment,
)
from anomalies.rules import (
    calculate_rise_rate,
    detect_rapid_rise,
    detect_model_disagreement,
    detect_sensor_inconsistency,
    detect_capacity_anomaly,
)
from anomalies.detector import AnomalyDetector

__all__ = [
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyAssessment",
    "calculate_rise_rate",
    "detect_rapid_rise",
    "detect_model_disagreement",
    "detect_sensor_inconsistency",
    "detect_capacity_anomaly",
    "AnomalyDetector",
]
