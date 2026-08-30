"""
Layer 26 — Validation Scenarios & Fault/Recovery Suites:
Defines standard test suites for master normal storm, fault injection, and recovery verification.
"""

from __future__ import annotations

from replay.faults import Fault, FaultType


def get_fault_suite() -> list[tuple[str, list[Fault]]]:
    """Returns the 7 canonical fault scenarios."""
    return [
        ("F1_sensor_offline", [
            Fault("F1", FaultType.SENSOR_OFFLINE, 1800, 3600, {"sensor_id": "S001"})
        ]),
        ("F2_sensor_spike", [
            Fault("F2", FaultType.SENSOR_SPIKE, 1800, 1860, {"sensor_id": "S001", "depth_cm": 90.0})
        ]),
        ("F3_reduced_drainage", [
            Fault("F3", FaultType.DRAINAGE_CAPACITY, 2700, 3600, {"edge_id": "E001", "capacity_factor": 0.3})
        ]),
        ("F4_extreme_rainfall", [
            Fault("F4", FaultType.RAINFALL_MULTIPLIER, 1800, 3600, {"multiplier": 2.5})
        ]),
        ("F5_rainfall_unavailable", [
            Fault("F5", FaultType.RAINFALL_UNAVAILABLE, 1800, 3600, {})
        ]),
        ("F6_no_sensor_coverage", [
            Fault("F6", FaultType.NO_SENSOR_COVERAGE, 1800, 5400, {})
        ]),
        ("F7_road_blockage", [
            Fault("F7", FaultType.ROAD_BLOCKAGE, 1800, 3600, {"road_id": "R002"})
        ]),
    ]


def get_recovery_suite() -> list[tuple[str, list[Fault]]]:
    """Returns recovery test suites where faults are deactivated after an operational window."""
    return [
        ("R1_sensor_recovery", [
            Fault("R1", FaultType.SENSOR_OFFLINE, 1800, 2400, {"sensor_id": "S001"})
        ]),
        ("R2_capacity_recovery", [
            Fault("R2", FaultType.DRAINAGE_CAPACITY, 2700, 3600, {"edge_id": "E001", "capacity_factor": 0.3})
        ]),
    ]
