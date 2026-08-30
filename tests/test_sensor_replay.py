"""
Layer 11-12 — Sensor Dataset Replay Tests:
Loads sensor_01.json and sensor_anomaly_01.json from data/replay/sensors/
and verifies end-to-end replay processing and anomaly rejection.
"""

from sensors.models import MeasurementStatus, RejectionReason, SensorState
from sensors.registry import SensorRegistry
from sensors.simulator import load_sensor_replay
from sensors.validation import SensorValidator


def test_replay_sensor_01():
    """Verifies clean replay of data/replay/sensors/sensor_01.json."""
    registry = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
    validator = SensorValidator(registry=registry)

    envelopes = load_sensor_replay("data/replay/sensors/sensor_01.json")
    assert len(envelopes) == 3

    for env in envelopes:
        res = validator.validate(env)
        assert res.measurement_status == MeasurementStatus.ACCEPTED
        assert res.sensor_state == SensorState.ONLINE
        assert res.water_level_cm is not None


def test_replay_sensor_anomaly_01():
    """Verifies replay of data/replay/sensors/sensor_anomaly_01.json."""
    registry = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
    validator = SensorValidator(registry=registry)

    envelopes = load_sensor_replay("data/replay/sensors/sensor_anomaly_01.json")
    assert len(envelopes) == 5

    results = [validator.validate(env) for env in envelopes]

    assert results[0].measurement_status == MeasurementStatus.ACCEPTED
    assert results[1].measurement_status == MeasurementStatus.ACCEPTED
    assert results[2].measurement_status == MeasurementStatus.ACCEPTED
    assert results[3].measurement_status == MeasurementStatus.REJECTED
    assert results[3].rejection_reason == RejectionReason.RATE_SPIKE
    assert results[4].measurement_status == MeasurementStatus.ACCEPTED

    for r in results:
        assert r.sensor_state == SensorState.ONLINE
