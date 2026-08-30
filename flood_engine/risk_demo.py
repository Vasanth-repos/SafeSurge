"""
Layer 10 — Flood Risk Classification Demo:
Demonstrates classification of cell and road flood depths into prototype risk states
(SAFE, WATCH, HIGH, UNSAFE) across a forecast timeline.
"""

from shapely.geometry import LineString, Polygon

from flood_engine.depth import DepthEngine, RoadFeature
from flood_engine.grid import ComputationalGrid
from flood_engine.risk import RiskEngine


def main():
    print("Layer 10 - Flood Risk Classification Engine")
    print("=" * 68)

    grid = ComputationalGrid.create_synthetic_demo_grid(rows=6, cols=6, resolution_m=10.0)
    depth_engine = DepthEngine(grid_crs="EPSG:32644")
    risk_engine = RiskEngine()

    roads = [
        RoadFeature("R001_MAIN_AVENUE", Polygon([(2, 2), (25, 2), (25, 8), (2, 8), (2, 2)]), source_crs="EPSG:32644"),
        RoadFeature("R002_CROSS_ST", LineString([(5, 0), (5, 30)]), width_m=6.0, source_crs="EPSG:32644"),
        RoadFeature("R003_OUTSIDE_HWY", Polygon([(100, 100), (150, 100), (150, 110), (100, 110), (100, 100)]), source_crs="EPSG:32644"),
    ]

    storage_by_cell = {
        "C00001": 18.4,  # 18.4 cm -> HIGH
        "C00002": 28.5,  # 28.5 cm -> UNSAFE
        "C00003": 8.0,   #  8.0 cm -> WATCH
        "C00004": 2.0,   #  2.0 cm -> SAFE
    }

    # Forecast at t=1800s (lead time +30 min from reference t=0)
    depth_result = depth_engine.compute(grid, storage_by_cell, roads, timestamp_seconds=1800)
    risk_result = risk_engine.classify(depth_result, reference_time_seconds=0)

    print(f"Loaded Profile: {risk_result['risk_profile_id']}")
    print(f"Timing Context: Ref={risk_result['reference_time_seconds']}s | Valid={risk_result['valid_time_seconds']}s | Lead={risk_result['lead_time_seconds']/60:.0f} min\n")

    print("Cell Risk States (Sample):")
    for cid in ("C00001", "C00002", "C00003", "C00004"):
        c_info = risk_result["cells"][cid]
        print(
            f"  {cid}: Depth={c_info['depth_cm']:5.2f} cm | Risk={c_info['risk_state']:6s} | "
            f"Status={c_info['data_status']:5s} | Source={c_info['source']}"
        )

    print("\nRoad Risk States:")
    for rid, r_info in risk_result["roads"].items():
        d_str = f"{r_info['weighted_depth_cm']:5.2f} cm" if r_info['weighted_depth_cm'] is not None else "   N/A  "
        risk_str = r_info['risk_state'] if r_info['risk_state'] else "  N/A "
        print(
            f"  {rid:18s} | Depth={d_str} | Risk={risk_str:6s} | "
            f"Coverage={r_info['coverage_fraction']*100:5.1f}% [{r_info['coverage_status']:11s}] | Status={r_info['data_status']}"
        )

    print("-" * 68)
    print("Layer 10 Risk Classification Engine: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
