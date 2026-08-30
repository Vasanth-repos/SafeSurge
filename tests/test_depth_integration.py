"""
Layer 9 — Water Depth Engine Integration Tests:
Verifies seamless coupling with Layer 5 surface storage outputs,
and proves that DepthEngine is strictly read-only with respect to hydrologic storage state.
"""

import pytest
from shapely.geometry import Polygon

from flood_engine.d8 import D8Terrain
from flood_engine.depth import DepthEngine, RoadFeature
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStorageEngine


def test_surface_to_depth_engine_integration_and_immutability():
    """
    Simulates storm in Layer 5 SurfaceStorageEngine -> feeds into Layer 9 DepthEngine.
    Verifies:
    1. DepthEngine produces correct cell and road depth fields.
    2. SurfaceStorageEngine storage state is NOT mutated by DepthEngine (read-only invariant).
    """
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface_engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)
    depth_engine = DepthEngine(grid_crs="EPSG:32644")

    # Construct test road covering C00001 (x: 0..10, y: 0..10)
    road_geom = Polygon([(1, 1), (9, 1), (9, 5), (1, 5), (1, 1)])  # Area = 32 m²
    road = RoadFeature(road_id="MAIN_ST", geometry=road_geom, source_crs="EPSG:32644")

    # Step 1: Runoff into C00001
    s_step = surface_engine.step(60, {"C00001": 5.0, **{cid: 0.0 for cid in terrain.cells if cid != "C00001"}})
    c1_storage_before = surface_engine.storage("C00001")
    assert c1_storage_before > 0.0

    # Layer 9 computation
    storage_input = {cid: cs.new_storage_m3 for cid, cs in s_step.cells.items()}
    depth_result = depth_engine.compute(grid, storage_input, [road], timestamp_seconds=60)

    # Invariant: SurfaceStorageEngine state is unchanged
    assert surface_engine.storage("C00001") == pytest.approx(c1_storage_before)

    # Road depth matches cell depth
    c1_depth_cm = depth_result.cells["C00001"].depth_cm
    assert depth_result.roads["MAIN_ST"].weighted_depth_cm == pytest.approx(c1_depth_cm)
    assert depth_result.roads["MAIN_ST"].coverage_status == "FULL"
