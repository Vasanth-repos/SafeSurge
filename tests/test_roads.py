"""
Layer 17 — Road Exposure & Risk Tests:
Verifies STRtree cell intersection, exposure fraction, weighted depth, relevant maximum depth,
exposure-weighted confidence, and risk classification.
"""

import pytest
from shapely.geometry import LineString, Polygon
from roads.models import Road, RoadCellExposure
from roads.mapping import RoadSpatialMapper
from roads.exposure import calculate_road_depth, calculate_road_confidence
from roads.risk import classify_road_risk, RoadRiskEngine


def test_road_spatial_intersection_and_exposure_fraction():
    """
    Road R1: LineString (0, 5) -> (30, 5) with length 30m.
    Cell C1: Polygon (0, 0) -> (10, 10) [10m length intersection -> frac = 10/30 = 0.333]
    Cell C2: Polygon (10, 0) -> (20, 10) [10m length intersection -> frac = 10/30 = 0.333]
    Cell C3: Polygon (20, 0) -> (30, 10) [10m length intersection -> frac = 10/30 = 0.333]
    """
    road = Road("R1", "A", "B", LineString([(0.0, 5.0), (30.0, 5.0)]), length_m=30.0)
    cells = {
        "C1": Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
        "C2": Polygon([(10, 0), (20, 0), (20, 10), (10, 10)]),
        "C3": Polygon([(20, 0), (30, 0), (30, 10), (20, 10)]),
    }

    mapper = RoadSpatialMapper([road], cells)
    exposures = mapper.get_exposures("R1")
    assert len(exposures) == 3

    for exp in exposures:
        assert exp.intersection_length_m == pytest.approx(10.0)
        assert exp.exposure_fraction == pytest.approx(1.0 / 3.0)


def test_weighted_depth_and_relevant_maximum():
    """
    R001 intersects:
    C001 (frac=0.4): Depth = 2.0 cm
    C002 (frac=0.4): Depth = 20.0 cm
    C003 (frac=0.2): Depth = 4.0 cm
    Mean depth = 0.4*2 + 0.4*20 + 0.2*4 = 0.8 + 8.0 + 0.8 = 9.6 cm
    Max relevant depth = 20.0 cm
    Affected fraction = 1.0
    """
    exposures = [
        RoadCellExposure("R001", "C001", 40.0, 0.4),
        RoadCellExposure("R001", "C002", 40.0, 0.4),
        RoadCellExposure("R001", "C003", 20.0, 0.2),
    ]
    depths = {"C001": 2.0, "C002": 20.0, "C003": 4.0}

    mean_d, max_rel_d, aff_frac = calculate_road_depth(exposures, depths, minimum_exposure_fraction=0.10)
    assert mean_d == pytest.approx(9.6)
    assert max_rel_d == pytest.approx(20.0)
    assert aff_frac == pytest.approx(1.0)


def test_road_risk_classification():
    """Verifies road risk classification against thresholds."""
    assert classify_road_risk(2.0, 5.0, 15.0, 25.0) == "SAFE"
    assert classify_road_risk(8.0, 5.0, 15.0, 25.0) == "WATCH"
    assert classify_road_risk(18.0, 5.0, 15.0, 25.0) == "HIGH"
    assert classify_road_risk(28.0, 5.0, 15.0, 25.0) == "UNSAFE"
