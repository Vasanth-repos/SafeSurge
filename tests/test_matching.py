"""
Layer 13 — Sensor-to-Model Spatiotemporal Matching Tests:
Verifies matching logic, time skew tolerances, and missing cell handling.
"""

import pytest

from fusion.matching import match_sensor_to_model
from fusion.models import SensorObservation


def test_matching_exact_and_acceptable_time_difference():
    """Verifies matching when time difference <= 30s."""
    model_depths = {"C104": 18.0}

    # Exact time
    obs_exact = SensorObservation("S1", "C104", 60, 25.0, "ONLINE", "ACCEPTED")
    m1, d1, r1 = match_sensor_to_model(obs_exact, model_depths, model_timestamp_seconds=60, max_time_difference_seconds=30)
    assert m1 is True
    assert d1 == pytest.approx(18.0)
    assert r1 == pytest.approx(7.0)

    # 20s difference (acceptable)
    obs_skew = SensorObservation("S1", "C104", 40, 25.0, "ONLINE", "ACCEPTED")
    m2, d2, r2 = match_sensor_to_model(obs_skew, model_depths, model_timestamp_seconds=60, max_time_difference_seconds=30)
    assert m2 is True


def test_excessive_time_difference_rejected():
    """Verifies that time difference > 30s fails matching."""
    model_depths = {"C104": 18.0}
    obs_late = SensorObservation("S1", "C104", 10, 25.0, "ONLINE", "ACCEPTED")
    matched, _, _ = match_sensor_to_model(obs_late, model_depths, model_timestamp_seconds=60, max_time_difference_seconds=30)
    assert matched is False


def test_missing_model_cell_fails_matching():
    """Verifies unknown cell ID returns matched=False."""
    model_depths = {"C104": 18.0}
    obs_unknown = SensorObservation("S1", "C999", 60, 25.0, "ONLINE", "ACCEPTED")
    matched, _, _ = match_sensor_to_model(obs_unknown, model_depths, model_timestamp_seconds=60)
    assert matched is False
