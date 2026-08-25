"""
Scenario 2: Sensor Pipeline Validation
Injects out-of-range and rate-spike readings, asserting both are flagged and excluded from fusion.
"""

import pytest
from backend.services.simulation_service import SimulationService
from sensor.validation import validate_sensor_reading


def test_sensor_validation_rules():
    # 1. Normal reading
    assert validate_sensor_reading(12.0, 10.0, dt_seconds=60.0, r_critical_cm_min=5.0) == "VALID"

    # 2. Out-of-range negative
    assert validate_sensor_reading(-5.0, 0.0, dt_seconds=60.0) in ("OUT_OF_RANGE", "INVALID_RANGE")

    # 3. Out-of-range excessive height (>300cm)
    assert validate_sensor_reading(450.0, 10.0, dt_seconds=60.0, max_physical_depth_cm=300.0) in ("OUT_OF_RANGE", "INVALID_RANGE")

    # 4. Critical rate of rise spike (e.g. jump 20cm in 60s -> 20 cm/min > 5 cm/min)
    assert validate_sensor_reading(30.0, 5.0, dt_seconds=60.0, r_critical_cm_min=5.0) in ("RATE_SPIKE", "INVALID_SPIKE")

    # 5. Missing heartbeat
    assert validate_sensor_reading(10.0, 8.0, heartbeat=False) == "MISSING_HEARTBEAT"


def test_sensor_spike_and_range_exclusion_in_simulation():
    sim = SimulationService()
    sim.reset()

    # Step 1: Valid initial baseline
    sim.step(rainfall_input=0.0, sensor_readings={1: {"water_level_cm": 5.0, "heartbeat": True}})
    sensor_1 = sim.sensors[1]
    assert sensor_1.status == "ONLINE"
    assert sensor_1.last_valid_reading_cm == 5.0

    # Step 2: Inject extreme rate spike (jump to 80cm)
    sim.step(rainfall_input=0.0, sensor_readings={1: {"water_level_cm": 80.0, "heartbeat": True}})
    assert sensor_1.last_quality_flag in ("RATE_SPIKE", "INVALID_SPIKE")
    # Should not update last_valid_reading_cm
    assert sensor_1.last_valid_reading_cm == 5.0

    # Step 3: Inject out-of-range reading (999cm)
    sim.step(rainfall_input=0.0, sensor_readings={1: {"water_level_cm": 999.0, "heartbeat": True}})
    assert sensor_1.last_quality_flag in ("OUT_OF_RANGE", "INVALID_RANGE")
    assert sensor_1.last_valid_reading_cm == 5.0
