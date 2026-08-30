"""
Layer 11 — Ultrasonic Measurement Tests:
Verifies distance to water level conversion (L = H_ref - D), envelope processing,
and strict preservation of negative levels without silent clamping.
"""

import pytest

from sensors.models import SensorEnvelope
from sensors.registry import SensorConfig
from sensors.ultrasonic import distance_to_water_level, process_measurement


@pytest.fixture
def sensor_config():
    return SensorConfig(
        sensor_id="S001",
        enabled=True,
        location_id="C104",
        reference_height_cm=100.0,
        min_distance_cm=2.0,
        max_distance_cm=400.0,
        min_level_cm=0.0,
        max_level_cm=95.0,
        samples_per_measurement=5,
        minimum_valid_samples=3,
        float_enabled=True,
        float_trigger_level_cm=20.0,
        float_tolerance_cm=3.0,
    )


def test_distance_to_water_level_standard():
    """Verifies L = 100 - 73 = 27 cm."""
    assert distance_to_water_level(100.0, 73.0) == pytest.approx(27.0)


def test_negative_water_level_not_clamped():
    """Verifies that distance exceeding reference height produces negative level without clamping to 0."""
    # Distance = 110cm with reference = 100cm -> level = -10cm
    assert distance_to_water_level(100.0, 110.0) == pytest.approx(-10.0)


def test_process_measurement_envelope(sensor_config):
    """Verifies full envelope processing."""
    env = SensorEnvelope(
        sensor_id="S001",
        boot_id="boot-001",
        sequence=1,
        measured_at_seconds=10,
        received_at_seconds=11,
        distance_samples_cm=(73.0, 73.1, 72.9, 73.0, 73.0),
        float_triggered=False,
    )
    meas = process_measurement(env, sensor_config)
    assert meas.distance_cm == pytest.approx(73.0)
    assert meas.water_level_cm == pytest.approx(27.0)
    assert meas.valid_echo_count == 5
    assert meas.float_triggered is False
