"""
Tests for Layer 22 Mass Conservation Diagnostic & Water Ledger.
"""

import pytest
from diagnostics.mass_balance import (
    WaterLedger,
    evaluate_timestep_balance,
    MassBalanceDiagnostic,
)


def test_perfect_mass_balance():
    # Input = 100, delta_S = 60, Drainage = 30, Outflow = 10 -> Residual = 0
    mb = evaluate_timestep_balance(
        runoff_input_m3=100.0,
        previous_storage_m3=50.0,
        current_storage_m3=110.0,
        drainage_m3=30.0,
        boundary_outflow_m3=10.0,
    )
    assert mb.status == "PASS"
    assert mb.balance_error_m3 == 0.0
    assert mb.relative_error == 0.0


def test_mass_balance_diagnostic_tracker():
    diag = MassBalanceDiagnostic(absolute_tolerance_m3=5.0, relative_tolerance=0.005)
    diag.record_step(100.0, 0.0, 70.0, 20.0, 10.0)
    diag.record_step(50.0, 70.0, 90.0, 25.0, 5.0)

    summary = diag.evaluate_simulation_summary()
    assert summary["status"] == "PASS"
    assert summary["steps_count"] == 2
    assert summary["cumulative_runoff_m3"] == 150.0
