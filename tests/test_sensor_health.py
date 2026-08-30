"""
Layer 12 — Sensor Health State Tests:
Verifies connectivity state transitions (ONLINE -> STALE -> OFFLINE) and clock skew invalidations.
"""

from sensors.health import SensorHealthTracker, evaluate_sensor_health
from sensors.models import SensorState


def test_sensor_health_transitions():
    """Verifies health state transitions based on age."""
    # Never received -> OFFLINE
    assert evaluate_sensor_health(100, None, 30, 180) == SensorState.OFFLINE

    # Age = 10s (<= 30s) -> ONLINE
    assert evaluate_sensor_health(100, 90, 30, 180) == SensorState.ONLINE

    # Age = 45s (> 30s, <= 180s) -> STALE
    assert evaluate_sensor_health(100, 55, 30, 180) == SensorState.STALE

    # Age = 200s (> 180s) -> OFFLINE
    assert evaluate_sensor_health(300, 100, 30, 180) == SensorState.OFFLINE

    # Clock skew (received in future) -> INVALID
    assert evaluate_sensor_health(100, 110, 30, 180) == SensorState.INVALID


def test_health_tracker_stateful():
    """Verifies tracker records heartbeat and evaluates state."""
    tracker = SensorHealthTracker(stale_after_seconds=30, offline_after_seconds=180)
    assert tracker.get_state("S001", 100) == SensorState.OFFLINE

    tracker.record_heartbeat("S001", 100)
    assert tracker.get_state("S001", 110) == SensorState.ONLINE
    assert tracker.get_state("S001", 140) == SensorState.STALE
    assert tracker.get_state("S001", 300) == SensorState.OFFLINE
