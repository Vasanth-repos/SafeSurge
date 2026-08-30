"""
Layer 11 — Ultrasonic Distance to Water Level Conversion:
Converts filtered ultrasonic echo distance (D) to water level (L = H_ref - D)
without silent clamping.
"""

from __future__ import annotations

from sensors.filtering import filter_echoes
from sensors.models import SensorEnvelope, UltrasonicMeasurement
from sensors.registry import SensorConfig


def distance_to_water_level(
    reference_height_cm: float,
    distance_cm: float,
) -> float:
    """
    Computes physical water level: L = H_ref - D.
    Does NOT clamp to 0 or reference height; out-of-range values are
    preserved so validation can flag calibration/physical anomalies.
    """
    return float(reference_height_cm) - float(distance_cm)


def process_measurement(
    envelope: SensorEnvelope,
    config: SensorConfig,
) -> UltrasonicMeasurement:
    """
    Executes Layer 11 raw measurement processing:
    1. Filters burst echoes.
    2. Computes median distance.
    3. Calculates water level if distance is valid.
    """
    dist_med, valid_count = filter_echoes(
        samples=envelope.distance_samples_cm,
        min_distance_cm=config.min_distance_cm,
        max_distance_cm=config.max_distance_cm,
        minimum_valid_samples=config.minimum_valid_samples,
    )

    if dist_med is not None:
        level = distance_to_water_level(config.reference_height_cm, dist_med)
    else:
        level = None

    return UltrasonicMeasurement(
        sensor_id=envelope.sensor_id,
        boot_id=envelope.boot_id,
        sequence=envelope.sequence,
        measured_at_seconds=envelope.measured_at_seconds,
        received_at_seconds=envelope.received_at_seconds,
        distance_cm=dist_med,
        water_level_cm=level,
        valid_echo_count=valid_count,
        float_triggered=envelope.float_triggered,
    )
