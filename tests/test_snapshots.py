"""
Tests for Layer 20–25 SimulationSnapshot immutability and contract serialization.
"""

import pytest
from flood_engine.snapshot import (
    SimulationSnapshot,
    CellSnapshot,
    RoadSnapshot,
    SensorSnapshot,
    ForecastSnapshot,
    MassBalanceSnapshot,
    SystemStatus,
    RainfallStatus,
)


def test_snapshot_immutability_and_serialization():
    cell = CellSnapshot(
        cell_id="C001",
        row=0,
        col=0,
        elevation_m=20.0,
        model_depth_cm=10.0,
        correction_cm=1.5,
        corrected_depth_cm=11.5,
        risk="WATCH",
        confidence=0.85,
        status="VALID",
    )

    road = RoadSnapshot(
        road_id="R001",
        from_node="A",
        to_node="B",
        mean_depth_cm=5.0,
        max_relevant_depth_cm=5.0,
        affected_fraction=1.0,
        risk="WATCH",
        confidence=0.85,
    )

    sensor = SensorSnapshot(
        sensor_id="S001",
        location_id="C001",
        status="ONLINE",
        last_valid_reading_cm=11.5,
        last_valid_timestamp_seconds=60,
        age_seconds=0,
        bias_cm=1.5,
    )

    mb = MassBalanceSnapshot(
        runoff_input_m3=100.0,
        previous_storage_m3=50.0,
        current_storage_m3=120.0,
        drainage_m3=25.0,
        boundary_outflow_m3=5.0,
        balance_error_m3=0.0,
        relative_error=0.0,
        status="PASS",
    )

    snap = SimulationSnapshot(
        simulation_id="storm_01",
        timestamp_seconds=60,
        simulation_status="RUNNING",
        system_status=SystemStatus.NORMAL.value,
        rainfall_status=RainfallStatus.VALID.value,
        flood_cells=(cell,),
        road_risks=(road,),
        drainage_states=(),
        sensor_states=(sensor,),
        anomalies=(),
        forecast=None,
        mass_balance=mb,
    )

    # Immutability check
    with pytest.raises(Exception):
        snap.timestamp_seconds = 120

    data = snap.to_dict()
    assert data["simulation_id"] == "storm_01"
    assert data["timestamp_seconds"] == 60
    assert data["system_status"] == "NORMAL"
    assert len(data["cells"]) == 1
    assert data["cells"][0]["depth_cm"] == 11.5
    assert data["mass_balance"]["status"] == "PASS"
