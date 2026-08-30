"""
Layer 1 Grid Unit and Contract Tests:
Verifies ComputationalGrid catchment masking, boundary discovery,
outlet validation, O(1) cell lookup, and metadata persistence.
"""


import numpy as np
import pytest

from flood_engine.grid import ComputationalGrid, GridCell


def test_catchment_vs_nodata_separation():
    """Verifies that catchment domain and DEM nodata are strictly separated."""
    elev = np.array([
        [20.0, 22.0, np.nan],
        [18.0, 19.0, 21.0],
        [15.0, 16.0, 17.0],
    ])
    lat = np.zeros((3, 3))
    lon = np.zeros((3, 3))

    # Cell (0, 0) is outside catchment
    catchment = np.array([
        [False, True, True],
        [True, True, True],
        [True, True, True],
    ])

    grid = ComputationalGrid(
        elevation_m=np.nan_to_num(elev, nan=-9999.0),
        latitude=lat,
        longitude=lon,
        catchment_mask=catchment,
        dem_nodata_mask=np.isnan(elev),
    )

    # Total cells: 9
    assert grid.total_cells == 9
    # (0, 0) is outside catchment -> invalid
    assert not grid.valid_mask[0, 0]
    # (0, 2) has nodata -> invalid
    assert not grid.valid_mask[0, 2]
    # (1, 1) inside catchment with valid elevation -> valid
    assert grid.valid_mask[1, 1]
    # Valid count: 9 - 2 = 7
    assert grid.valid_cells_count == 7


def test_direct_o1_cell_lookup():
    """Verifies O(1) indexed cell retrieval."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10)

    cell_1 = grid.get_cell("C00001")
    assert isinstance(cell_1, GridCell)
    assert cell_1.cell_id == "C00001"
    assert cell_1.row == 0
    assert cell_1.col == 0

    cell_55 = grid.get_cell("C00055")
    assert cell_55.row == 5
    assert cell_55.col == 4

    with pytest.raises(IndexError):
        grid.get_cell("C00500")  # Out of bounds for 100-cell grid


def test_boundary_mask_derivation():
    """Verifies that all perimeter cells touching outside the catchment are flagged as boundary."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10)

    # (0, 0) is on edge of grid -> boundary
    assert grid.boundary_mask[0, 0]
    # (9, 9) is on edge of grid -> boundary
    assert grid.boundary_mask[9, 9]
    # Interior cell (5, 5) surrounded by valid neighbors is NOT boundary
    assert not grid.boundary_mask[5, 5]


def test_outlet_semantics_and_validation():
    """Verifies outlet assignment and physical constraint rules."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10)

    # Valid boundary cell (9, 9) should succeed as outlet
    grid.set_outlets([(9, 9)])
    assert grid.outlet_mask[9, 9]

    # Interior cell (5, 5) must be rejected because it is not on the boundary
    with pytest.raises(ValueError, match="must lie on the catchment boundary"):
        grid.set_outlets([(5, 5)])

    # Non-catchment cell must be rejected
    grid.catchment_mask[0, 9] = False
    grid.valid_mask = grid.catchment_mask & (~grid.dem_nodata_mask)
    grid.boundary_mask = grid.compute_boundary_mask()
    with pytest.raises(ValueError, match="outside the modeled catchment"):
        grid.set_outlets([(0, 9)])


def test_grid_serialization_and_metadata(tmp_path):
    """Verifies grid .npz and .json serialization roundtrip and provenance metadata."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=15, cols=15, resolution_m=10.0)
    save_path = tmp_path / "test_grid"

    npz_path, json_path = grid.save_to_file(save_path)
    assert npz_path.exists()
    assert json_path.exists()

    loaded = ComputationalGrid.load_from_file(save_path)
    assert loaded.rows == 15
    assert loaded.columns == 15
    assert loaded.resolution_m == 10.0
    assert loaded.metadata["catchment_id"] == "CHENNAI_URBAN_DEMO"
    assert loaded.valid_cells_count == grid.valid_cells_count
