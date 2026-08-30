"""
End-to-End Integration Test: Layer 5 (Surface Storage) -> Layer 6 (Drainage Network Coupling).
"""

from flood_engine.d8 import D8Terrain
from flood_engine.drainage import DrainageEdge, DrainageNode, StatefulDrainageNetwork
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine


def test_surface_to_drainage_coupling_conservation():
    """
    Verifies that captured surface volume routed into drainage nodes satisfies:
    Captured Volume = Node Storage + Outlet Discharge + Surcharge Volume.
    """
    # 1. Surface grid & D8
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface_engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)

    # 2. Drainage Network with inlet at cell C00001
    drainage_net = StatefulDrainageNetwork(expected_timestep_seconds=60)
    drainage_net.add_node(DrainageNode("INLET_1", 13.0, 80.0, node_type="inlet", storage_capacity_m3=10.0, associated_cell_id="C00001"))
    drainage_net.add_node(DrainageNode("OUTLET_1", 13.0, 80.1, node_type="outlet", base_capacity_m3_s=0.05, storage_capacity_m3=10.0))
    drainage_net.add_edge(DrainageEdge("E_PIPE", "INLET_1", "OUTLET_1", capacity_m3_s=0.04))

    # 3. Simulate storm: surface receives runoff, captures a fraction into drainage
    for i in range(1, 6):
        t = i * 60
        r_step = surface_engine.step(t, {"C00001": 2.0, **{cid: 0.0 for cid in terrain.cells.keys() if cid != "C00001"}})

        # Inlet captures 0.8 m³ from surface ponding if available
        captured_m3 = min(0.8, r_step.cells["C00001"].new_storage_m3)
        d_step = drainage_net.step(t, inflow_volume_m3_by_node={"INLET_1": captured_m3})

        assert abs(d_step.mass_balance_error_m3) <= 1e-5

    d_bal = drainage_net.mass_balance()
    assert d_bal["is_conserved"] is True
    assert d_bal["cumulative_inflow_m3"] > 0.0
    assert (
        d_bal["cumulative_inflow_m3"]
        == d_bal["current_node_storage_m3"] + d_bal["cumulative_outlet_discharge_m3"] + d_bal["cumulative_surcharge_m3"]
    )
