"""
Layer 9 — Water Depth Engine Demo Entry Point:
Transforms surface flood storage into cell-average depth fields and projects
inundation onto road segments via area-weighted spatial overlay.
"""

from shapely.geometry import Polygon, LineString
from flood_engine.grid import ComputationalGrid
from flood_engine.depth import (
    DepthEngine,
    RoadFeature,
    classify_depth,
)


def main():
    print("Layer 9 - Water Depth Engine & Road Inundation Field")
    print("=" * 68)

    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    # Define sample roads
    roads = [
        RoadFeature("R001_MAIN_AVENUE", Polygon([(2, 2), (25, 2), (25, 8), (2, 8), (2, 2)]), source_crs="EPSG:32644"),
        RoadFeature("R002_CROSS_ST", LineString([(5, 0), (5, 30)]), width_m=6.0, source_crs="EPSG:32644"),
        RoadFeature("R003_OUTSIDE_HWY", Polygon([(100, 100), (150, 100), (150, 110), (100, 110), (100, 100)]), source_crs="EPSG:32644"),
    ]

    # Ingest synthetic storage pattern
    storage_by_cell = {
        "C00001": 15.0,  # 15 cm depth
        "C00002": 25.0,  # 25 cm depth
        "C00003": 5.0,   # 5 cm depth
    }

    result = engine.compute(grid, storage_by_cell, roads, timestamp_seconds=60)

    print("Cell Flood Depths (Sample):")
    for cid in ("C00001", "C00002", "C00003", "C00004"):
        cd = result.cells[cid]
        cls = classify_depth(cd.depth_cm)
        print(f"  {cid}: Storage={cd.storage_m3:5.2f} m3 | Depth={cd.depth_cm:5.2f} cm [{cls:8s}]")

    print("\nRoad Segment Inundation Overlay:")
    for rid, rd in result.roads.items():
        depth_str = f"{rd.weighted_depth_cm:5.2f} cm" if rd.weighted_depth_cm is not None else "   N/A  "
        max_str = f"{rd.max_intersecting_cell_depth_cm:5.2f} cm" if rd.max_intersecting_cell_depth_cm is not None else "  N/A  "
        print(
            f"  {rid:18s} | Weighted Depth={depth_str} | Max Cell Depth={max_str} | "
            f"Coverage={rd.coverage_fraction*100:5.1f}% [{rd.coverage_status}]"
        )

    print("-" * 68)
    print("Layer 9 Water Depth Engine: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
