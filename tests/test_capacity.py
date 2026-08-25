"""
Layer 8 — Drainage Capacity Scenario Unit Tests:
Verifies effective capacity scaling (C_eff = C0 * F), base capacity immutability,
timeline event progression, status labeling, SCENARIO mode guarantees, and utilization.
"""

import pytest
import math
from flood_engine.capacity import (
    effective_capacity_m3_s,
    capacity_status,
    utilization,
    CapacityEvent,
    CapacityScenario,
    CapacityScenarioState,
    build_state,
    load_capacity_scenario,
)


def test_effective_capacity_nominal_reduced_severe():
    """Verifies C_eff = C0 * F for 1.0, 0.6, and 0.3 factors."""
    base = 0.02
    assert effective_capacity_m3_s(base, 1.0) == pytest.approx(0.020)
    assert effective_capacity_m3_s(base, 0.6) == pytest.approx(0.012)
    assert effective_capacity_m3_s(base, 0.3) == pytest.approx(0.006)


def test_base_capacity_immutability():
    """Verifies that base capacity variable remains strictly immutable."""
    base = 0.02
    eff = effective_capacity_m3_s(base, 0.3)
    assert eff == pytest.approx(0.006)
    assert base == pytest.approx(0.02)


def test_factor_validation_rules():
    """Verifies factor validation: reject booleans, non-numerics, negative, >1, and inf."""
    with pytest.raises(ValueError, match="numeric"):
        effective_capacity_m3_s(0.02, True)

    with pytest.raises(ValueError, match="numeric"):
        effective_capacity_m3_s(0.02, "invalid")

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        effective_capacity_m3_s(0.02, -0.1)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        effective_capacity_m3_s(0.02, 1.5)

    with pytest.raises(ValueError, match="finite"):
        effective_capacity_m3_s(0.02, float("inf"))


def test_scenario_timeline_transitions():
    """Verifies exact timestamp transitions at 45 min (2700s) and recovery at 75 min (4500s)."""
    events = [
        CapacityEvent(timestamp_seconds=0, edge_ids=("E002",), capacity_factor=1.0),
        CapacityEvent(timestamp_seconds=2700, edge_ids=("E002",), capacity_factor=0.3),
        CapacityEvent(timestamp_seconds=4500, edge_ids=("E002",), capacity_factor=1.0),
    ]
    scenario = CapacityScenario(
        scenario_id="scenario_01",
        name="Test Scenario",
        edge_ids=["E001", "E002", "E003"],
        events=events,
    )

    # Before minute 45
    assert scenario.factors_at(2699)["E002"] == pytest.approx(1.0)
    # At minute 45
    assert scenario.factors_at(2700)["E002"] == pytest.approx(0.3)
    # During degraded period
    assert scenario.factors_at(3600)["E002"] == pytest.approx(0.3)
    # Right before minute 75
    assert scenario.factors_at(4499)["E002"] == pytest.approx(0.3)
    # At minute 75 recovery
    assert scenario.factors_at(4500)["E002"] == pytest.approx(1.0)


def test_unaffected_edges_remain_nominal():
    """Verifies that edges not targeted by events remain strictly at F=1.0."""
    events = [
        CapacityEvent(timestamp_seconds=2700, edge_ids=("E002",), capacity_factor=0.3),
    ]
    scenario = CapacityScenario(
        scenario_id="scenario_01",
        name="Targeted Degradation",
        edge_ids=["E001", "E002", "E003"],
        events=events,
    )
    factors = scenario.factors_at(3000)
    assert factors["E001"] == pytest.approx(1.0)
    assert factors["E002"] == pytest.approx(0.3)
    assert factors["E003"] == pytest.approx(1.0)


def test_duplicate_events_rejection():
    """Verifies rejection of duplicate events for the same edge at the same timestamp."""
    events = [
        CapacityEvent(timestamp_seconds=2700, edge_ids=("E002",), capacity_factor=0.3),
        CapacityEvent(timestamp_seconds=2700, edge_ids=("E002",), capacity_factor=0.6),
    ]
    with pytest.raises(ValueError, match="Duplicate capacity event"):
        CapacityScenario("scen_dup", "Duplicate Test", ["E002"], events)


def test_unknown_edge_rejection():
    """Verifies rejection of events targeting edges not registered in scenario edge list."""
    events = [
        CapacityEvent(timestamp_seconds=100, edge_ids=("E999",), capacity_factor=0.5),
    ]
    with pytest.raises(ValueError, match="unknown edges"):
        CapacityScenario("scen_unk", "Unknown Edge Test", ["E001", "E002"], events)


def test_capacity_scenario_state_mode_is_scenario():
    """Verifies that scenario states strictly declare mode='SCENARIO'."""
    events = [
        CapacityEvent(timestamp_seconds=0, edge_ids=("E001",), capacity_factor=0.6),
    ]
    scenario = CapacityScenario("scen_mode", "Mode Test", ["E001"], events)
    base_caps = {"E001": 0.05}
    state = build_state(scenario, timestamp_seconds=60, base_capacity_m3_s_by_edge=base_caps)

    assert state.mode == "SCENARIO"
    assert state.capacity_factor_by_edge["E001"] == pytest.approx(0.6)
    assert state.effective_capacity_m3_s_by_edge["E001"] == pytest.approx(0.03)


def test_capacity_status_labels():
    """Verifies status categorization."""
    assert capacity_status(1.0) == "NORMAL"
    assert capacity_status(0.8) == "NORMAL"
    assert capacity_status(0.6) == "REDUCED"
    assert capacity_status(0.5) == "REDUCED"
    assert capacity_status(0.3) == "SEVERE"
    assert capacity_status(0.0) == "SEVERE"


def test_edge_utilization_calculation():
    """Verifies utilization metric calculation."""
    # Transmitted = 0.36 m³ in 60s with C_eff = 0.006 m³/s (Capacity vol = 0.36 m³) -> U = 1.0 (100%)
    assert utilization(0.36, 0.006, 60.0) == pytest.approx(1.0)
    # Transmitted = 0.18 m³ in 60s with C_eff = 0.006 m³/s -> U = 0.5 (50%)
    assert utilization(0.18, 0.006, 60.0) == pytest.approx(0.5)
    # Zero flow -> U = 0.0
    assert utilization(0.0, 0.006, 60.0) == pytest.approx(0.0)


def test_load_scenario_from_json():
    """Verifies loading data/scenarios/drainage_capacity_01.json."""
    scenario = load_capacity_scenario(
        "data/scenarios/drainage_capacity_01.json",
        known_edge_ids=["E001", "E002", "E003", "E004"],
    )
    assert scenario.scenario_id == "drainage_capacity_01"
    assert "E002" in scenario.edge_ids
    assert scenario.factors_at(100)["E002"] == pytest.approx(1.0)
    assert scenario.factors_at(3000)["E002"] == pytest.approx(0.3)
    assert scenario.factors_at(5000)["E002"] == pytest.approx(1.0)
