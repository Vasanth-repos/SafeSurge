"""
Anomaly Engine (Layer 16):
Multi-source deterministic anomaly detection, timestamp-aware rate-of-rise calculation,
anti-circular model disagreement tracking, and drainage capacity anomaly alerts.
"""

from anomalies.detector import AnomalyDetector
from anomalies.models import (
    AnomalyAssessment,
    AnomalySeverity,
    AnomalyType,
)
from anomalies.rules import (
    calculate_rise_rate,
    detect_capacity_anomaly,
    detect_model_disagreement,
    detect_rapid_rise,
    detect_sensor_inconsistency,
)

__all__ = [
    "AnomalyAssessment",
    "AnomalyDetector",
    "AnomalySeverity",
    "AnomalyType",
    "calculate_rise_rate",
    "detect_capacity_anomaly",
    "detect_model_disagreement",
    "detect_rapid_rise",
    "detect_sensor_inconsistency",
]
