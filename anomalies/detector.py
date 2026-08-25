"""
Layer 16 — Anomaly Detector Engine:
Evaluates multi-source anomaly rules, preserves all simultaneous detections,
and ranks headline primary classification with severity grading.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any, Mapping
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

# Priority order for headline primary classification
PRIORITY_ORDER = [
    AnomalyType.SENSOR_INCONSISTENCY,
    AnomalyType.POSSIBLE_CAPACITY_ANOMALY,
    AnomalyType.RAPID_RISE,
    AnomalyType.MODEL_DISAGREEMENT,
    AnomalyType.NORMAL,
]


class AnomalyDetector:
    def __init__(
        self,
        rapid_rise_threshold_cm_per_min: float = 5.0,
        model_disagreement_threshold_cm: float = 20.0,
        sensor_inconsistency_threshold_cm: float = 2.0,
        sensor_inconsistency_max_time_diff_s: int = 10,
        capacity_anomaly_min_depth_cm: float = 10.0,
        capacity_anomaly_min_rise_rate_cm_per_min: float = 2.0,
        capacity_anomaly_expected_factor: float = 1.0,
        capacity_anomaly_efficiency_drop: float = 0.40,
    ):
        self.rr_thresh = float(rapid_rise_threshold_cm_per_min)
        self.md_thresh = float(model_disagreement_threshold_cm)
        self.si_thresh = float(sensor_inconsistency_threshold_cm)
        self.si_max_dt = int(sensor_inconsistency_max_time_diff_s)
        self.ca_min_depth = float(capacity_anomaly_min_depth_cm)
        self.ca_min_rate = float(capacity_anomaly_min_rise_rate_cm_per_min)
        self.ca_exp_factor = float(capacity_anomaly_expected_factor)
        self.ca_eff_drop = float(capacity_anomaly_efficiency_drop)

    def evaluate_cell(
        self,
        cell_id: str,
        timestamp_seconds: int,
        current_depth_cm: float,
        previous_depth_cm: Optional[float] = None,
        previous_timestamp_seconds: Optional[int] = None,
        original_model_depth_cm: Optional[float] = None,
        sensor_depth_cm: Optional[float] = None,
        sensor_valid: bool = False,
        float_state: Optional[str] = None,
        float_valid: bool = False,
        float_timestamp_seconds: Optional[int] = None,
        capacity_factor: float = 1.0,
        expected_capture_m3: float = 0.0,
        observed_capture_m3: float = 0.0,
    ) -> AnomalyAssessment:
        """
        Evaluates all anomaly criteria for a cell snapshot.
        """
        detected: List[AnomalyType] = []
        details: Dict[str, Any] = {}

        # 1. Rapid Rise
        rise_rate_cm_min = 0.0
        if (
            previous_depth_cm is not None
            and previous_timestamp_seconds is not None
            and timestamp_seconds > previous_timestamp_seconds
        ):
            rise_rate_cm_min = calculate_rise_rate(
                previous_depth_cm=previous_depth_cm,
                current_depth_cm=current_depth_cm,
                previous_timestamp=previous_timestamp_seconds,
                current_timestamp=timestamp_seconds,
            )
            details["rise_rate_cm_per_min"] = round(rise_rate_cm_min, 2)
            if detect_rapid_rise(rise_rate_cm_min, self.rr_thresh):
                detected.append(AnomalyType.RAPID_RISE)

        # 2. Model Disagreement (evaluated against ORIGINAL model depth)
        if sensor_valid and sensor_depth_cm is not None and original_model_depth_cm is not None:
            disagree = detect_model_disagreement(
                sensor_depth_cm=sensor_depth_cm,
                original_model_depth_cm=original_model_depth_cm,
                threshold_cm=self.md_thresh,
            )
            details["model_disagreement_cm"] = round(abs(sensor_depth_cm - original_model_depth_cm), 2)
            if disagree:
                detected.append(AnomalyType.MODEL_DISAGREEMENT)

        # 3. Sensor Inconsistency
        if (
            sensor_valid
            and sensor_depth_cm is not None
            and float_valid
            and float_state is not None
            and float_timestamp_seconds is not None
        ):
            inconsistent = detect_sensor_inconsistency(
                ultrasonic_level_cm=sensor_depth_cm,
                ultrasonic_valid=sensor_valid,
                float_state=float_state,
                float_valid=float_valid,
                ultrasonic_timestamp=timestamp_seconds,
                float_timestamp=float_timestamp_seconds,
                threshold_cm=self.si_thresh,
                max_time_difference_seconds=self.si_max_dt,
            )
            if inconsistent:
                detected.append(AnomalyType.SENSOR_INCONSISTENCY)

        # 4. Drainage Capacity Anomaly
        if expected_capture_m3 > 0.0:
            cap_anomaly = detect_capacity_anomaly(
                surface_depth_cm=current_depth_cm,
                rise_rate_cm_per_minute=rise_rate_cm_min,
                capacity_factor=capacity_factor,
                expected_capture_m3=expected_capture_m3,
                observed_capture_m3=observed_capture_m3,
                minimum_depth_cm=self.ca_min_depth,
                minimum_rise_rate_cm_per_minute=self.ca_min_rate,
                expected_capacity_factor=self.ca_exp_factor,
                capture_efficiency_drop=self.ca_eff_drop,
            )
            if cap_anomaly:
                detected.append(AnomalyType.POSSIBLE_CAPACITY_ANOMALY)

        # Determine Primary Anomaly and Severity
        if not detected:
            primary = AnomalyType.NORMAL
            severity = AnomalySeverity.INFO
            detected = [AnomalyType.NORMAL]
        else:
            primary = next((p for p in PRIORITY_ORDER if p in detected), detected[0])
            if primary in (AnomalyType.POSSIBLE_CAPACITY_ANOMALY, AnomalyType.SENSOR_INCONSISTENCY):
                severity = AnomalySeverity.CRITICAL
            elif primary in (AnomalyType.RAPID_RISE, AnomalyType.MODEL_DISAGREEMENT):
                severity = AnomalySeverity.WARNING
            else:
                severity = AnomalySeverity.INFO

        return AnomalyAssessment(
            cell_id=cell_id,
            timestamp_seconds=timestamp_seconds,
            detected=tuple(detected),
            primary=primary,
            severity=severity,
            details=details,
        )
