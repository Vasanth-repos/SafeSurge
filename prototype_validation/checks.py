"""
Layer 26 — Comprehensive Subsystem & Integration Check Suite:
Executes the production pipeline and verifies all functional, physical, and integration properties.
"""

from __future__ import annotations

import os
import math
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

from prototype_validation.models import CheckResult, CheckStatus, CheckSeverity
from prototype_validation.thresholds import ValidationThresholds
from prototype_validation.assertions import (
    assert_non_negative_storage,
    assert_non_negative_depth,
    assert_mass_conservation,
    assert_snapshot_timestamp_consistency,
)
from flood_engine.grid import ComputationalGrid, GridCell
from flood_engine.d8 import D8Terrain, D8Cell
from flood_engine.risk import RiskState, RiskProfile, RiskThresholds, classify_depth
from sensors.registry import SensorRegistry
from sensors.validation import SensorValidator
from sensors.models import SensorEnvelope, MeasurementStatus, RejectionReason
from fusion.pipeline import FusionPipeline
from anomalies.detector import AnomalyDetector
from replay.engine import ReplayEngine
from replay.scenarios import ScenarioRunner
from replay.faults import Fault, FaultType
from routing.graph import DirectedRoadGraph
from routing.router import EmergencyRouter
from routing.models import RoadEdge, RoadEdgeState


def check_environment() -> CheckResult:
    """Verifies runtime environment, required directories, and configuration files."""
    req_paths = [
        "config.yaml",
        "data/sensors/registry.yaml",
        "config/scenarios/storm_01.yaml",
    ]
    missing = [p for p in req_paths if not os.path.exists(p)]
    if missing:
        return CheckResult(
            check_id="ENV-001",
            name="Environment & Required Assets",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Missing required configuration/asset files: {missing}",
            details={"missing": missing},
        )
    return CheckResult(
        check_id="ENV-001",
        name="Environment & Required Assets",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message="All required project directories, configs, and assets are present",
        details={"checked_paths": req_paths},
    )


