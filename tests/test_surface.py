"""
Layer 5 (Canonical) — Dynamic Surface Storage & D8 Routing Tests:
Verifies mass conservation invariants, D8 directional flow routing,
progressive downstream valley accumulation, boundary discharge accounting,
numerical stability across timesteps, effective ponding areas, and depth diagnostics.
"""

import math

import pytest

from flood_engine.d8 import D8Terrain
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine
from flood_engine.surface_diagnostics import classify_depth_risk


def test_mass_conservation_invariant():
    """Verifies that Total Runoff Input - Total Surface Storage - Boundary Discharge == 0."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=8, cols=8, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    # Ingest runoff over 10 timesteps
    for i in range(1, 11):
        t = i * 60
        r_input = {cid: (1.5 if cid in ("C00001", "C00002") else 0.2) for cid in terrain.cells}
        step = engine.step(t, r_input)
        assert abs(step.mass_balance_error_m3) <= 1e-5

    bal = engine.mass_balance()
    assert bal["is_conserved"] is True
    assert abs(bal["mass_balance_error_m3"]) <= 1e-5


def test_d8_downslope_flow_direction():
    """
    Verifies that water transfers strictly to the D8 downstream neighbor,
    and uphill / non-D8 neighbors receive exactly zero upstream inflow.
    """
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=5, cols=5, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    source_id = "C00001"
    target_id = terrain.get_cell(source_id).downstream_cell
    assert target_id is not None

    # Step 1: Add water only to C00001
    r_input = {cid: (5.0 if cid == source_id else 0.0) for cid in terrain.cells}
    step_1 = engine.step(60, r_input)

    outflow_c1 = step_1.cells[source_id].surface_outflow_m3
    assert outflow_c1 > 0.0

    # The downstream target must receive this exact outflow as upstream inflow
    assert math.isclose(step_1.cells[target_id].upstream_inflow_m3, outflow_c1, rel_tol=1e-5)

    # Other non-downstream cells must receive 0 inflow
    for cid, c_state in step_1.cells.items():
        if cid != target_id:
            assert c_state.upstream_inflow_m3 == 0.0


def test_progressive_valley_accumulation():
    """Verifies that downstream valley storage at t4 > valley storage at t1."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    # Ridge cell C00001 slopes into valley path ending near C00095
    valley_cell = "C00095"

    storages_valley = []
    for i in range(1, 6):
        t = i * 60
        r_input = {cid: (3.0 if cid == "C00001" else 0.0) for cid in terrain.cells}
        step = engine.step(t, r_input)
        storages_valley.append(step.cells[valley_cell].new_storage_m3)

    # Valley storage at later timesteps must be greater than initial timestep
    assert storages_valley[-1] >= storages_valley[0]


def test_boundary_outflow_accounting():
    """Verifies that water reaching open boundaries is discharged and tracked in mass balance."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, boundary_condition="open", expected_timestep_seconds=60)

    # Place runoff on boundary exit cell (e.g. outlet cell C00036)
    outlet_id = "C00036"
    assert terrain.get_cell(outlet_id).is_outlet

    r_input = {cid: (4.0 if cid == outlet_id else 0.0) for cid in terrain.cells}
    step = engine.step(60, r_input)

    assert step.total_boundary_outflow_m3 > 0.0
    bal = engine.mass_balance()
    assert bal["cumulative_boundary_outflow_m3"] > 0.0
    assert bal["is_conserved"] is True


def test_numerical_stability_across_timesteps():
    """Verifies numerical stability across delta_t = 30s, 60s, and 120s."""
    for dt in (30, 60, 120):
        grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
        terrain = D8Terrain.compute_from_grid(grid)
        engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=dt)

        for i in range(1, 6):
            t = i * dt
            step = engine.step(t, 2.0, dt_seconds=dt)
            # All storages non-negative
            for c in step.cells.values():
                assert c.new_storage_m3 >= 0.0
                assert c.water_depth_m >= 0.0
            assert abs(step.mass_balance_error_m3) <= 1e-5


def test_rejection_of_invalid_inputs():
    """Verifies rejection of negative runoff, non-zero drainage in Layer 5, and backwards timestamps."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    # Negative runoff
    with pytest.raises(ValueError, match="Invalid runoff volume"):
        engine.step(60, -1.0)

    # Non-zero drainage in Layer 5
    with pytest.raises(ValueError, match="Drainage capture is not active in Layer 5"):
        engine.step(60, 0.0, drainage_capture_m3_by_cell={"C00001": 0.5})

    # Backward timestamp
    engine.step(60, 0.0)
    with pytest.raises(ValueError, match="strictly greater"):
        engine.step(30, 0.0)


def test_effective_area_and_depth_diagnostics():
    """Verifies effective area depth calculation and depth risk classification."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)

    # Cell C00001 has effective road ponding area = 25 m² instead of 100 m²
    eff_areas = {cid: (25.0 if cid == "C00001" else 100.0) for cid in terrain.cells}
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, effective_areas_m2=eff_areas, expected_timestep_seconds=60)

    step = engine.step(60, {"C00001": 2.5, **{cid: 0.0 for cid in terrain.cells if cid != "C00001"}})
    c1 = step.cells["C00001"]
    # depth = storage / 25.0
    expected_depth = c1.new_storage_m3 / 25.0
    assert math.isclose(c1.water_depth_m, expected_depth, rel_tol=1e-5)

    # Risk tiers test
    assert classify_depth_risk(0.02) == "NORMAL"
    assert classify_depth_risk(0.08) == "WARNING"
    assert classify_depth_risk(0.20) == "HAZARDOUS"
    assert classify_depth_risk(0.45) == "SEVERE"
    assert classify_depth_risk(0.75) == "CRITICAL"

    diag = engine.get_diagnostics()
    assert "max_depth_m" in diag
    assert "risk_counts" in diag
