"""
Layer 14 — Spatial Bias Correction Unit Tests:
Verifies distance decay, freshness attenuation, multi-sensor weighting, dry-cell protection,
correction bounds, and offline sensor exclusion.
"""

import pytest

from fusion.models import SensorBiasState
from fusion.spatial import SpatialBiasCorrector, calculate_freshness


def test_freshness_decay():
    """Verifies freshness calculation: age=0 -> 1.0, age=90 -> 0.5, age>=180 -> 0.0."""
    assert calculate_freshness(0, 180) == pytest.approx(1.0)
    assert calculate_freshness(90, 180) == pytest.approx(0.5)
    assert calculate_freshness(180, 180) == pytest.approx(0.0)
    assert calculate_freshness(200, 180) == pytest.approx(0.0)


def test_colocated_and_distance_decay():
    """
    Verifies that colocated cell receives full local bias,
    while distant cells receive decaying correction.
    """
    corrector = SpatialBiasCorrector(max_distance_m=1000.0, max_absolute_correction_cm=15.0)

    sensor_state = SensorBiasState(sensor_id="S1", bias_cm=10.0, observation_count=5, last_updated_seconds=60, is_eligible=True)
    states = {"S1": sensor_state}
    coords = {"S1": (0.0, 0.0)}
    health = {"S1": "ONLINE"}
    quality = {"S1": 1.0}

    # Colocated cell (0, 0)
    c_zero = corrector.calculate_cell_correction(
        cell_id="C0",
        cell_model_depth_cm=5.0,
        cell_coords_m=(0.0, 0.0),
        sensor_states=states,
        sensor_coords_m_by_id=coords,
        sensor_health_by_id=health,
        sensor_qualities_by_id=quality,
        current_timestamp_seconds=60,
    )
    assert c_zero == pytest.approx(10.0)

    # Nearby cell (100m away)
    c_100m = corrector.calculate_cell_correction(
        cell_id="C1",
        cell_model_depth_cm=5.0,
        cell_coords_m=(100.0, 0.0),
        sensor_states=states,
        sensor_coords_m_by_id=coords,
        sensor_health_by_id=health,
        sensor_qualities_by_id=quality,
        current_timestamp_seconds=60,
    )
    assert 0.0 < c_100m <= 10.0

    # Outside radius (1200m away) -> 0.0
    c_far = corrector.calculate_cell_correction(
        cell_id="C2",
        cell_model_depth_cm=5.0,
        cell_coords_m=(1200.0, 0.0),
        sensor_states=states,
        sensor_coords_m_by_id=coords,
        sensor_health_by_id=health,
        sensor_qualities_by_id=quality,
        current_timestamp_seconds=60,
    )
    assert c_far == pytest.approx(0.0)


def test_dry_cell_protection():
    """Verifies that non-colocated dry cells (model depth < 1cm) do not receive spread bias."""
    corrector = SpatialBiasCorrector(minimum_model_depth_for_spatial_correction_cm=1.0)
    states = {"S1": SensorBiasState("S1", bias_cm=10.0, observation_count=5, last_updated_seconds=60, is_eligible=True)}

    c_dry = corrector.calculate_cell_correction(
        cell_id="C_DRY",
        cell_model_depth_cm=0.0,  # Dry cell
        cell_coords_m=(50.0, 0.0),
        sensor_states=states,
        sensor_coords_m_by_id={"S1": (0.0, 0.0)},
        sensor_health_by_id={"S1": "ONLINE"},
        sensor_qualities_by_id={"S1": 1.0},
        current_timestamp_seconds=60,
    )
    assert c_dry == pytest.approx(0.0)


def test_offline_sensor_has_zero_spatial_influence():
    """Verifies that an OFFLINE sensor has zero live spatial influence."""
    corrector = SpatialBiasCorrector()
    states = {"S1": SensorBiasState("S1", bias_cm=10.0, observation_count=5, last_updated_seconds=60, is_eligible=True)}

    c_off = corrector.calculate_cell_correction(
        cell_id="C1",
        cell_model_depth_cm=5.0,
        cell_coords_m=(50.0, 0.0),
        sensor_states=states,
        sensor_coords_m_by_id={"S1": (0.0, 0.0)},
        sensor_health_by_id={"S1": "OFFLINE"},
        sensor_qualities_by_id={"S1": 1.0},
        current_timestamp_seconds=60,
    )
    assert c_off == pytest.approx(0.0)


def test_multiple_sensors_equidistant_averaging():
    """
    Verifies that a cell equidistant from S1 (+10 cm) and S2 (-5 cm)
    with equal freshness and quality receives the balanced mean (+2.5 cm).
    """
    corrector = SpatialBiasCorrector()
    states = {
        "S1": SensorBiasState("S1", bias_cm=10.0, observation_count=5, last_updated_seconds=60, is_eligible=True),
        "S2": SensorBiasState("S2", bias_cm=-5.0, observation_count=5, last_updated_seconds=60, is_eligible=True),
    }
    coords = {"S1": (-50.0, 0.0), "S2": (50.0, 0.0)}
    health = {"S1": "ONLINE", "S2": "ONLINE"}
    quality = {"S1": 1.0, "S2": 1.0}

    # Cell at (0, 0) is equidistant from (-50, 0) and (50, 0)
    c_mid = corrector.calculate_cell_correction(
        cell_id="C_MID",
        cell_model_depth_cm=10.0,
        cell_coords_m=(0.0, 0.0),
        sensor_states=states,
        sensor_coords_m_by_id=coords,
        sensor_health_by_id=health,
        sensor_qualities_by_id=quality,
        current_timestamp_seconds=60,
    )
    # (10 + (-5)) / 2 = 2.5 cm
    assert c_mid == pytest.approx(2.5)
