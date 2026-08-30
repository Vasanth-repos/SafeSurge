"""
Layer 10 — Flood Risk Integration Tests:
Executes the complete chain: Layer 5 Surface Storage -> Layer 9 Water Depth -> Layer 10 Risk Engine,
verifying state immutability, road coverage preservation, and deterministic classification.
"""

import pytest
from shapely.geometry import Polygon

from flood_engine.d8 import D8Terrain
from flood_engine.depth import DepthEngine, RoadFeature
from flood_engine.grid import ComputationalGrid
from flood_engine.risk import (
    DataStatus,
    RiskEngine,
)
from flood_engine.surface import SurfaceStorageEngine


def test_full_chain_layer5_layer9_layer10_integration():
    """
    Simulates:
    1. Layer 5: Ingests 18.4 m³ storage on C00001 (100 m² cell).
    2. Layer 9: Computes cell depth = 18.4 cm and projects onto road.
    3. Layer 10: Classifies C00001 as HIGH risk, verifies lead time and data status.
    4. Invariant: Neither Layer 9 nor Layer 10 mutates surface storage or depth.
    """
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    terrain = D8Terrain.compute_from_grid(grid)
    surface_engine = SurfaceStorageEngine(grid=grid, terrain=terrain, expected_timestep_seconds=60)
    depth_engine = DepthEngine(grid_crs="EPSG:32644")
    risk_engine = RiskEngine()

    road_geom = Polygon([(1, 1), (9, 1), (9, 5), (1, 5), (1, 1)])
    road = RoadFeature(road_id="R001_MAIN", geometry=road_geom, source_crs="EPSG:32644")

    # Step 1: Run surface storage
    storage_input = {"C00001": 18.4, **{cid: 0.0 for cid in terrain.cells.keys() if cid != "C00001"}}
    s_step = surface_engine.step(60, storage_input)

    # Step 2: Layer 9 Depth calculation
    current_storage = {cid: cs.new_storage_m3 for cid, cs in s_step.cells.items()}
    depth_res = depth_engine.compute(grid, current_storage, [road], timestamp_seconds=60)

    c1_depth_cm = depth_res.cells["C00001"].depth_cm
    assert c1_depth_cm == pytest.approx(current_storage["C00001"])
    assert c1_depth_cm >= 15.0  # In HIGH risk bracket

    # Step 3: Layer 10 Risk classification (forecast valid at t=60, reference at t=0)
    risk_output = risk_engine.classify(depth_res, reference_time_seconds=0)

    # Verify cell classification
    c1_risk = risk_output["cells"]["C00001"]
    assert c1_risk["depth_cm"] == pytest.approx(c1_depth_cm, abs=1e-3)
    assert c1_risk["risk_state"] == "HIGH"
    assert c1_risk["data_status"] == "VALID"
    assert c1_risk["lead_time_seconds"] == 60
    assert c1_risk["risk_profile_id"] == "prototype_v1"

    # Verify road classification
    r1_risk = risk_output["roads"]["R001_MAIN"]
    assert r1_risk["weighted_depth_cm"] == pytest.approx(c1_depth_cm, abs=1e-3)
    assert r1_risk["risk_state"] == "HIGH"
    assert r1_risk["coverage_status"] == "FULL"
    assert r1_risk["data_status"] == "VALID"

    # Invariant: storage is unmutated
    assert surface_engine.storage("C00001") == pytest.approx(current_storage["C00001"])


def test_road_no_coverage_preserves_no_data_risk_status():
    """Verifies that an unmodeled road receives risk_state=None and data_status=NO_DATA."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    depth_engine = DepthEngine(grid_crs="EPSG:32644")
    risk_engine = RiskEngine()

    outside_road = RoadFeature(
        road_id="R_OUTSIDE",
        geometry=Polygon([(100, 100), (120, 100), (120, 110), (100, 110), (100, 100)]),
        source_crs="EPSG:32644",
    )

    depth_res = depth_engine.compute(grid, {"C00001": 20.0}, [outside_road], timestamp_seconds=60)
    risk_res = risk_engine.classify_roads(depth_res.roads, reference_time_seconds=0)

    rd_risk = risk_res["R_OUTSIDE"]
    assert rd_risk.risk_state is None
    assert rd_risk.data_status == DataStatus.NO_DATA
    assert rd_risk.coverage_status == "NO_COVERAGE"