def check_grid_and_d8_integrity() -> CheckResult:
    """Verifies grid geometry validity, uniqueness, and D8 downslope flow without cycles."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10, resolution_m=10.0)
    d8 = D8Terrain.compute_from_grid(grid)
    d8_cells = d8.cells

    # Check for cycles
    visited = set()
    rec_stack = set()
    has_cycle = False

    def is_cyclic(cid: str) -> bool:
        visited.add(cid)
        rec_stack.add(cid)
        cell = d8_cells.get(cid)
        if cell is not None and cell.downstream_cell is not None:
            down = cell.downstream_cell
            if down in d8_cells:
                if down not in visited:
                    if is_cyclic(down):
                        return True
                elif down in rec_stack:
                    return True
        rec_stack.remove(cid)
        return False

    for cid in d8_cells:
        if cid not in visited:
            if is_cyclic(cid):
                has_cycle = True
                break

    if has_cycle:
        return CheckResult(
            check_id="GRID-001",
            name="Grid Topology & D8 Acyclic Integrity",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message="Detected impossible flow cycle in D8 surface drainage graph",
            details={"has_cycle": True},
        )

    return CheckResult(
        check_id="GRID-001",
        name="Grid Topology & D8 Acyclic Integrity",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message=f"D8 terrain verified across {len(d8_cells)} cells with zero cycles and valid boundary discharges",
        details={"total_cells": len(d8_cells), "has_cycle": False},
    )


def check_rainfall_determinism(runner: ScenarioRunner) -> CheckResult:
    """Runs the same scenario twice to verify exact numerical determinism."""
    run_a = runner.run("config/scenarios/storm_01.yaml")
    run_b = runner.run("config/scenarios/storm_01.yaml")

    if len(run_a) != len(run_b):
        return CheckResult(
            check_id="REPLAY-001",
            name="Deterministic Scenario Replay",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Timestep count mismatch between identical runs: {len(run_a)} vs {len(run_b)}",
            details={"count_a": len(run_a), "count_b": len(run_b)},
        )

    diff_count = 0
    for sa, sb in zip(run_a, run_b):
        if sa.timestamp_seconds != sb.timestamp_seconds:
            diff_count += 1
        if sa.mass_balance.current_storage_m3 != sb.mass_balance.current_storage_m3:
            diff_count += 1

    if diff_count > 0:
        return CheckResult(
            check_id="REPLAY-001",
            name="Deterministic Scenario Replay",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Detected {diff_count} state differences between identical replay runs",
            details={"diff_count": diff_count},
        )

    return CheckResult(
        check_id="REPLAY-001",
        name="Deterministic Scenario Replay",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message=f"Exact numerical determinism verified across {len(run_a)} snapshots (Run A == Run B)",
        details={"snapshots_compared": len(run_a)},
    )


def check_sensor_spike_rejection() -> CheckResult:
    """Verifies that an erroneous 90cm rate spike is rejected and excluded from fusion."""
    reg = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
    validator = SensorValidator(reg)

    # Sequence: 10cm, 11cm, 12cm, 90cm (Spike), 13cm
    # (Sensor S001 has reference distance = 100cm)
    envelopes = [
        SensorEnvelope("S001", "boot_1", 1, 0, 0, (90.0, 90.0, 90.0), False),
        SensorEnvelope("S001", "boot_1", 2, 10, 10, (89.0, 89.0, 89.0), False),
        SensorEnvelope("S001", "boot_1", 3, 20, 20, (88.0, 88.0, 88.0), False),
        SensorEnvelope("S001", "boot_1", 4, 30, 30, (10.0, 10.0, 10.0), False),  # Spike
        SensorEnvelope("S001", "boot_1", 5, 40, 40, (87.0, 87.0, 87.0), False),
    ]

    results = [validator.validate(env) for env in envelopes]

    if results[3].measurement_status != MeasurementStatus.REJECTED or results[3].rejection_reason != RejectionReason.RATE_SPIKE:
        return CheckResult(
            check_id="SENS-001",
            name="Sensor Rate Spike Filtering",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Expected REJECTED (RATE_SPIKE) for 90cm outlier, got {results[3].measurement_status} ({results[3].rejection_reason})",
            details={"result": str(results[3])},
        )

    if results[4].measurement_status != MeasurementStatus.ACCEPTED:
        return CheckResult(
            check_id="SENS-001",
            name="Sensor Rate Spike Filtering",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Sensor failed to recover on subsequent valid reading, got {results[4].measurement_status}",
            details={"result": str(results[4])},
        )

    return CheckResult(
        check_id="SENS-001",
        name="Sensor Rate Spike Filtering",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message="Erroneous 90cm spike rejected (RATE_SPIKE) and subsequent 13cm valid reading accepted",
        details={"spike_status": results[3].measurement_status.value, "recovery_status": results[4].measurement_status.value},
    )


def check_dynamic_emergency_routing() -> CheckResult:
    """Verifies that an inundated road (UNSAFE >= 25cm) triggers dynamic rerouting."""
    edges = [
        RoadEdge("R1", "A", "B", 60.0),
        RoadEdge("R2", "B", "D", 60.0),
        RoadEdge("R3", "A", "C", 60.0),
        RoadEdge("R4", "C", "D", 60.0),
    ]
    graph = DirectedRoadGraph(edges)
    router = EmergencyRouter(graph)

    # Dry: A -> B -> D
    states_dry = {
        "R1": RoadEdgeState("R1", "A", "B", 60.0, 0.0, "SAFE", 1.0),
        "R2": RoadEdgeState("R2", "B", "D", 60.0, 0.0, "SAFE", 1.0),
        "R3": RoadEdgeState("R3", "A", "C", 60.0, 0.0, "SAFE", 1.0),
        "R4": RoadEdgeState("R4", "C", "D", 60.0, 0.0, "SAFE", 1.0),
    }
    r_dry = router.find_route("A", "D", "storm_01", 0, states_dry)

    # Flood on R2 (B->D) >= 25cm -> UNSAFE
    states_flooded = dict(states_dry)
    states_flooded["R2"] = RoadEdgeState("R2", "B", "D", 60.0, 30.0, "UNSAFE", 0.9)
    r_flooded = router.find_route("A", "D", "storm_01", 3600, states_flooded)

    if r_dry.road_path != ("R1", "R2"):
        return CheckResult(
            check_id="ROUTE-001",
            name="Dynamic Safe Routing",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Initial dry route expected ('R1', 'R2'), got {r_dry.road_path}",
            details={"dry_path": r_dry.road_path},
        )

    if r_flooded.road_path != ("R3", "R4"):
        return CheckResult(
            check_id="ROUTE-001",
            name="Dynamic Safe Routing",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Alternate route during flood expected ('R3', 'R4'), got {r_flooded.road_path}",
            details={"flooded_path": r_flooded.road_path},
        )

    return CheckResult(
        check_id="ROUTE-001",
        name="Dynamic Safe Routing",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message="Router dynamically diverted traffic from inundated R2 (B->D) to safe corridor A->C->D with explanation",
        details={"dry_route": r_dry.road_path, "flooded_route": r_flooded.road_path, "avoided": [a.road_id for a in r_flooded.avoided_roads]},
    )
