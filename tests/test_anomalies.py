"""
Layer 16 — Anomaly Engine Tests:
Verifies rate-of-rise calculation, falling water suppression, anti-circular model disagreement,
synchronized sensor inconsistency, and capacity anomaly detection.
"""

import pytest
from anomalies.models import AnomalyType, AnomalySeverity
from anomalies.rules import (
    calculate_rise_rate,
    detect_rapid_rise,
    detect_model_disagreement,
    detect_sensor_inconsistency,
    detect_capacity_anomaly,
)
from anomalies.detector import AnomalyDetector


def test_rapid_rise_and_falling_water():
    """
    Test 1: 5 cm -> 12 cm in 60s -> (12 - 5)/60 * 60 = 7 cm/min -> RAPID_RISE.
    Test 2: 30 cm -> 20 cm in 60s -> rate = -10 cm/min -> NOT RAPID_RISE.
    """
    # 5 -> 12 cm
    r1 = calculate_rise_rate(5.0, 12.0, 0, 60)
    assert r1 == pytest.approx(7.0)
    assert detect_rapid_rise(r1, threshold_cm_per_minute=5.0) is True

    # 30 -> 20 cm (falling water)
    r2 = calculate_rise_rate(30.0, 20.0, 0, 60)
    assert r2 == pytest.approx(-10.0)
    assert detect_rapid_rise(r2, threshold_cm_per_minute=5.0) is False


def test_model_disagreement_with_original_model():
    """
    Test 3: Sensor = 25.0 cm, Model = 18.0 cm, Threshold = 5.0 cm -> |25 - 18| = 7 > 5 -> True.
    Sensor = 25.0 cm, Model = 23.0 cm, Threshold = 5.0 cm -> |25 - 23| = 2 <= 5 -> False.
    """
    assert detect_model_disagreement(25.0, 18.0, threshold_cm=5.0) is True
    assert detect_model_disagreement(25.0, 23.0, threshold_cm=5.0) is False


def test_sensor_inconsistency_synchronized():
    """
    Test 4: Ultrasonic = 0.0 cm (DRY), Float = WATER_PRESENT -> Inconsistent!
    If timestamps differ by > 10s -> Not flagged.
    """
    # Synchronized (dt = 0s)
    assert detect_sensor_inconsistency(
        ultrasonic_level_cm=0.0,
        ultrasonic_valid=True,
        float_state="WATER_PRESENT",
        float_valid=True,
        ultrasonic_timestamp=100,
        float_timestamp=100,
        threshold_cm=2.0,
        max_time_difference_seconds=10,
    ) is True

    # Asynchronous (dt = 30s > 10s) -> Not evaluated
    assert detect_sensor_inconsistency(
        ultrasonic_level_cm=0.0,
        ultrasonic_valid=True,
        float_state="WATER_PRESENT",
        float_valid=True,
        ultrasonic_timestamp=100,
        float_timestamp=130,
        threshold_cm=2.0,
        max_time_difference_seconds=10,
    ) is False


def test_capacity_anomaly_logic():
    """
    Test 5: Known reduced capacity (factor = 0.3 < 1.0) is NOT an anomaly.
    Unexpected poor capture during storm when factor=1.0 IS flagged.
    """
    # Case A: Configured scenario factor = 0.3 -> NOT anomaly
    assert detect_capacity_anomaly(
        surface_depth_cm=15.0,
        rise_rate_cm_per_minute=3.0,
        capacity_factor=0.3,  # Known scenario!
        expected_capture_m3=100.0,
        observed_capture_m3=30.0,
        expected_capacity_factor=1.0,
    ) is False

    # Case B: Factor = 1.0, but capture dropped by > 40% -> Flagged anomaly!
    assert detect_capacity_anomaly(
        surface_depth_cm=15.0,
        rise_rate_cm_per_minute=3.0,
        capacity_factor=1.0,
        expected_capture_m3=100.0,
        observed_capture_m3=40.0,  # 60% drop
        expected_capacity_factor=1.0,
        capture_efficiency_drop=0.40,
    ) is True


def test_detector_multi_anomaly_ranking():
    """Verifies that all detected anomaly signals are retained and prioritized correctly."""
    detector = AnomalyDetector(rapid_rise_threshold_cm_per_min=5.0, model_disagreement_threshold_cm=5.0)

    # Trigger both rapid rise (0 -> 10 cm in 60s = 10 cm/min) and model disagreement (obs=10, model=0 -> e=10 > 5)
    assessment = detector.evaluate_cell(
        cell_id="C104",
        timestamp_seconds=60,
        current_depth_cm=10.0,
        previous_depth_cm=0.0,
        previous_timestamp_seconds=0,
        original_model_depth_cm=0.0,
        sensor_depth_cm=10.0,
        sensor_valid=True,
    )

    assert AnomalyType.RAPID_RISE in assessment.detected
    assert AnomalyType.MODEL_DISAGREEMENT in assessment.detected
    assert assessment.primary == AnomalyType.RAPID_RISE
    assert assessment.severity == AnomalySeverity.WARNING
