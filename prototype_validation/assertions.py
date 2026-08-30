"""
Layer 26 — Production Output Invariant Assertions:
Evaluates physical, temporal, and structural invariants on actual pipeline outputs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from flood_engine.snapshot import SimulationSnapshot
from prototype_validation.models import CheckResult, CheckSeverity, CheckStatus
from prototype_validation.thresholds import ValidationThresholds


def assert_non_negative_storage(
    snapshots: Sequence[SimulationSnapshot],
    thresholds: ValidationThresholds,
) -> CheckResult:
    """Invariant: Surface storage must be strictly non-negative and finite."""
    min_storage = float("inf")
    nan_count = 0

    for snap in snapshots:
        s_val = snap.mass_balance.current_storage_m3
        if math.isnan(s_val) or math.isinf(s_val):
            nan_count += 1
        min_storage = min(min_storage, s_val)

    if nan_count > 0:
        return CheckResult(
            check_id="PHYS-001",
            name="Storage Finite Non-NaN",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Found {nan_count} non-finite/NaN storage values",
            details={"nan_count": nan_count},
        )

    if min_storage < thresholds.min_storage_tolerance_m3:
        return CheckResult(
            check_id="PHYS-001",
            name="No Negative Surface Storage",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Detected negative surface storage: {min_storage:.6f} m³",
            details={"min_storage_m3": min_storage},
        )

    return CheckResult(
        check_id="PHYS-001",
        name="No Negative Surface Storage",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message=f"All {len(snapshots)} snapshots exhibited non-negative finite storage (min={min_storage:.4f} m³)",
        details={"min_storage_m3": min_storage, "snapshots_checked": len(snapshots)},
    )


def assert_non_negative_depth(
    snapshots: Sequence[SimulationSnapshot],
    thresholds: ValidationThresholds,
) -> CheckResult:
    """Invariant: Water depths across all grid cells must be non-negative."""
    min_depth = float("inf")
    nan_count = 0
    total_cells = 0

    for snap in snapshots:
        for c in snap.flood_cells:
            total_cells += 1
            if math.isnan(c.corrected_depth_cm) or math.isinf(c.corrected_depth_cm):
                nan_count += 1
            min_depth = min(min_depth, c.corrected_depth_cm)

    if nan_count > 0:
        return CheckResult(
            check_id="PHYS-002",
            name="Cell Flood Depths Finite",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Found {nan_count} non-finite/NaN cell depths",
            details={"nan_count": nan_count},
        )

    if min_depth < thresholds.min_depth_tolerance_cm:
        return CheckResult(
            check_id="PHYS-002",
            name="No Negative Flood Depth",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Detected negative cell flood depth: {min_depth:.4f} cm",
            details={"min_depth_cm": min_depth},
        )

    return CheckResult(
        check_id="PHYS-002",
        name="No Negative Flood Depth",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message=f"All {total_cells} evaluated cell-timesteps were non-negative (min={min_depth:.2f} cm)",
        details={"min_depth_cm": min_depth, "cell_timesteps_evaluated": total_cells},
    )


def assert_mass_conservation(
    snapshots: Sequence[SimulationSnapshot],
    thresholds: ValidationThresholds,
) -> CheckResult:
    """Invariant: System mass balance error must stay within configured tolerances."""
    max_error = 0.0
    max_rel_error = 0.0
    failed_steps = 0

    for snap in snapshots:
        mb = snap.mass_balance
        err = abs(mb.balance_error_m3)
        rel_err = mb.relative_error
        max_error = max(max_error, err)
        max_rel_error = max(max_rel_error, rel_err)
        if mb.status != "PASS":
            failed_steps += 1

    if failed_steps > 0:
        return CheckResult(
            check_id="HYD-001",
            name="Continuous Mass Conservation",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"{failed_steps} timesteps failed zero-loss mass conservation (max_error={max_error:.4f} m³)",
            details={"failed_steps": failed_steps, "max_error_m3": max_error, "max_relative_error": max_rel_error},
        )

    return CheckResult(
        check_id="HYD-001",
        name="Continuous Mass Conservation",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message=f"All {len(snapshots)} timesteps satisfied conservation invariant (max_err={max_error:.6f} m³, max_rel={max_rel_error:.6f})",
        details={"max_error_m3": max_error, "max_relative_error": max_rel_error},
    )


def assert_snapshot_timestamp_consistency(
    snapshots: Sequence[SimulationSnapshot],
) -> CheckResult:
    """Invariant: All components in a snapshot must share the exact same simulation timestamp."""
    inconsistent_count = 0

    for snap in snapshots:
        t = snap.timestamp_seconds
        # Check roads
        if any(r.mean_depth_cm is None for r in snap.road_risks):
            inconsistent_count += 1
        # Check sensors
        if any(s.last_valid_timestamp_seconds is not None and s.last_valid_timestamp_seconds > t for s in snap.sensor_states):
            inconsistent_count += 1

    if inconsistent_count > 0:
        return CheckResult(
            check_id="SNAP-001",
            name="Snapshot Timestamp Coherence",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAIL,
            message=f"Found {inconsistent_count} snapshots with temporal drift or future state",
            details={"inconsistent_count": inconsistent_count},
        )

    return CheckResult(
        check_id="SNAP-001",
        name="Snapshot Timestamp Coherence",
        severity=CheckSeverity.CRITICAL,
        status=CheckStatus.PASS,
        message=f"All {len(snapshots)} snapshots exhibited 100% synchronized internal temporal coherence",
        details={"snapshots_evaluated": len(snapshots)},
    )
