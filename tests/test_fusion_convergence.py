"""
Scenario 3: Sensor Fusion Convergence Validation
Injects a fixed synthetic offset/bias and asserts corrected prediction
converges exponentially toward observed ground truth over N timesteps.
"""

import pytest
from backend.services.simulation_service import SimulationService


def test_fusion_bias_convergence():
    sim = SimulationService()
    sim.reset()

    sensor_id = 1
    cell_id = sim.sensors[sensor_id].cell_id
    observed_fixed_level = 18.0  # Constant observation

    initial_model_depth = sim.cells[cell_id].depth_cm  # 0.0 cm
    initial_error = abs(observed_fixed_level - initial_model_depth)

    # Run for 10 timesteps with constant observed telemetry
    for _ in range(10):
        sim.step(
            rainfall_input=0.0,
            sensor_readings={sensor_id: {"water_level_cm": observed_fixed_level, "heartbeat": True}},
        )

    # After 10 steps of alpha=0.3 smoothing, fused depth should be very close to observed
    final_fused_depth = sim.fused_depths_cm[cell_id]
    final_error = abs(observed_fixed_level - final_fused_depth)

    # Convergence check: error must decrease significantly (> 90% reduction)
    assert final_error < initial_error * 0.1, (
        f"Fusion did not converge: initial error {initial_error}, final error {final_error}"
    )
    assert abs(final_fused_depth - observed_fixed_level) < 1.0
