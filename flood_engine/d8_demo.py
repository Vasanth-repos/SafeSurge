"""
Layer 2 — DEM + D8 Terrain Flow Demo & Validation Entry Point.
"""

from pathlib import Path
from flood_engine.grid import ComputationalGrid
from flood_engine.d8 import D8Terrain


def main():
    print("Urban Flood Nowcast — Layer 2 D8 Terrain Demo")
    print("=" * 50)

    # 1. Load hardened Layer 1 demo grid (20x20, 10m resolution)
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=20, cols=20, resolution_m=10.0)
    print(f"Loaded Grid: {grid.metadata.get('grid_id')} ({grid.rows}x{grid.columns}, res={grid.resolution_m}m)")

    # 2. Compute D8 Terrain Topology
    terrain = D8Terrain.compute_from_grid(grid)
    print(f"Computed D8 Terrain across {terrain.valid_cell_count} valid cells.")

    # 3. Validate D8 Constraints
    val = terrain.validate_d8()
    print("-" * 50)
    print(f"Valid Cells:          {val['total_valid_cells']}")
    print(f"Downstream Cells:     {val['downstream_count']}")
    print(f"Configured Outlets:   {val['outlet_count']}")
    print(f"Boundary Terminals:   {val['boundary_count']}")
    print(f"Local Sinks:          {val['local_sink_count']}")
    print(f"Flat Sinks:           {val['flat_sink_count']}")
    print(f"Violations:           {val['violation_count']}")
    print(f"Topology Validation:  {'PASS' if val['is_valid'] else 'FAIL'}")

    # 4. Demonstrate Sample Flow Path Tracing
    sample_start = "C00001"
    flow_path = terrain.trace_to_terminal(sample_start)
    print("-" * 50)
    print(f"Flow Path Trace from {sample_start} ({len(flow_path)} steps):")
    for idx, cid in enumerate(flow_path):
        c = terrain.get_cell(cid.split()[0])
        arrow = " --> " if idx < len(flow_path) - 1 else f" [{c.state.upper()}]"
        print(f"  {c.cell_id} (elev={c.elevation_m:.2f}m, dir={c.direction or 'None'}){arrow}")

    # 5. Export D8 Artifacts
    export_dir = Path("data/processed/grid")
    npz_path, json_path, csv_path = terrain.save_to_file(export_dir / "d8_terrain")
    print("-" * 50)
    print(f"Saved D8 NPZ:      {npz_path}")
    print(f"Saved D8 Metadata: {json_path}")
    print(f"Saved Routing CSV: {csv_path}")
    print("=" * 50)
    print("Layer 2 D8 Demo: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
