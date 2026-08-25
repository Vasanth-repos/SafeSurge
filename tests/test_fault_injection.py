"""
Tests for Layer 24 Fault Injection Framework & Disruption Scenarios.
"""

import pytest
from replay.faults import Fault, FaultType, FaultInjectionEngine
from replay.scenarios import ScenarioRunner


def test_sensor_offline_fault():
    fault = Fault("F1", FaultType.SENSOR_OFFLINE, 1800, 3600, {"sensor_id": "S001"})
    engine = FaultInjectionEngine([fault])

    # Inactive before start
    reading, status, modified = engine.apply_sensor_override("S001", 1000, 15.0, "ONLINE")
    assert status == "ONLINE"
    assert modified is False

    # Active during window
    reading, status, modified = engine.apply_sensor_override("S001", 2000, 15.0, "ONLINE")
    assert status == "OFFLINE"
    assert reading is None
    assert modified is True


def test_sensor_spike_fault():
    fault = Fault("F2", FaultType.SENSOR_SPIKE, 1800, 1860, {"sensor_id": "S001", "depth_cm": 90.0})
    engine = FaultInjectionEngine([fault])

    reading, status, modified = engine.apply_sensor_override("S001", 1800, 15.0, "ONLINE")
    assert status == "ONLINE"
    assert reading == 90.0
    assert modified is True


def test_capacity_reduction_fault():
    fault = Fault("F3", FaultType.DRAINAGE_CAPACITY, 2700, 3600, {"edge_id": "E001", "capacity_factor": 0.3})
    engine = FaultInjectionEngine([fault])

    fac = engine.get_capacity_factor("E001", 3000, default_factor=1.0)
    assert fac == 0.3
    fac_other = engine.get_capacity_factor("E002", 3000, default_factor=1.0)
    assert fac_other == 1.0
