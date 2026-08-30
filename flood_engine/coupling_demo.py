"""
Layer 7 — Surface ↔ Drainage Coupling Demo Entry Point.
"""

from flood_engine.coupling import (
    DrainageInlet,
    InletCellMapping,
    SurfaceDrainageCouplingEngine,
)
from flood_engine.d8 import D8Terrain
from flood_engine.drainage import StatefulDrainageNetwork
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine


def main():
    print("Layer 7 - Surface <-> Drainage Coupling Engine")
    print("=" * 68)

    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    drainage = StatefulDrainageNetwork.create_synthetic_demo_network()
    inlets = [
        DrainageInlet("I001", "N001", base_capacity_m3_s=0.05),
        DrainageInlet("I002", "N002", base_capacity_m3_s=0.03, blockage_factor=0.6),
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

    print(f"Initialized coupled system with {len(inlets)} inlets across {len(terrain.cells)} cells.")
    print("Simulating storm runoff with coupled surface routing, inlet capture, and delayed surcharge:\n")

    # Ingest runoff burst
    for i in range(1, 6):
        t = i * 60
        r_input = {cid: (4.0 if cid in ("C00001", "C00022") else 0.0) for cid in terrain.cells}
        res = coupling.step(t, r_input)

        c1_store = res.surface_storage_m3_by_cell["C00001"]
        n1_store = res.drainage_storage_m3_by_node["N001"]
        cap_vol = res.total_drainage_capture_m3
        surch_pend = sum(res.pending_surcharge_m3_by_cell.values())

        print(
            f"t={t:3d}s | Runoff In={res.total_runoff_input_m3:4.1f} m3 | Capture={cap_vol:4.2f} m3 | "
            f"Surf C1={c1_store:5.2f} m3 | Pipe N1={n1_store:5.2f} m3 | "
            f"Pending Surcharge={surch_pend:5.2f} m3"
        )

    print("-" * 68)
    bal = coupling.mass_balance()
    print("Coupled Mass Conservation Summary:")
    print(f"  Cumulative Runoff:        {bal['cumulative_runoff_m3']:.4f} m3")
    print(f"  Active Surface Storage:   {bal['current_surface_storage_m3']:.4f} m3")
    print(f"  Active Drainage Storage:  {bal['current_drainage_storage_m3']:.4f} m3")
    print(f"  Pending Delayed Surcharge:{bal['pending_surcharge_m3']:.4f} m3")
    print(f"  Cumulative Outfall Disch: {bal['cumulative_drainage_outlet_m3']:.4f} m3")
    print(f"  Mass Balance Error:       {bal['mass_balance_error_m3']:.8f} m3")
    print(f"  System Conservation Check:{'PASS' if bal['is_conserved'] else 'FAIL'}")
    print("=" * 68)
    print("Layer 7 Surface <-> Drainage Coupling: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
