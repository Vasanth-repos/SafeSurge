"""
Layer 11 — Sensor Registry Tests:
Verifies configuration loading from data/sensors/registry.yaml, individual sensor overrides,
and invalid configuration parameter rejections.
"""

import pytest

from sensors.registry import SensorConfig, SensorRegistry


def test_load_registry_from_yaml():
    """Verifies loading data/sensors/registry.yaml."""
    reg = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
    assert "S001" in reg
    assert "S002" in reg
    assert "S003_DISABLED" in reg

    s1 = reg.get("S001")
    assert s1.enabled is True
    assert s1.location_id == "C104"
    assert s1.reference_height_cm == pytest.approx(100.0)
    assert s1.float_trigger_level_cm == pytest.approx(20.0)

    s3 = reg.get("S003_DISABLED")
    assert s3.enabled is False


def test_invalid_sensor_config_rejected():
    """Verifies rejection of invalid reference height or minimum sample count."""
    with pytest.raises(ValueError, match="reference_height_cm must be > 0"):
        SensorConfig("S_BAD", True, "C1", -10.0, 2.0, 400.0, 0.0, 95.0, 5, 3, True, 20.0, 3.0)

    with pytest.raises(ValueError, match="minimum_valid_samples"):
        SensorConfig("S_BAD2", True, "C1", 100.0, 2.0, 400.0, 0.0, 95.0, 5, 6, True, 20.0, 3.0)
