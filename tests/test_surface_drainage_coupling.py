"""
Layer 7 — Surface ↔ Drainage Coupling Test Suite:
Verifies inlet capacity limits, blockage factors, multiple cell/inlet allocations,
deterministic single-deduction surface capture, 1-timestep delayed surcharge,
and strict system-wide mass conservation.
"""


import pytest

from flood_engine.coupling import (
    DrainageInlet,
    InletCellMapping,
    SurfaceDrainageCouplingEngine,
    allocate_cell_capture,
    allocate_inlet_capacity,
    calculate_capture_volume,
)
from flood_engine.d8 import D8Terrain
from flood_engine.drainage import DrainageEdge, DrainageNode, StatefulDrainageNetwork
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine


def test_capture_below_capacity():
    """Test 1: Available volume is less than capacity -> captures entire available volume."""
    assert calculate_capture_volume(
        available_surface_m3=2.0,
        capacity_m3_s=0.1,
        dt_seconds=60.0,
    ) == pytest.approx(2.0)


def test_capture_capacity_limit():
    """Test 2: Available volume exceeds capacity -> captures capacity limit."""
    assert calculate_capture_volume(
        available_surface_m3=10.0,
        capacity_m3_s=0.05,
        dt_seconds=60.0,
    ) == pytest.approx(3.0)


def test_zero_capacity_captures_nothing():
    """Test 3: Zero capacity -> captures 0."""
    assert calculate_capture_volume(
        available_surface_m3=10.0,
        capacity_m3_s=0.0,
        dt_seconds=60.0,
    ) == pytest.approx(0.0)


def test_effective_capacity_with_blockage():
    """Test 4: Blockage factor reduces effective inlet capacity."""
    inlet = DrainageInlet(
        inlet_id="I1",
        node_id="N1",
        base_capacity_m3_s=0.05,
        blockage_factor=0.4,
    )
    assert inlet.effective_capacity_m3_s == pytest.approx(0.02)


def test_multiple_cells_feeding_one_inlet():
    """Test 5: Multiple cells feeding one inlet do not exceed inlet volumetric capacity."""
    available = {"C1": 5.0, "C2": 5.0, "C3": 10.0}
    # Inlet capacity = 0.05 m³/s (3.0 m³ in 60s)
    alloc = allocate_inlet_capacity(
        available_by_cell=available,
        capacity_m3_s=0.05,
        dt_seconds=60.0,
    )
    total_capture = sum(alloc.values())
    assert total_capture == pytest.approx(3.0)
    assert alloc["C1"] == pytest.approx(0.75)
    assert alloc["C2"] == pytest.approx(0.75)
    assert alloc["C3"] == pytest.approx(1.50)


def test_multiple_inlets_feeding_one_cell():
    """Test 6: Multiple inlets on one cell do not exceed available cell water."""
    available = 4.0
    # Inlet 1 cap = 0.05 (3 m³), Inlet 2 cap = 0.05 (3 m³) -> Total cap 6 m³ > available 4 m³
    inlet_caps = {"I1": 0.05, "I2": 0.05}
    alloc = allocate_cell_capture(
        available_m3=available,
        inlet_capacities_m3_s=inlet_caps,
        dt_seconds=60.0,
    )
    total_capture = sum(alloc.values())
    assert total_capture == pytest.approx(4.0)
    assert alloc["I1"] == pytest.approx(2.0)
    assert alloc["I2"] == pytest.approx(2.0)


