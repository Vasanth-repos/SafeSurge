"""
Layer 9 — Road Depth & Spatial Overlay Unit Tests:
Verifies road geometry conversions, CRS transformation, intersection calculation,
area-weighted depth, coverage fractions, quality states, and missing coverage handling.
"""

import pytest
from shapely.geometry import LineString, Polygon

from flood_engine.depth import (
    DepthEngine,
    RoadFeature,
    road_to_polygon,
)
from flood_engine.grid import ComputationalGrid


def test_line_road_requires_width():
    """Verifies that line-based road requires positive width_m."""
    line = LineString([(0, 0), (10, 0)])
    with pytest.raises(ValueError, match="requires width_m > 0"):
        RoadFeature(road_id="R1", geometry=line, width_m=None)
    with pytest.raises(ValueError, match="requires width_m > 0"):
        RoadFeature(road_id="R1", geometry=line, width_m=-2.0)


def test_polygon_road_does_not_require_width():
    """Verifies that polygon-based road does not require width."""
    poly = Polygon([(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)])
    road = RoadFeature(road_id="R2", geometry=poly, width_m=None)
    assert road.road_id == "R2"
    assert road.width_m is None


def test_invalid_geometry_rejected():
    """Verifies that empty geometry raises ValueError."""
    empty_line = LineString()
    with pytest.raises(ValueError, match="cannot be empty"):
        RoadFeature(road_id="R_EMPTY", geometry=empty_line, width_m=6.0)


def test_road_polygon_not_double_buffered():
    """Verifies that road polygons are used directly without buffering."""
    poly = Polygon([(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)])
    result_poly = road_to_polygon(poly, width_m=10.0)
    assert result_poly.area == pytest.approx(50.0)


def test_weighted_depth_single_cell():
    """Verifies that a road entirely inside a single uniform cell receives the exact cell depth."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    # Cell C00001 occupies (x: 0..10, y: 0..10)
    road_poly = Polygon([(2, 2), (8, 2), (8, 6), (2, 6), (2, 2)])  # Area = 24 m²
    road = RoadFeature(road_id="R_SINGLE", geometry=road_poly, source_crs="EPSG:32644")

    # Cell C00001 has 2.0 m³ storage -> 2.0 cm depth (area=100 m²)
    storage = {"C00001": 2.0}
    depth_res = engine.compute(grid, storage, [road], timestamp_seconds=60)

    rd = depth_res.roads["R_SINGLE"]
    assert rd.weighted_depth_cm == pytest.approx(2.0)
    assert rd.max_intersecting_cell_depth_cm == pytest.approx(2.0)
    assert rd.coverage_fraction == pytest.approx(1.0)
    assert rd.coverage_status == "FULL"


def test_weighted_depth_multiple_cells():
    """
    Verifies area-weighted road depth across multiple cells:
    C00005 (x: 0..10, y: 10..20) depth=10cm (area=50m²)
    C00006 (x: 10..20, y: 10..20) depth=20cm (area=50m²)
    Expected: (50*10 + 50*20) / 100 = 15.0 cm.
    """
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    # Road spans across C00005 (x: 5..10, y: 12..17 -> 5x5 = 25m²) and C00006 (x: 10..20, y: 12..17 -> 10x5 = 50m²)
    # Total area = 75 m². Expected: (25*10 + 50*20) / 75 = (250 + 1000) / 75 = 16.6667 cm
    road_poly = Polygon([(5, 12), (20, 12), (20, 17), (5, 17), (5, 12)])  # 75 m²
    road = RoadFeature(road_id="R_MULTI", geometry=road_poly, source_crs="EPSG:32644")

    # Set C00005 storage -> 10 cm (10.0 m³), C00006 storage -> 20 cm (20.0 m³)
    storage = {"C00005": 10.0, "C00006": 20.0}
    depth_res = engine.compute(grid, storage, [road], timestamp_seconds=60)

    rd = depth_res.roads["R_MULTI"]
    # (25 * 10.0 + 50 * 20.0) / 75.0 = 16.6667 cm
    expected_depth = (25.0 * 10.0 + 50.0 * 20.0) / 75.0
    assert rd.weighted_depth_cm == pytest.approx(expected_depth)
    assert rd.max_intersecting_cell_depth_cm == pytest.approx(20.0)
    assert rd.coverage_fraction == pytest.approx(1.0)
    assert rd.coverage_status == "FULL"


def test_no_coverage_road():
    """Verifies that roads outside the modeled grid return NO_COVERAGE and depth=None."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    # Road outside grid boundary (grid is 0..40, 0..40)
    outside_poly = Polygon([(100, 100), (120, 100), (120, 110), (100, 110), (100, 100)])
    road = RoadFeature(road_id="R_OUTSIDE", geometry=outside_poly, source_crs="EPSG:32644")

    depth_res = engine.compute(grid, {"C00001": 5.0}, [road], timestamp_seconds=60)
    rd = depth_res.roads["R_OUTSIDE"]

    assert rd.weighted_depth_cm is None
    assert rd.max_intersecting_cell_depth_cm is None
    assert rd.coverage_fraction == pytest.approx(0.0)
    assert rd.coverage_status == "NO_COVERAGE"


def test_partial_coverage_road():
    """Verifies partial coverage reporting when road extends outside grid."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    # C00008 is at row 1, col 3 (x: 30..40, y: 10..20)
    # Road from x=30 to x=50, y=12..17 (width=5m) -> 10m inside grid (50 m²), 10m outside grid (50 m²)
    partial_poly = Polygon([(30, 12), (50, 12), (50, 17), (30, 17), (30, 12)])  # Area = 100 m²
    road = RoadFeature(road_id="R_PARTIAL", geometry=partial_poly, source_crs="EPSG:32644")

    storage = {"C00008": 8.0}  # C00008 depth = 8.0 cm
    depth_res = engine.compute(grid, storage, [road], timestamp_seconds=60)

    rd = depth_res.roads["R_PARTIAL"]
    assert rd.coverage_fraction == pytest.approx(0.50)
    assert rd.coverage_status == "PARTIAL"
    assert rd.weighted_depth_cm == pytest.approx(8.0)
