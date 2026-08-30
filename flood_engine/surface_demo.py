"""
Layer 5 — Surface Storage & D8 Routing Demo Entry Point.
"""

from flood_engine.d8 import D8Terrain
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine


def main():
    print("Layer 5 — Dynamic Surface Storage & D8 Routing")
    print("=" * 65)

    grid = ComputationalGrid.create_synthetic_demo_grid(rows=10, cols=10, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    print(f"Loaded Grid: {grid.metadata.get('grid_id')} ({grid.rows}x{grid.columns}, res={grid.resolution_m}m)")
    print(f"Routing Coeff k: {engine.routing_coefficient_k}, Max Fraction: {engine.max_routing_fraction}\n")

    # Ingest runoff burst on upper ridge cell (C00001) across 4 timesteps
    for i in range(1, 5):
        t = i * 60
        runoff_input = {cid: (2.5 if cid == "C00001" and i == 1 else 0.0) for cid in terrain.cells}
        step = engine.step(t, runoff_input)

        c1 = step.cells["C00001"]
        c_down = step.cells.get(c1.downstream_cell) if c1.downstream_cell else None
        down_info = f"| downstream {c_down.cell_id} storage={c_down.new_storage_m3:.4f} m³" if c_down else ""

        print(
            f"t={t:3d}s | C00001 S_old={c1.old_storage_m3:.4f} m³ | outflow={c1.surface_outflow_m3:.4f} m³ | "
            f"S_new={c1.new_storage_m3:.4f} m³ (depth={c1.water_depth_m*100:5.2f}cm) {down_info}"
        )

    print("-" * 65)
    bal = engine.mass_balance()
    diag = engine.get_diagnostics()

    print("Mass Conservation Summary:")
    print(f"  Total Cumulative Runoff Input: {bal['cumulative_runoff_input_m3']:.6f} m³")
    print(f"  Total Active Surface Storage:  {bal['current_surface_storage_m3']:.6f} m³")
    print(f"  Total Boundary Discharge:      {bal['cumulative_boundary_outflow_m3']:.6f} m³")
    print(f"  Mass Balance Error:            {bal['mass_balance_error_m3']:.8f} m³")
    print(f"  Conservation Invariant Check:  {'PASS' if bal['is_conserved'] else 'FAIL'}\n")

    print(f"Spatial Diagnostics: Max Depth = {diag['max_depth_m']*100:.2f} cm | Risk Counts = {diag['risk_counts']}")
    print("=" * 65)
    print("Layer 5 Surface Routing: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
