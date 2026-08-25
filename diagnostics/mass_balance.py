"""
Layer 22 — Hydrological Mass Conservation Diagnostic & Water Ledger:
Verifies zero-loss mass balance: Input Runoff = Storage Change + Drainage + Boundary Outflow + Residual.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from flood_engine.snapshot import MassBalanceSnapshot


@dataclass
class WaterLedger:
    runoff_input_m3: float = 0.0
    previous_storage_m3: float = 0.0
    current_storage_m3: float = 0.0
    drainage_m3: float = 0.0
    boundary_outflow_m3: float = 0.0


def evaluate_timestep_balance(
    runoff_input_m3: float,
    previous_storage_m3: float,
    current_storage_m3: float,
    drainage_m3: float,
    boundary_outflow_m3: float,
    absolute_tolerance_m3: float = 5.0,
    relative_tolerance: float = 0.005,
    epsilon: float = 1e-6,
) -> MassBalanceSnapshot:
    """
    Computes per-timestep mass balance residual:
    E = I - (S_current - S_prev) - D - B
    Relative error = |E| / max(I, epsilon)
    """
    delta_s = current_storage_m3 - previous_storage_m3
    residual = runoff_input_m3 - delta_s - drainage_m3 - boundary_outflow_m3
    denom = max(runoff_input_m3, previous_storage_m3, epsilon)
    rel_err = abs(residual) / denom

    is_pass = (abs(residual) <= absolute_tolerance_m3) or (rel_err <= relative_tolerance)
    status_str = "PASS" if is_pass else "FAIL"

    return MassBalanceSnapshot(
        runoff_input_m3=runoff_input_m3,
        previous_storage_m3=previous_storage_m3,
        current_storage_m3=current_storage_m3,
        drainage_m3=drainage_m3,
        boundary_outflow_m3=boundary_outflow_m3,
        balance_error_m3=residual,
        relative_error=rel_err,
        status=status_str,
    )


class MassBalanceDiagnostic:
    def __init__(
        self,
        absolute_tolerance_m3: float = 5.0,
        relative_tolerance: float = 0.005,
    ):
        self.abs_tol = float(absolute_tolerance_m3)
        self.rel_tol = float(relative_tolerance)
        self.history: List[MassBalanceSnapshot] = []

    def reset(self) -> None:
        self.history.clear()

    def record_step(
        self,
        runoff_input_m3: float,
        previous_storage_m3: float,
        current_storage_m3: float,
        drainage_m3: float,
        boundary_outflow_m3: float,
    ) -> MassBalanceSnapshot:
        mb = evaluate_timestep_balance(
            runoff_input_m3=runoff_input_m3,
            previous_storage_m3=previous_storage_m3,
            current_storage_m3=current_storage_m3,
            drainage_m3=drainage_m3,
            boundary_outflow_m3=boundary_outflow_m3,
            absolute_tolerance_m3=self.abs_tol,
            relative_tolerance=self.rel_tol,
        )
        self.history.append(mb)
        return mb

    def evaluate_simulation_summary(self) -> Dict[str, Any]:
        if not self.history:
            return {"status": "NO_DATA", "steps": 0}

        max_err = max(abs(h.balance_error_m3) for h in self.history)
        max_rel_err = max(h.relative_error for h in self.history)
        all_passed = all(h.status == "PASS" for h in self.history)

        total_runoff = sum(h.runoff_input_m3 for h in self.history)
        total_drainage = sum(h.drainage_m3 for h in self.history)
        total_boundary = sum(h.boundary_outflow_m3 for h in self.history)
        final_storage = self.history[-1].current_storage_m3
        cum_residual = total_runoff - final_storage - total_drainage - total_boundary

        return {
            "status": "PASS" if all_passed else "FAIL",
            "steps_count": len(self.history),
            "max_balance_error_m3": round(max_err, 6),
            "max_relative_error": round(max_rel_err, 6),
            "cumulative_runoff_m3": round(total_runoff, 4),
            "final_storage_m3": round(final_storage, 4),
            "cumulative_drainage_m3": round(total_drainage, 4),
            "cumulative_boundary_m3": round(total_boundary, 4),
            "cumulative_residual_m3": round(cum_residual, 6),
        }
