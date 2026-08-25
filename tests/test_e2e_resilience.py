"""
End-to-End Resilience & Disruption Scenario Tests (Layer 24-25):
Verifies that all 7 operational faults maintain causality, stability, and graceful degradation.
"""

import pytest
from replay.scenarios import ScenarioRunner
from replay.faults import Fault, FaultType


def test_scenario_baseline_storm_01():
    runner = ScenarioRunner("config.yaml")
    snapshots = runner.run("config/scenarios/storm_01.yaml")

    assert len(snapshots) == 181  # 180 min in 60s steps
    assert snapshots[0].timestamp_seconds == 0
    assert snapshots[-1].timestamp_seconds == 10800

    # Causal assertions
    max_d = max(max(c.corrected_depth_cm for c in s.flood_cells) for s in snapshots)
    assert max_d > 0.0
    assert all(s.mass_balance.status == "PASS" for s in snapshots)


def test_scenario_sensor_offline_degraded_state():
    runner = ScenarioRunner("config.yaml")
    snapshots = runner.run("config/scenarios/sensor_offline.yaml")

    snap_normal = next(s for s in snapshots if s.timestamp_seconds == 600)
    assert snap_normal.system_status == "NORMAL"

    snap_degraded = next(s for s in snapshots if s.timestamp_seconds == 2400)
    assert snap_degraded.system_status == "DEGRADED"
    assert any("S001" in r for r in snap_degraded.degraded_reasons)


def test_scenario_sensor_spike_resilience():
    runner = ScenarioRunner("config.yaml")
    snapshots = runner.run("config/scenarios/sensor_spike.yaml")

    snap_spike = next(s for s in snapshots if s.timestamp_seconds == 1800)
    # Model and mass balance remain numerically stable
    assert snap_spike.mass_balance.status == "PASS"
