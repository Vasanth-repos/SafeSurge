"""
Layer 26 — Master Prototype Validation Runner:
Executes the actual production flood pipeline, runs invariant assertions,
and generates deterministic PASS / WARN / FAIL validation reports.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional

from prototype_validation.models import (
    CheckResult,
    CheckStatus,
    CheckSeverity,
    ValidationReport,
)
from prototype_validation.thresholds import ValidationThresholds
from prototype_validation.assertions import (
    assert_non_negative_storage,
    assert_non_negative_depth,
    assert_mass_conservation,
    assert_snapshot_timestamp_consistency,
)
from prototype_validation.checks import (
    check_environment,
    check_grid_and_d8_integrity,
    check_rainfall_determinism,
    check_sensor_spike_rejection,
    check_dynamic_emergency_routing,
)
from prototype_validation.scenarios import get_fault_suite, get_recovery_suite
from replay.scenarios import ScenarioRunner
from replay.engine import ReplayEngine
from backend.services.snapshot_service import SnapshotService


class PrototypeValidationRunner:
    def __init__(
        self,
        config_path: str = "config.yaml",
        thresholds: Optional[ValidationThresholds] = None,
    ):
        self.config_path = config_path
        self.thresholds = thresholds or ValidationThresholds()
        self.runner = ScenarioRunner(config_path=config_path)

    def validate_normal_scenario(
        self,
        scenario_yaml_path: str = "config/scenarios/e2e_validation.yaml",
    ) -> ValidationReport:
        """Executes full end-to-end master normal validation."""
        started_at = datetime.utcnow().isoformat() + "Z"
        checks: List[CheckResult] = []

        # 1. Environment & Configuration Check
        checks.append(check_environment())

        # 2. Grid & D8 Topology Check
        checks.append(check_grid_and_d8_integrity())

        # 3. Production Pipeline Execution
        snapshots = self.runner.run(scenario_yaml_path)

        # 4. Invariant Assertions on Pipeline Output
        checks.append(assert_non_negative_storage(snapshots, self.thresholds))
        checks.append(assert_non_negative_depth(snapshots, self.thresholds))
        checks.append(assert_mass_conservation(snapshots, self.thresholds))
        checks.append(assert_snapshot_timestamp_consistency(snapshots))

        # 5. Determinism Check
        checks.append(check_rainfall_determinism(self.runner))

        # 6. Sensor Spike Rejection Check
        checks.append(check_sensor_spike_rejection())

        # 7. Dynamic Safe Routing Check
        checks.append(check_dynamic_emergency_routing())

        # 8. API & Dashboard Contract Compatibility
        snap_service = SnapshotService(config_path=self.config_path)
        dash_state = snap_service.get_dashboard_state(lead_time_minutes=30)
        if dash_state.get("system_status") is not None and "cells" in dash_state:
            checks.append(
                CheckResult(
                    check_id="API-001",
                    name="API & GIS Dashboard Contract Compatibility",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.PASS,
                    message="Dashboard state parsed validly with coherent snapshot metadata and geometry",
                    details={"cell_count": len(dash_state.get("cells", []))},
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="API-001",
                    name="API & GIS Dashboard Contract Compatibility",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.FAIL,
                    message="Dashboard state missing required snapshot metadata or cell geometry",
                    details={"dash_state": dash_state},
                )
            )

        completed_at = datetime.utcnow().isoformat() + "Z"

        # Determine Overall Status: Any critical FAIL -> FAIL; else any WARN -> WARN; else PASS
        overall_status = CheckStatus.PASS
        if any(c.status == CheckStatus.FAIL for c in checks):
            overall_status = CheckStatus.FAIL
        elif any(c.status == CheckStatus.WARN for c in checks):
            overall_status = CheckStatus.WARN

        summary = {
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c.status == CheckStatus.PASS),
            "warning_checks": sum(1 for c in checks if c.status == CheckStatus.WARN),
            "failed_checks": sum(1 for c in checks if c.status == CheckStatus.FAIL),
        }

        return ValidationReport(
            validation_id=f"val_{int(time.time())}",
            scenario_id="e2e_validation_01",
            status=overall_status,
            checks=tuple(checks),
            started_at=started_at,
            completed_at=completed_at,
            simulation_id="e2e_validation_01",
            timestep_count=len(snapshots),
            summary=summary,
        )

    def validate_fault_suite(self) -> List[CheckResult]:
        """Executes all 7 canonical fault scenarios and verifies stability."""
        engine = ReplayEngine(config_path=self.config_path)
        fault_checks: List[CheckResult] = []

        for name, faults in get_fault_suite():
            snaps = engine.run_scenario(
                scenario_name=name,
                total_minutes=90,
                timestep_seconds=60,
                faults=faults,
            )
            # Invariant: storage and mass balance must remain non-negative and valid
            all_mb_pass = all(s.mass_balance.status == "PASS" for s in snaps)
            min_s = min(s.mass_balance.current_storage_m3 for s in snaps)

            if all_mb_pass and min_s >= 0.0:
                fault_checks.append(
                    CheckResult(
                        check_id=f"FAULT-{name}",
                        name=f"Fault Resilience: {name}",
                        severity=CheckSeverity.CRITICAL,
                        status=CheckStatus.PASS,
                        message=f"Simulation remained stable under {name} with zero negative storage",
                        details={"min_storage_m3": min_s, "timesteps": len(snaps)},
                    )
                )
            else:
                fault_checks.append(
                    CheckResult(
                        check_id=f"FAULT-{name}",
                        name=f"Fault Resilience: {name}",
                        severity=CheckSeverity.CRITICAL,
                        status=CheckStatus.FAIL,
                        message=f"Simulation failed invariant during {name}",
                        details={"min_storage_m3": min_s, "mb_pass": all_mb_pass},
                    )
                )

        return fault_checks

    def validate_recovery_suite(self) -> List[CheckResult]:
        """Executes recovery scenarios where faults cease and verifies clean restoration."""
        engine = ReplayEngine(config_path=self.config_path)
        recovery_checks: List[CheckResult] = []

        for name, faults in get_recovery_suite():
            snaps = engine.run_scenario(
                scenario_name=name,
                total_minutes=90,
                timestep_seconds=60,
                faults=faults,
            )
            # Inspect state after recovery window (t > 3600s)
            post_fault_snaps = [s for s in snaps if s.timestamp_seconds > 3600]
            recovered_ok = all(s.system_status == "NORMAL" for s in post_fault_snaps)

            if recovered_ok and len(post_fault_snaps) > 0:
                recovery_checks.append(
                    CheckResult(
                        check_id=f"REC-{name}",
                        name=f"Fault Recovery: {name}",
                        severity=CheckSeverity.IMPORTANT,
                        status=CheckStatus.PASS,
                        message=f"Subsystem cleanly recovered to NORMAL state following {name}",
                        details={"post_fault_snapshots": len(post_fault_snaps)},
                    )
                )
            else:
                recovery_checks.append(
                    CheckResult(
                        check_id=f"REC-{name}",
                        name=f"Fault Recovery: {name}",
                        severity=CheckSeverity.IMPORTANT,
                        status=CheckStatus.FAIL,
                        message=f"Subsystem failed to restore NORMAL state after {name}",
                        details={"recovered_ok": recovered_ok},
                    )
                )

        return recovery_checks
