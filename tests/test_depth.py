"""
Layer 9 — Water Depth Engine Unit Tests:
Verifies conversion from surface storage (m³) to cell depth (m/cm),
negative/zero validations, precision retention, and depth field dictionaries.
"""


import pytest

from flood_engine.depth import (
    DepthEngine,
    classify_depth,
    depth_field_cm,
    depth_m_to_cm,
    storage_to_depth_m,
)
from flood_engine.grid import ComputationalGrid


def test_storage_to_depth():
    """Verifies h = S / A formula."""
    assert storage_to_depth_m(10.0, 100.0) == pytest.approx(0.10)
    assert storage_to_depth_m(18.4, 100.0) == pytest.approx(0.184)


def test_depth_to_cm():
    """Verifies depth conversion to cm."""
    assert depth_m_to_cm(0.10) == pytest.approx(10.0)
    assert depth_m_to_cm(0.184) == pytest.approx(18.4)


def test_zero_storage():
    """Verifies zero storage produces 0.0m depth."""
    assert storage_to_depth_m(0.0, 100.0) == pytest.approx(0.0)
    assert depth_m_to_cm(0.0) == pytest.approx(0.0)


def test_negative_storage_rejected():
    """Verifies rejection of negative storage values."""
    with pytest.raises(ValueError, match="Negative surface storage"):
        storage_to_depth_m(-1.0, 100.0)


def test_zero_area_rejected():
    """Verifies rejection of zero or non-positive cell areas."""
    with pytest.raises(ValueError, match="Cell area must be > 0"):
        storage_to_depth_m(10.0, 0.0)
    with pytest.raises(ValueError, match="Cell area must be > 0"):
        storage_to_depth_m(10.0, -10.0)


def test_unknown_cell_rejected():
    """Verifies that unknown cell IDs in storage input raise ValueError."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    bad_storage = {"C00001": 5.0, "C99999": 2.0}
    with pytest.raises(ValueError, match="Unknown cell IDs"):
        engine.compute_cell_depths(grid, bad_storage, timestamp_seconds=60)


def test_missing_storage_defaults_zero():
    """Verifies that omitted cell IDs default to 0.0 storage."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    # Supply storage for only C00001
    partial_storage = {"C00001": 2.5}
    results = engine.compute_cell_depths(grid, partial_storage, timestamp_seconds=60)

    assert results["C00001"].depth_cm == pytest.approx(2.5)
    assert results["C00002"].depth_cm == pytest.approx(0.0)
    assert results["C00002"].storage_m3 == pytest.approx(0.0)


def test_cell_depth_field():
    """Verifies depth_field_cm generates dictionary of depth values."""
    grid = ComputationalGrid.create_synthetic_demo_grid(rows=4, cols=4, resolution_m=10.0)
    engine = DepthEngine(grid_crs="EPSG:32644")

    storage = {"C00001": 1.2, "C00002": 3.4}
    results = engine.compute_cell_depths(grid, storage, timestamp_seconds=60)
    field = depth_field_cm(results)

    assert field["C00001"] == pytest.approx(1.2)
    assert field["C00002"] == pytest.approx(3.4)


def test_internal_precision():
    """Verifies high floating-point precision is preserved without truncation."""
    val_m3 = 18.4123456789
    depth = storage_to_depth_m(val_m3, 100.0)
    cm = depth_m_to_cm(depth)
    assert depth == val_m3 / 100.0
    assert cm == pytest.approx(18.4123456789)


def test_depth_classification():
    """Verifies LOW, MODERATE, SEVERE, CRITICAL thresholds."""
    assert classify_depth(2.0) == "LOW"
    assert classify_depth(8.0) == "MODERATE"
    assert classify_depth(22.0) == "SEVERE"
    assert classify_depth(45.0) == "CRITICAL"
