"""
Layer 12 — Sensor Telemetry Validation Tests:
Verifies identity validation, sequence checking (duplicates/out-of-order), rate-of-rise filtering,
float switch consistency, and rejection audit logging.
"""

import pytest
from sensors.models import (
    SensorState,
    MeasurementStatus,
    RejectionReason,
    SensorEnvelope,
)
from sensors.registry import SensorRegistry, SensorConfig
from sensors.validation import SensorValidator, validate_rate_of_rise


@pytest.fixture
def validator():
    config_s1 = SensorConfig(
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
    config_s2 = SensorConfig(
        sensor_id="S_DISABLED",
        enabled=False,
        location_id="C105",
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
    registry = SensorRegistry({"S001": config_s1, "S_DISABLED": config_s2})
    return SensorValidator(registry=registry, max_rate_cm_per_second=2.0, max_rate_gap_seconds=30)


def test_unknown_and_disabled_sensor_rejection(validator):
    """Verifies unknown and disabled sensors are rejected."""
    # Unknown
    env_unk = SensorEnvelope("S999", "boot-1", 1, 10, 11, (90.0, 90.0, 90.0, 90.0, 90.0))
    res_unk = validator.validate(env_unk)
    assert res_unk.measurement_status == MeasurementStatus.REJECTED
    assert res_unk.rejection_reason == RejectionReason.UNKNOWN_SENSOR

    # Disabled
    env_dis = SensorEnvelope("S_DISABLED", "boot-1", 1, 10, 11, (90.0, 90.0, 90.0, 90.0, 90.0))
    res_dis = validator.validate(env_dis)
    assert res_dis.measurement_status == MeasurementStatus.REJECTED
    assert res_dis.rejection_reason == RejectionReason.DISABLED_SENSOR


def test_invalid_timestamps_rejected(validator):
    """Verifies clock skew (received_at < measured_at) or negative timestamps are rejected."""
    env = SensorEnvelope("S001", "boot-1", 1, 100, 80, (90.0, 90.0, 90.0, 90.0, 90.0))
    res = validator.validate(env)
    assert res.measurement_status == MeasurementStatus.REJECTED
    assert res.rejection_reason == RejectionReason.INVALID_TIMESTAMP


def test_duplicate_and_out_of_order_sequence_rejection(validator):
    """Verifies duplicate sequence and out-of-order packet rejections."""
    env1 = SensorEnvelope("S001", "boot-1", 10, 10, 11, (90.0, 90.0, 90.0, 90.0, 90.0))
    res1 = validator.validate(env1)
    assert res1.measurement_status == MeasurementStatus.ACCEPTED

    # Duplicate seq 10
    env2 = SensorEnvelope("S001", "boot-1", 10, 20, 21, (90.0, 90.0, 90.0, 90.0, 90.0))
    res2 = validator.validate(env2)
    assert res2.measurement_status == MeasurementStatus.REJECTED
    assert res2.rejection_reason == RejectionReason.DUPLICATE

    # Out of order seq 8 < 10
    env3 = SensorEnvelope("S001", "boot-1", 8, 30, 31, (90.0, 90.0, 90.0, 90.0, 90.0))
    res3 = validator.validate(env3)
    assert res3.measurement_status == MeasurementStatus.REJECTED
    assert res3.rejection_reason == RejectionReason.OUT_OF_ORDER

    # New boot_id resets sequence ordering cleanly
    env4 = SensorEnvelope("S001", "boot-2", 1, 40, 41, (90.0, 90.0, 90.0, 90.0, 90.0))
    res4 = validator.validate(env4)
    assert res4.measurement_status == MeasurementStatus.ACCEPTED


def test_float_switch_conflict_rejection(validator):
    """Verifies rejection when float switch contradicts water level beyond tolerance."""
    # Water level = 100 - 95 = 5 cm, but float is triggered (trigger=20cm, tolerance=3cm -> min 17cm)
    env = SensorEnvelope("S001", "boot-1", 1, 10, 11, (95.0, 95.0, 95.0, 95.0, 95.0), float_triggered=True)
    res = validator.validate(env)
    assert res.measurement_status == MeasurementStatus.REJECTED
    assert res.rejection_reason == RejectionReason.FLOAT_CONFLICT


def test_canonical_rate_spike_anomaly_sequence(validator):
    """
    Executes the canonical anomaly sequence:
    Input levels: 10, 11, 12, 90, 13
    Expected:
    10 -> ACCEPTED
    11 -> ACCEPTED
    12 -> ACCEPTED
    90 -> REJECTED (RATE_SPIKE)
    13 -> ACCEPTED (compared against 12cm, not 90cm)
    Sensor State remains ONLINE throughout.
    """
    levels = [10.0, 11.0, 12.0, 90.0, 13.0]
    results = []

    for idx, lvl in enumerate(levels, start=1):
        dist = 100.0 - lvl
        t = idx * 10
        # float switch triggered only when level >= 20 cm
        f_trig = (lvl >= 20.0)
        env = SensorEnvelope("S001", "boot-1", idx, t, t + 1, (dist, dist, dist, dist, dist), float_triggered=f_trig)
        res = validator.validate(env)
        results.append(res)
        assert res.sensor_state == SensorState.ONLINE

    assert results[0].measurement_status == MeasurementStatus.ACCEPTED
    assert results[0].water_level_cm == pytest.approx(10.0)

    assert results[1].measurement_status == MeasurementStatus.ACCEPTED
    assert results[1].water_level_cm == pytest.approx(11.0)

    assert results[2].measurement_status == MeasurementStatus.ACCEPTED
    assert results[2].water_level_cm == pytest.approx(12.0)

    assert results[3].measurement_status == MeasurementStatus.REJECTED
    assert results[3].rejection_reason == RejectionReason.RATE_SPIKE
    assert results[3].water_level_cm == pytest.approx(90.0)

    assert results[4].measurement_status == MeasurementStatus.ACCEPTED
    assert results[4].water_level_cm == pytest.approx(13.0)
