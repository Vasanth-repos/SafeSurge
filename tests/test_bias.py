"""
Layer 13 — Sensor Bias Estimation Unit Tests:
Verifies residual calculation, EWMA update, minimum observation warmup,
large-residual rejection threshold, and clamping safety bounds.
"""

import pytest
from fusion.models import SensorObservation
from fusion.bias import calculate_residual, update_ewma_bias, SensorBiasEstimator


def test_residual_calculation():
    """Verifies e = H_obs - H_model: 25 - 18 = +7 cm, 12 - 18 = -6 cm."""
    assert calculate_residual(25.0, 18.0) == pytest.approx(7.0)
    assert calculate_residual(12.0, 18.0) == pytest.approx(-6.0)


def test_ewma_bias_update_and_clamping():
    """Verifies B_t = 0.3 * 7 + 0.7 * 0 = 2.1 cm, and max bias clamping at 50 cm."""
    b1 = update_ewma_bias(current_bias_cm=0.0, residual_cm=7.0, alpha=0.3, quality=1.0, max_bias_cm=50.0)
    assert b1 == pytest.approx(2.1)

    # Clamping
    b_huge = update_ewma_bias(current_bias_cm=45.0, residual_cm=50.0, alpha=0.5, quality=1.0, max_bias_cm=50.0)
    assert b_huge <= 50.0


def test_minimum_observation_warmup_and_estimator():
    """
    Verifies that bias is NOT eligible until minimum_bias_observations (3) is reached:
    Obs 1 -> residual recorded, is_eligible=False, bias=0
    Obs 2 -> residual recorded, is_eligible=False, bias=0
    Obs 3 -> is_eligible=True, bias updated via EWMA
    """
    estimator = SensorBiasEstimator(bias_alpha=0.3, minimum_bias_observations=3, max_residual_for_bias_update_cm=20.0)

    # Obs 1
    o1 = SensorObservation("S1", "C104", 10, 25.0, "ONLINE", "ACCEPTED", quality=1.0)
    s1 = estimator.update_observation(o1, model_depth_cm=18.0)
    assert s1.observation_count == 1
    assert s1.is_eligible is False
    assert s1.bias_cm == 0.0

    # Obs 2
    o2 = SensorObservation("S1", "C104", 20, 25.0, "ONLINE", "ACCEPTED", quality=1.0)
    s2 = estimator.update_observation(o2, model_depth_cm=18.0)
    assert s2.observation_count == 2
    assert s2.is_eligible is False
    assert s2.bias_cm == 0.0

    # Obs 3 -> becomes eligible and updates bias: 0.3 * 7.0 = 2.1 cm
    o3 = SensorObservation("S1", "C104", 30, 25.0, "ONLINE", "ACCEPTED", quality=1.0)
    s3 = estimator.update_observation(o3, model_depth_cm=18.0)
    assert s3.observation_count == 3
    assert s3.is_eligible is True
    assert s3.bias_cm == pytest.approx(2.1)


def test_large_residual_protection_ignored():
    """
    Verifies that a residual exceeding max_residual_for_bias_update_cm (20cm)
    records the residual but does NOT update persistent bias.
    """
    estimator = SensorBiasEstimator(bias_alpha=0.3, minimum_bias_observations=3, max_residual_for_bias_update_cm=20.0)

    # Prime with 3 normal observations (model=18, obs=25 -> e=+7)
    for t in (10, 20, 30):
        estimator.update_observation(
            SensorObservation("S1", "C104", t, 25.0, "ONLINE", "ACCEPTED"),
            model_depth_cm=18.0,
        )
    b_before = estimator.get_state("S1").bias_cm
    assert b_before > 0.0

    # Inject large residual: model=10, obs=50 -> e=+40 (> 20cm)
    o_spike = SensorObservation("S1", "C104", 40, 50.0, "ONLINE", "ACCEPTED")
    s_spike = estimator.update_observation(o_spike, model_depth_cm=10.0)

    assert s_spike.last_residual_cm == pytest.approx(40.0)
    # Bias is unchanged by the outlier
    assert s_spike.bias_cm == pytest.approx(b_before)


def test_unaccepted_or_offline_observations_ignored():
    """Verifies that REJECTED or OFFLINE observations do not update bias count or values."""
    estimator = SensorBiasEstimator(minimum_bias_observations=3)

    # REJECTED
    o_rej = SensorObservation("S1", "C104", 10, 25.0, "ONLINE", "REJECTED")
    s_rej = estimator.update_observation(o_rej, model_depth_cm=18.0)
    assert s_rej.observation_count == 0

    # OFFLINE
    o_off = SensorObservation("S1", "C104", 20, 25.0, "OFFLINE", "ACCEPTED")
    s_off = estimator.update_observation(o_off, model_depth_cm=18.0)
    assert s_off.observation_count == 0
