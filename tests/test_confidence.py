"""
Layer 15 — Confidence & Anti-Circularity Unit Tests:
Verifies coverage, freshness, historical agreement, evidence history factors,
and proves that agreement is evaluated strictly against the ORIGINAL MODEL.
"""

import pytest
from fusion.models import ObservationHistoryRecord
from fusion.history import SensorHistoryTracker
from fusion.confidence import (
    calculate_coverage,
    calculate_agreement,
    calculate_history_factor,
    ConfidenceEstimator,
)


def test_anti_circularity_agreement_uses_original_model():
    """
    CRITICAL ANTI-CIRCULARITY TEST:
    Given:
      Original model depth = 18.0 cm
      Sensor observed depth = 25.0 cm
      (If corrected depth were 20.1 cm, discrepancy would be 4.9 cm).
    Agreement MUST compute MAE against the ORIGINAL model (18.0 cm):
      MAE = |25.0 - 18.0| = 7.0 cm.
      C_a = 1 - 7.0 / 20.0 = 0.65.
    """
    records = [
        ObservationHistoryRecord(
            timestamp_seconds=i * 10,
            model_depth_cm=18.0,       # ORIGINAL model depth
            observed_depth_cm=25.0,    # Sensor observation
            residual_cm=7.0,
        )
        for i in range(1, 6)
    ]

    agreement, n = calculate_agreement(records, scale_cm=20.0, minimum_observations=5)
    assert n == 5
    # Expected: 1 - (7.0 / 20.0) = 0.65
    assert agreement == pytest.approx(0.65)


def test_coverage_and_freshness_bounds():
    """Verifies coverage and freshness bounds in [0, 1]."""
    # Coverage: 0m -> 1.0, 500m -> 0.5, >=1000m -> 0.0
    assert calculate_coverage(0.0, 1000.0) == pytest.approx(1.0)
    assert calculate_coverage(500.0, 1000.0) == pytest.approx(0.5)
    assert calculate_coverage(1200.0, 1000.0) == pytest.approx(0.0)


def test_history_factor():
    """Verifies history factor: N=2, target=10 -> H=0.2."""
    assert calculate_history_factor(2, 10) == pytest.approx(0.2)
    assert calculate_history_factor(10, 10) == pytest.approx(1.0)
    assert calculate_history_factor(15, 10) == pytest.approx(1.0)
    assert calculate_history_factor(0, 10) == pytest.approx(0.0)


def test_no_sensor_yields_zero_confidence():
    """Verifies that cells with no nearby sensor receive 0.0 confidence."""
    estimator = ConfidenceEstimator(max_distance_m=1000.0)
    history_tracker = SensorHistoryTracker()

    conf = estimator.estimate_cell_confidence(
        cell_id="C_REMOTE",
        cell_coords_m=(5000.0, 5000.0),
        sensor_coords_m_by_id={"S1": (0.0, 0.0)},
        sensor_health_by_id={"S1": "ONLINE"},
        sensor_last_updated_by_id={"S1": 60},
        history_tracker=history_tracker,
        current_timestamp_seconds=60,
    )
    assert conf.score == pytest.approx(0.0)
    assert conf.coverage == pytest.approx(0.0)


def test_offline_sensor_yields_zero_confidence():
    """Verifies that if nearest sensor is OFFLINE, confidence is 0.0."""
    estimator = ConfidenceEstimator(max_distance_m=1000.0)
    history_tracker = SensorHistoryTracker()

    conf = estimator.estimate_cell_confidence(
        cell_id="C1",
        cell_coords_m=(10.0, 10.0),
        sensor_coords_m_by_id={"S1": (0.0, 0.0)},
        sensor_health_by_id={"S1": "OFFLINE"},
        sensor_last_updated_by_id={"S1": 60},
        history_tracker=history_tracker,
        current_timestamp_seconds=60,
    )
    assert conf.score == pytest.approx(0.0)


def test_insufficient_history_suppresses_agreement_without_error():
    """Verifies that history < 5 sets agreement=0.0 and applies lower history factor."""
    records = [
        ObservationHistoryRecord(10, 18.0, 18.0, 0.0),
        ObservationHistoryRecord(20, 18.0, 18.0, 0.0),
    ]
    agreement, count = calculate_agreement(records, minimum_observations=5)
    assert count == 2
    assert agreement == pytest.approx(0.0)
