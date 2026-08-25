"""
Layer 16 — Deterministic Anomaly Detection Rules:
Implements physical rate-of-rise checks, anti-circular model disagreement rules,
sensor contact-closure inconsistency checks, and drainage capacity anomaly detection.
"""

from __future__ import annotations

from typing import Optional


def calculate_rise_rate(
    previous_depth_cm: float,
    current_depth_cm: float,
    previous_timestamp: int,
    current_timestamp: int,
) -> float:
    """
    Computes rate of depth change in cm/minute:
    R = (H_t - H_{t-1}) / (t_t - t_{t-1}) * 60
    """
    dt = current_timestamp - previous_timestamp
    if dt <= 0:
        raise ValueError(f"Invalid timestamps for rate calculation: dt={dt} <= 0")
    delta_h = current_depth_cm - previous_depth_cm
    return (delta_h / dt) * 60.0


def detect_rapid_rise(
    rise_rate_cm_per_minute: float,
    threshold_cm_per_minute: float = 5.0,
) -> bool:
    """
    Detects sudden water level surge:
    Rising rate >= threshold (e.g. >= 5 cm/min).
    Falling water (< 0) never triggers rapid rise.
    """
    return rise_rate_cm_per_minute >= threshold_cm_per_minute


def detect_model_disagreement(
    sensor_depth_cm: float,
    original_model_depth_cm: float,
    threshold_cm: float = 20.0,
) -> bool:
    """
    Detects severe discrepancy between sensor observation and ORIGINAL model depth:
    |H_sensor - H_ORIGINAL_model| > threshold_cm
    """
    return abs(sensor_depth_cm - original_model_depth_cm) > threshold_cm


def detect_sensor_inconsistency(
    ultrasonic_level_cm: float,
    ultrasonic_valid: bool,
    float_state: str,  # e.g., "WATER_PRESENT" or "DRY"
    float_valid: bool,
    ultrasonic_timestamp: int,
    float_timestamp: int,
    threshold_cm: float = 2.0,
    max_time_difference_seconds: int = 10,
) -> bool:
    """
    Detects physical contact inconsistency between ultrasonic and float switch:
    Only evaluated when BOTH sensors are VALID and temporally synchronized (dt <= 10s).
    """
    if not ultrasonic_valid or not float_valid:
        return False

    if abs(ultrasonic_timestamp - float_timestamp) > max_time_difference_seconds:
        return False

    ultrasonic_water = (ultrasonic_level_cm > threshold_cm)
    float_water = (float_state.upper() in ("WATER_PRESENT", "TRUE", "1"))

    return ultrasonic_water != float_water


def detect_capacity_anomaly(
    surface_depth_cm: float,
    rise_rate_cm_per_minute: float,
    capacity_factor: float,
    expected_capture_m3: float,
    observed_capture_m3: float,
    minimum_depth_cm: float = 10.0,
    minimum_rise_rate_cm_per_minute: float = 2.0,
    expected_capacity_factor: float = 1.0,
    capture_efficiency_drop: float = 0.40,
) -> bool:
    """
    Detects unexpected drainage capacity failure:
    1. Known reduced-capacity scenarios (capacity_factor < expected) are NOT anomalies.
    2. Requires significant standing water (depth >= minimum_depth) and active rise (rate >= minimum_rise_rate).
    3. Requires observed capture to drop significantly below expected (< 1 - drop).
    """
    # If the system is already configured in a known reduced capacity scenario, do not flag anomaly
    if capacity_factor < expected_capacity_factor:
        return False

    if surface_depth_cm < minimum_depth_cm:
        return False

    if rise_rate_cm_per_minute < minimum_rise_rate_cm_per_minute:
        return False

    if expected_capture_m3 <= 0.0:
        return False

    capture_ratio = observed_capture_m3 / expected_capture_m3
    return capture_ratio <= (1.0 - capture_efficiency_drop)
