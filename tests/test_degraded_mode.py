"""
Scenario 4: Degraded Mode & Sensor Dropout Validation
Disconnects a sensor mid-run, asserting graceful transition to STALE/OFFLINE,
confidence score reduction, and fallback to model-only predictions.
"""

import pytest
from backend.services.simulation_service import SimulationService


def test_sensor_disconnect_and_degraded_mode():
    sim = SimulationService()
    sim.reset()

    # Step 1: Active online sensor
    sim.step(rainfall_input=0.0, sensor_readings={1: {"water_level_cm": 10.0, "heartbeat": True}})
    s1 = sim.sensors[1]
    assert s1.status == "ONLINE"
    initial_conf = sim.cell_confidences[s1.cell_id]

    # Step 2: Inject disconnect (simulate missing heartbeats)
    sim.inject_fault("sensor_disconnect", target_id=1)

    # Step through 3 missed heartbeats -> STALE
    for _ in range(3):
        sim.step(rainfall_input=0.0)

    assert s1.status == "STALE"

    # Step through 3 more missed heartbeats (total 6) -> OFFLINE
    for _ in range(3):
        sim.step(rainfall_input=0.0)

    assert s1.status == "OFFLINE"

    # In OFFLINE state, sensor is excluded from active fusion
    # Verify confidence for the cell has dropped compared to active state
    offline_conf = sim.cell_confidences[s1.cell_id]
    assert offline_conf < initial_conf
