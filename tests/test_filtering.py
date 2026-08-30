"""
Layer 11 — Ultrasonic Echo Filtering Tests:
Verifies invalid sample filtering, range boundary constraints, minimum count requirements,
and median calculation robustness against single-burst outlier spikes.
"""

import pytest

from sensors.filtering import filter_echoes


def test_clean_burst_median():
    """Verifies median calculation for clean sample burst."""
    samples = [72.9, 73.1, 73.0, 73.2, 72.8]
    med, count = filter_echoes(samples, min_distance_cm=2.0, max_distance_cm=400.0, minimum_valid_samples=3)
    assert count == 5
    assert med == pytest.approx(73.0)


def test_outlier_spike_rejection_via_median():
    """Verifies that a severe spike in one sample (150cm) does not bias the median."""
    samples = [72.9, 73.1, 73.0, 150.0, 73.2]
    med, count = filter_echoes(samples, min_distance_cm=2.0, max_distance_cm=400.0, minimum_valid_samples=3)
    assert count == 5
    assert med == pytest.approx(73.1)


def test_null_and_infinite_samples_filtered():
    """Verifies None and non-finite values are filtered."""
    samples = [72.9, None, float("nan"), 73.1, 73.0]
    med, count = filter_echoes(samples, min_distance_cm=2.0, max_distance_cm=400.0, minimum_valid_samples=3)
    assert count == 3
    assert med == pytest.approx(73.0)


def test_insufficient_samples_returns_none():
    """Verifies returning None when valid samples fall below minimum_valid_samples."""
    samples = [72.9, None, None, None, None]
    med, count = filter_echoes(samples, min_distance_cm=2.0, max_distance_cm=400.0, minimum_valid_samples=3)
    assert count == 1
    assert med is None


def test_out_of_bounds_echoes_filtered():
    """Verifies samples outside [min, max] range are discarded."""
    samples = [1.0, 500.0, 73.0, 73.2, 73.1]  # 1.0 < 2.0 and 500.0 > 400.0
    med, count = filter_echoes(samples, min_distance_cm=2.0, max_distance_cm=400.0, minimum_valid_samples=3)
    assert count == 3
    assert med == pytest.approx(73.1)
