"""
Scenario 1: Mass Conservation Validation
Runs a replay storm and asserts |balance_error| <= tolerance at every single timestep.
"""

import pytest
from backend.services.simulation_service import SimulationService


def test_mass_conservation_during_storm():
    sim = SimulationService()
    sim.reset()

    # Step through a severe rainfall event with varying intensities
    rain_profile = [5.0, 15.0, 35.0, 60.0, 45.0, 20.0, 5.0, 0.0, 0.0]

    for step_idx, rain_rate_hr in enumerate(rain_profile):
        dt_s = 60.0
        rain_mm_step = (rain_rate_hr / 3600.0) * dt_s
        res = sim.step(rainfall_input=rain_mm_step, dt_seconds=dt_s)

        mb = res["mass_balance"]
        assert mb["status"] == "PASS", f"Mass balance failed at step {step_idx}: {mb}"
        assert abs(mb["balance_error_m3"]) <= sim.tolerance_m3, (
            f"Balance error {mb['balance_error_m3']} exceeds tolerance {sim.tolerance_m3}"
        )

        # Storage in all cells must never be negative
        for cid, cell in sim.cells.items():
            assert cell.storage_m3 >= 0.0, f"Cell {cid} has negative storage: {cell.storage_m3}"
            assert cell.depth_cm >= 0.0, f"Cell {cid} has negative depth: {cell.depth_cm}"
