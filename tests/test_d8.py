"""
Layer 2 — DEM + D8 Terrain Flow Analysis Tests:
Verifies D8 steepest descent, tie-breaking ordering, terminal states,
flow-path tracing, validation constraints, and export artifacts.
"""

import pytest
import math
import numpy as np
from pathlib import Path
from flood_engine.grid import ComputationalGrid
from flood_engine.d8 import D8Terrain, D8Cell, NEIGHBOR_ORDER


def test_d8_slope_and_direction_calculation():
    """
    Verifies that the centre cell selects southeast neighbour:
    30.0  29.5  29.0
    29.5  29.0  28.5
    29.0  28.5  28.0
    slope_SE = (29.0 - 28.0)/(10 * sqrt(2)) ≈ 0.0707
    or for 2m drop: slope = 2 / (10 * sqrt(2)) ≈ 0.1414
    """
    elev = np.array([
        [30.0, 29.5, 29.0],
        [29.5, 29.0, 28.5],
        [29.0, 28.5, 27.0],  # SE cell drops 2.0m -> slope = 2/(10*sqrt(2)) ≈ 0.1414
    ])
    lat = np.zeros((3, 3))
    lon = np.zeros((3, 3))

    grid = ComputationalGrid(
        elevation_m=elev,
        latitude=lat,
        longitude=lon,
        resolution_m=10.0,
    )

    terrain = D8Terrain.compute_from_grid(grid)
    center_cell = terrain.get_cell("C00005")  # (row 1, col 1)

    assert center_cell.direction == "SE"
    assert center_cell.downstream_cell == "C00009"  # (row 2, col 2)
    expected_slope = 2.0 / (10.0 * math.sqrt(2.0))
    assert math.isclose(center_cell.slope, expected_slope, rel_tol=1e-4)
    assert center_cell.state == "downstream"


def test_deterministic_tie_breaking():
    """
    Verifies tie-breaking order: N -> E -> S -> W -> NE -> SE -> SW -> NW.
    If N and E drop by the exact same height over the same distance, N must be selected.
    """
    elev = np.array([
        [20.0, 18.0, 20.0],  # N is 18.0 (drop = 2.0)
        [20.0, 20.0, 18.0],  # Center is 20.0, E is 18.0 (drop = 2.0)
        [20.0, 20.0, 20.0],
    ])
    grid = ComputationalGrid(
        elevation_m=elev,
        latitude=np.zeros((3, 3)),
        longitude=np.zeros((3, 3)),
        resolution_m=10.0,
    )

    terrain = D8Terrain.compute_from_grid(grid)
    center_cell = terrain.get_cell("C00005")

    # Both N (C00002) and E (C00006) have slope = 2.0 / 10.0 = 0.2
    # Because N appears before E in NEIGHBOR_ORDER, N must win
    assert center_cell.direction == "N"
    assert center_cell.downstream_cell == "C00002"
    assert math.isclose(center_cell.slope, 0.2, rel_tol=1e-4)


def test_terminal_states_classification():
    """
    Verifies that every cell is classified into: downstream, outlet, boundary, local_sink, or flat_sink.
    """
    # 5x5 terrain with center local sink (elev 10) surrounded by high ridge (elev 25)
    elev = np.full((5, 5), 25.0)
    elev[2, 2] = 10.0  # local sink
    elev[2, 3] = 10.0  # flat neighbor

    grid = ComputationalGrid(
        elevation_m=elev,
        latitude=np.zeros((5, 5)),
        longitude=np.zeros((5, 5)),
        resolution_m=10.0,
    )
    # Mark (4, 4) as outlet
    grid.set_outlets([(4, 4)])

    terrain = D8Terrain.compute_from_grid(grid)

    outlet_cell = terrain.get_cell("C00025")
    assert outlet_cell.state == "outlet"
    assert outlet_cell.downstream_cell is None

    # Boundary cell without lower neighbor
    b_cell = terrain.get_cell("C00001")
    assert b_cell.state == "boundary"
    assert b_cell.downstream_cell is None

    # Ridge cell sloping down into sink
    ridge_cell = terrain.get_cell("C00012")  # (2, 1) at 25.0m slopes to (2, 2) at 10.0m
    assert ridge_cell.state == "downstream"
    assert ridge_cell.downstream_cell == "C00013"

    # Flat sink cell (2, 2) has equal neighbor (2, 3) and no lower downhill path
    sink_cell = terrain.get_cell("C00013")
    assert sink_cell.state in ("local_sink", "flat_sink")
    assert sink_cell.downstream_cell is None


def test_flow_path_tracing():
    """Verifies continuous downstream path tracing to terminal."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)

    path = terrain.trace_to_terminal("C00001")
    assert len(path) >= 2
    assert path[0] == "C00001"

    # Terminal cell should have no downstream target
    terminal_cell = terrain.get_cell(path[-1])
    assert terminal_cell.downstream_cell is None
    assert terminal_cell.state in ("outlet", "boundary", "local_sink", "flat_sink")


def test_d8_validation_rules():
    """Verifies D8 topological validation checks."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)

    val = terrain.validate_d8()
    assert val["is_valid"] is True
    assert val["violation_count"] == 0
    assert val["outlet_count"] == 1
    assert val["downstream_count"] > 0


def test_d8_serialization_and_csv_export(tmp_path):
    """Verifies D8 terrain .npz, .metadata.json, and .csv export."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=8, cols=8, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)

    out_base = tmp_path / "test_d8_export"
    npz_path, json_path, csv_path = terrain.save_to_file(out_base)

    assert npz_path.exists()
    assert json_path.exists()
    assert csv_path.exists()

    # Verify CSV has headers and rows
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 + terrain.valid_cell_count
    assert "cell_id,row,col,elevation_m" in lines[0]
