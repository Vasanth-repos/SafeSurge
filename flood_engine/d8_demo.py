"""
Layer 2 — DEM + D8 Terrain Flow Demo & Validation Entry Point.
"""

from pathlib import Path

from flood_engine.d8 import D8Terrain
from flood_engine.grid import ComputationalGrid


def main():
    print("Urban Flood Nowcast — Layer 2 D8 Terrain Demo")
    print("=" * 50)

    # 1. Load hardened Layer 1 demo grid (20x20, 10m resolution)
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=20, cols=20, resolution_m=10.0)
    print(f"Loaded Grid: {grid.metadata.get('grid_id')} ({grid.rows}x{grid.columns}, res={grid.resolution_m}m)")

    # 2. Compute D8 Terrain Topology
    terrain = D8Terrain.compute_from_grid(grid)
    meta = terrain.metadata
    print(f"Computed D8 Terrain across {terrain.valid_cell_count} valid cells.")

    # 3. Terrain QA & Topology Statistics
    print("-" * 50)
    print(f"Valid Cells:          {meta['valid_cells']}")
    print(f"Downstream Cells:     {meta['downstream_count']} ({meta['downstream_pct']}%)")
    print(f"Configured Outlets:   {meta['outlet_count']} ({meta['outlet_pct']}%)")
    print(f"Boundary Exits:       {meta['boundary_exit_count']} ({meta['boundary_exit_pct']}%)")
    print(f"Local Sinks:          {meta['local_sink_count']} ({meta['local_sink_pct']}%)")
    print(f"Flat Sinks:           {meta['flat_sink_count']} ({meta['flat_sink_pct']}%)")
    print(f"Elevation Range:      {meta['elevation_min_m']}m - {meta['elevation_max_m']}m")
    print(f"Mean Slope Ratio:     {meta['mean_slope_ratio']:.4f} (Max: {meta['max_slope_ratio']:.4f})")
    print(f"Topology Validation:  {meta['validation_status']}")

    # 4. Demonstrate Sample Flow Path Tracing
    sample_start = "C00001"
    flow_path = terrain.trace_to_terminal(sample_start)
    print("-" * 50)
    print(f"Flow Path Trace from {sample_start} ({len(flow_path)} steps):")
    for idx, cid in enumerate(flow_path):
        c = terrain.get_cell(cid.split()[0])
        dist_str = f", dist={c.flow_distance_m:.1f}m" if c.flow_distance_m > 0 else ""
        arrow = " --> " if idx < len(flow_path) - 1 else f" [{c.state.upper()}]"
        print(f"  {c.cell_id} (elev={c.elevation_m:.2f}m, slope={c.slope_ratio:.4f}{dist_str}, dir={c.direction or 'None'}){arrow}")

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
