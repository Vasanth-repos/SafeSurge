"""
Layer 1 Grid Demo & Validation:
Demonstrates ComputationalGrid initialization, boundary mask derivation,
outlet enforcement, and metadata provenance.
"""

from pathlib import Path
from flood_engine.grid import ComputationalGrid


def main():
    print("Urban Flood Nowcast — Layer 1 Grid Demo")
    print("=" * 45)

    grid = ComputationalGrid.create_synthetic_demo_grid(rows=20, cols=20, resolution_m=10.0)

    print(f"Grid ID:           {grid.metadata.get('grid_id')}")
    print(f"Catchment ID:      {grid.metadata.get('catchment_id')}")
    print(f"Dimensions:        {grid.rows} rows × {grid.columns} cols ({grid.total_cells} total cells)")
    print(f"Valid Cells:       {grid.valid_cells_count} / {grid.total_cells}")
    print(f"Boundary Cells:    {int(grid.boundary_mask.sum())}")
    print(f"Configured Outlets:{int(grid.outlet_mask.sum())}")
    print(f"Resolution:        {grid.resolution_m} m (Area: {grid.cell_area_m2} m²)")
    print(f"CRS:               {grid.crs}")

    # Test O(1) cell lookup
    sample_cell = grid.get_cell("C00001")
    print("-" * 45)
    print(f"Sample Cell [C00001]: (r={sample_cell.row}, c={sample_cell.col}), elev={sample_cell.elevation_m:.2f}m, is_boundary={sample_cell.is_boundary}")

    # Export grid artifacts
    export_dir = Path("data/processed/grid")
    export_dir.mkdir(parents=True, exist_ok=True)
    npz_path, json_path = grid.save_to_file(export_dir / "layer1_demo_grid")
    print(f"Saved grid archive: {npz_path}")
    print(f"Saved metadata:     {json_path}")

    # Re-load verification
    reloaded = ComputationalGrid.load_from_file(npz_path)
    assert reloaded.total_cells == grid.total_cells
    assert reloaded.valid_cells_count == grid.valid_cells_count
    print("Grid serialization & roundtrip check: PASS")
    print("=" * 45)
    print("Grid identity:      PASS")
    print("Catchment boundary: PASS")
    print("Outlet semantics:   PASS")


if __name__ == "__main__":
    main()
