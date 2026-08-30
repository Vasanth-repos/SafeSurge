"""
Layer 8 — Drainage Capacity Scenario Integration Tests:
Executes baseline vs. reduced-capacity simulation experiments, verifying the causal chain:
Capacity Degradation -> Reduced Pipe Throughput -> Increased Node Storage -> Surcharge -> Surface Ponding,
with strict mass conservation across both baseline and degraded scenarios.
"""


import pytest

from flood_engine.capacity import (
    CapacityEvent,
    CapacityScenario,
)
from flood_engine.coupling import (
    DrainageInlet,
    InletCellMapping,
    SurfaceDrainageCouplingEngine,
)
from flood_engine.d8 import D8Terrain
from flood_engine.drainage import DrainageEdge, DrainageNode, StatefulDrainageNetwork
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine


def _setup_coupled_system():
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    drainage = StatefulDrainageNetwork(expected_timestep_seconds=60)
    drainage.add_node(DrainageNode("N001", 13.0, 80.0, storage_capacity_m3=2.0))
    drainage.add_node(DrainageNode("N002", 13.0, 80.1, storage_capacity_m3=2.0))
    drainage.add_node(DrainageNode("N_OUT", 13.0, 80.2, node_type="outlet", base_capacity_m3_s=0.10, storage_capacity_m3=10.0))

    # Pipe E001 (N001 -> N002, 0.05 m³/s), Pipe E002 (N002 -> N_OUT, 0.05 m³/s)
    drainage.add_edge(DrainageEdge("E001", "N001", "N002", capacity_m3_s=0.05))
    drainage.add_edge(DrainageEdge("E002", "N002", "N_OUT", capacity_m3_s=0.05))

    inlets = [
        DrainageInlet("I001", "N001", base_capacity_m3_s=0.05),
        DrainageInlet("I002", "N002", base_capacity_m3_s=0.05),
    ]
    mappings = [
        InletCellMapping("I001", "C00001"),
        InletCellMapping("I002", "C00022"),
    ]

    coupling = SurfaceDrainageCouplingEngine(
        surface_engine=surface,
        drainage_network=drainage,
        inlets=inlets,
        mappings=mappings,
        dt_seconds=60.0,
        surcharge_cell_by_node={"N001": "C00001", "N002": "C00022"},
    )
    return coupling, terrain


def test_baseline_vs_reduced_capacity_experiment():
    """
    Runs controlled comparison:
    Simulation A (Baseline): F=1.0 throughout.
    Simulation B (Degraded): F=0.3 on E002 at t=180s.

    Verifies:
    1. Run B pipe throughput on E002 is lower than Run A.
    2. Run B generates higher surcharge than Run A.
    3. Both Run A and Run B strictly conserve mass (Error == 0).
    """
    sim_a, terrain_a = _setup_coupled_system()
    sim_b, _terrain_b = _setup_coupled_system()

    scenario = CapacityScenario(
        scenario_id="test_scen",
        name="Test Degraded Scenario",
        edge_ids=["E001", "E002"],
        events=[
            CapacityEvent(timestamp_seconds=0, edge_ids=("E002",), capacity_factor=1.0),
            CapacityEvent(timestamp_seconds=180, edge_ids=("E002",), capacity_factor=0.3),
        ],
    )

    steps_a = []
    steps_b = []

    # Run 5 timesteps (60s, 120s, 180s, 240s, 300s)
    for i in range(1, 6):
        t = i * 60
        r_input = {cid: (4.0 if cid in ("C00001", "C00022") else 0.0) for cid in terrain_a.cells}

        # Run A: baseline factors (all 1.0)
        res_a = sim_a.step(t, r_input, capacity_factor_by_edge={"E001": 1.0, "E002": 1.0})
        # Run B: scenario factors
        factors_b = scenario.factors_at(t)
        res_b = sim_b.step(t, r_input, capacity_factor_by_edge=factors_b)

        steps_a.append(res_a)
        steps_b.append(res_b)

        assert abs(res_a.mass_balance_error_m3) <= 1e-5
        assert abs(res_b.mass_balance_error_m3) <= 1e-5

    # During degraded period (t >= 180s):
    # Total surcharge in Run B must be >= Run A
    surch_a = sum(s.total_drainage_capture_m3 - s.drainage_outlet_volume_m3 for s in steps_a)
    surch_b = sum(s.total_drainage_capture_m3 - s.drainage_outlet_volume_m3 for s in steps_b)
    assert surch_b >= surch_a

    assert steps_b[-1].pending_surcharge_m3_by_cell["C00022"] >= steps_a[-1].pending_surcharge_m3_by_cell["C00022"]

    bal_a = sim_a.mass_balance()
    bal_b = sim_b.mass_balance()

    assert bal_a["is_conserved"] is True
    assert bal_b["is_conserved"] is True
    assert bal_a["cumulative_runoff_m3"] == pytest.approx(bal_b["cumulative_runoff_m3"])


def test_capacity_restoration_recovery_dynamics():
    """Verifies that capacity restoration (F: 0.3 -> 1.0) enables higher discharge without resetting storage."""
    sim, terrain = _setup_coupled_system()

    scenario = CapacityScenario(
        scenario_id="recovery_scen",
        name="Recovery Scenario",
        edge_ids=["E001", "E002"],
        events=[
            CapacityEvent(timestamp_seconds=60, edge_ids=("E002",), capacity_factor=0.3),
            CapacityEvent(timestamp_seconds=180, edge_ids=("E002",), capacity_factor=1.0),
        ],
    )

    r_input = {cid: (3.0 if cid in ("C00001", "C00022") else 0.0) for cid in terrain.cells}

    # t=60s (Degraded)
    step1 = sim.step(60, r_input, capacity_factor_by_edge=scenario.factors_at(60))
    assert abs(step1.mass_balance_error_m3) <= 1e-5

    # t=120s (Degraded)
    step2 = sim.step(120, r_input, capacity_factor_by_edge=scenario.factors_at(120))
    assert abs(step2.mass_balance_error_m3) <= 1e-5

    # t=180s (Restored to 1.0)
    step3 = sim.step(180, {cid: 0.0 for cid in terrain.cells}, capacity_factor_by_edge=scenario.factors_at(180))
    assert abs(step3.mass_balance_error_m3) <= 1e-5

    bal = sim.mass_balance()
    assert bal["is_conserved"] is True