def test_capture_removed_exactly_once():
    """Test 7: 10 m³ available, 3 m³ captured -> 7 m³ surface remaining, 3 m³ drainage inflow."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    drainage = StatefulDrainageNetwork(expected_timestep_seconds=60)
    drainage.add_node(DrainageNode("N001", 13.0, 80.0, storage_capacity_m3=20.0))
    drainage.add_node(DrainageNode("N_OUT", 13.0, 80.1, node_type="outlet", storage_capacity_m3=20.0))
    drainage.add_edge(DrainageEdge("E001", "N001", "N_OUT", capacity_m3_s=0.10))

    inlets = [DrainageInlet("I001", "N001", base_capacity_m3_s=0.05)]
    mappings = [InletCellMapping("I001", "C00001")]

    coupling = SurfaceDrainageCouplingEngine(
        surface_engine=surface,
        drainage_network=drainage,
        inlets=inlets,
        mappings=mappings,
        dt_seconds=60.0,
    )

    runoff = {cid: (10.0 if cid == "C00001" else 0.0) for cid in terrain.cells.keys()}
    step = coupling.step(60, runoff)

    assert step.total_drainage_capture_m3 == pytest.approx(3.0)
    assert step.drainage_inflow_m3_by_node["N001"] == pytest.approx(3.0)
    assert step.mass_balance_error_m3 == pytest.approx(0.0, abs=1e-5)


def test_surcharge_is_delayed_and_no_instantaneous_loop():
    """
    Test 8 & 9: Surcharge generated at timestep t is delayed and becomes surface input only at t+1.
    No instantaneous feedback loop occurs during timestep t.
    """
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    drainage = StatefulDrainageNetwork(expected_timestep_seconds=60)
    # N001 has tiny storage capacity = 1.0 m³, and blocked downstream pipe (0 capacity)
    drainage.add_node(DrainageNode("N001", 13.0, 80.0, storage_capacity_m3=1.0))
    drainage.add_node(DrainageNode("N_OUT", 13.0, 80.1, node_type="outlet", storage_capacity_m3=10.0))
    drainage.add_edge(DrainageEdge("E001", "N001", "N_OUT", capacity_m3_s=0.0))  # Blocked

    inlets = [DrainageInlet("I001", "N001", base_capacity_m3_s=0.05)]  # Can capture 3.0 m³ in 60s
    mappings = [InletCellMapping("I001", "C00001")]

    coupling = SurfaceDrainageCouplingEngine(
        surface_engine=surface,
        drainage_network=drainage,
        inlets=inlets,
        mappings=mappings,
        dt_seconds=60.0,
        surcharge_cell_by_node={"N001": "C00001"},
    )

    # Step 1: t=60s. Ingest 10 m³ on C00001
    runoff_1 = {cid: (10.0 if cid == "C00001" else 0.0) for cid in terrain.cells.keys()}
    step_1 = coupling.step(60, runoff_1)

    # 3.0 m³ captured -> Node N001 stores 1.0 m³ max, remaining 2.0 m³ is surcharge
    assert step_1.drainage_surcharge_m3_by_node["N001"] == pytest.approx(2.0)
    # The 2.0 m³ surcharge is stored in pending surcharge for t=120, NOT added to surface storage yet
    assert step_1.pending_surcharge_m3_by_cell["C00001"] == pytest.approx(2.0)
    assert abs(step_1.mass_balance_error_m3) <= 1e-5

    # Step 2: t=120s with 0 runoff. The 2.0 m³ pending surcharge is now injected onto C00001
    runoff_2 = {cid: 0.0 for cid in terrain.cells.keys()}
    step_2 = coupling.step(120, runoff_2)

    # Pending surcharge has been consumed
    assert abs(step_2.mass_balance_error_m3) <= 1e-5


def test_full_system_mass_conservation():
    """Test 10: Multi-step storm satisfies system-wide mass conservation without water loss."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    drainage = StatefulDrainageNetwork.create_synthetic_demo_network()
    inlets = [
        DrainageInlet("I001", "N001", base_capacity_m3_s=0.05),
        DrainageInlet("I002", "N002", base_capacity_m3_s=0.03, blockage_factor=0.7),
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
    )

    # Simulate 5 storm timesteps
    for i in range(1, 6):
        t = i * 60
        r_input = {cid: (4.0 if cid in ("C00001", "C00022") else 0.5) for cid in terrain.cells.keys()}
        res = coupling.step(t, r_input)
        assert abs(res.mass_balance_error_m3) <= 1e-5

    bal = coupling.mass_balance()
    assert bal["is_conserved"] is True
    assert abs(bal["mass_balance_error_m3"]) <= 1e-5


def test_pipe_bottleneck_and_surcharge_return_scenario():
    """
    Test 11 (Bottleneck Scenario):
    - 10 m³ surface water
    - Inlet capacity = 0.05 m³/s (3.0 m³ capture)
    - Pipe capacity = 0.02 m³/s (1.2 m³ pipe transmission)
    - Node storage capacity = 1.0 m³
    - Surcharge = 3.0 - 1.2 - 1.0 = 0.8 m³
    - Next timestep: 0.8 m³ queued to mapped surface cell.
    """
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    drainage = StatefulDrainageNetwork(expected_timestep_seconds=60)
    drainage.add_node(DrainageNode("N001", 13.0, 80.0, storage_capacity_m3=1.0))
    drainage.add_node(DrainageNode("N002", 13.0, 80.1, node_type="outlet", storage_capacity_m3=10.0))
    drainage.add_edge(DrainageEdge("E001", "N001", "N002", capacity_m3_s=0.02))  # 1.2 m³ in 60s

    inlets = [DrainageInlet("I001", "N001", base_capacity_m3_s=0.05)]
    mappings = [InletCellMapping("I001", "C00001")]

    coupling = SurfaceDrainageCouplingEngine(
        surface_engine=surface,
        drainage_network=drainage,
        inlets=inlets,
        mappings=mappings,
        dt_seconds=60.0,
        surcharge_cell_by_node={"N001": "C00001"},
    )

    runoff = {cid: (10.0 if cid == "C00001" else 0.0) for cid in terrain.cells.keys()}
    step = coupling.step(60, runoff)

    assert step.total_drainage_capture_m3 == pytest.approx(3.0)
    assert step.drainage_storage_m3_by_node["N001"] == pytest.approx(1.0)
    assert step.drainage_surcharge_m3_by_node["N001"] == pytest.approx(0.8)
    assert step.pending_surcharge_m3_by_cell["C00001"] == pytest.approx(0.8)
    assert abs(step.mass_balance_error_m3) <= 1e-5
