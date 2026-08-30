"""
Layer 3 (Hardened) — Rainfall Replay Engine Tests:
Verifies scalar replay, deterministic iteration, timestep validation,
schema integrity, error handling, fingerprinting, volume helpers, and spatial replay.
"""

import math

import pytest

from replay.rainfall import (
    RainfallStep,
    ScalarRainfallReplay,
    SpatialRainfallReplay,
    load_rainfall_replay,
    rainfall_depth_to_volume_m3,
    rainfall_mm_to_meters,
)


def test_scalar_rainfall_replay_and_stats():
    """Verifies scalar replay loading and statistical aggregations."""
    replay = load_rainfall_replay("data/replay/rainfall/storm_01.json")

    assert isinstance(replay, ScalarRainfallReplay)
    assert replay.step_count == 3
    assert replay.timestep_seconds == 60
    assert replay.duration_seconds == 180
    assert replay.total_rainfall_mm == 12.0
    assert replay.max_timestep_rainfall_mm == 6.0
    assert replay.mean_timestep_rainfall_mm == 4.0


def test_deterministic_replay_iteration():
    """Verifies that replay() is a pure deterministic generator yielding exact steps."""
    replay = load_rainfall_replay("data/replay/rainfall/storm_01.json")

    steps_1 = list(replay.replay())
    steps_2 = list(replay.replay())

    assert len(steps_1) == 3
    assert steps_1 == steps_2

    assert steps_1[0] == RainfallStep(minute=1, timestamp_seconds=60, rainfall_mm=2.0, timestep_seconds=60)
    assert steps_1[1] == RainfallStep(minute=2, timestamp_seconds=120, rainfall_mm=4.0, timestep_seconds=60)
    assert steps_1[2] == RainfallStep(minute=3, timestamp_seconds=180, rainfall_mm=6.0, timestep_seconds=60)


def test_config_timestep_alignment():
    """Verifies that rainfall replay timestep must match config.yaml simulation timestep."""
    # Matches 60s
    replay = load_rainfall_replay("data/replay/rainfall/storm_01.json", config_path="config.yaml")
    assert replay.timestep_seconds == 60

    # Fails when mismatch occurs
    bad_data = {
        "schema_version": "rainfall-replay-v1",
        "timestep_seconds": 30,
        "steps": [{"minute": 1, "rainfall_mm": 5.0}],
    }
    with pytest.raises(ValueError, match="does not match configured simulation timestep"):
        ScalarRainfallReplay.load_from_dict(bad_data, expected_timestep_seconds=60)


def test_invalid_inputs_rejection():
    """Verifies strict validation against malformed, negative, NaN, or non-contiguous data."""
    # Negative rainfall
    with pytest.raises(ValueError, match="negative rainfall"):
        ScalarRainfallReplay.load_from_dict({
            "timestep_seconds": 60,
            "steps": [{"minute": 1, "rainfall_mm": -2.0}],
        })

    # NaN rainfall
    with pytest.raises(ValueError, match="invalid non-numeric rainfall"):
        ScalarRainfallReplay.load_from_dict({
            "timestep_seconds": 60,
            "steps": [{"minute": 1, "rainfall_mm": float("nan")}],
        })

    # Non-contiguous minutes
    with pytest.raises(ValueError, match="non-contiguous minute"):
        ScalarRainfallReplay.load_from_dict({
            "timestep_seconds": 60,
            "steps": [
                {"minute": 1, "rainfall_mm": 2.0},
                {"minute": 3, "rainfall_mm": 4.0},  # Skipped minute 2
            ],
        })

    # Empty steps
    with pytest.raises(ValueError, match="non-empty 'steps' array"):
        ScalarRainfallReplay.load_from_dict({
            "timestep_seconds": 60,
            "steps": [],
        })


def test_fingerprinting():
    """Verifies file sha256 and canonical content fingerprints."""
    replay = load_rainfall_replay("data/replay/rainfall/storm_01.json")
    assert len(replay.source_sha256) == 64
    assert len(replay.content_fingerprint) == 64


def test_unit_conversions():
    """Verifies mm to meters and rainfall depth to volume conversions."""
    assert rainfall_mm_to_meters(2.0) == 0.002
    assert rainfall_mm_to_meters(10.0) == 0.010

    # 10 mm on 100 m² = 0.01 m * 100 m² = 1.0 m³
    vol = rainfall_depth_to_volume_m3(rainfall_mm=10.0, area_m2=100.0)
    assert math.isclose(vol, 1.0)


def test_spatial_rainfall_replay():
    """Verifies spatial rainfall replay loading and execution."""
    replay = load_rainfall_replay("data/replay/rainfall/spatial_storm_01.json")

    assert isinstance(replay, SpatialRainfallReplay)
    assert replay.step_count == 2
    steps = list(replay.replay())
    assert len(steps) == 2
    assert steps[0].cells["C00001"] == 4.2
    assert steps[0].cells["C00003"] == 7.3


def test_spatial_deterministic_ordering():
    """Verifies that spatial cells are normalized into sorted deterministic key order."""
    data = {
        "schema_version": "spatial-rainfall-replay-v1",
        "timestep_seconds": 60,
        "steps": [
            {
                "timestamp": 60,
                "cells": {
                    "C00003": 7.3,
                    "C00001": 4.2,
                    "C00002": 5.1,
                },
            }
        ],
    }
    replay = SpatialRainfallReplay.load_from_dict(data)
    step = next(replay.replay())
    keys = list(step.cells.keys())
    assert keys == ["C00001", "C00002", "C00003"]


def test_spatial_unknown_cell_rejection():
    """Verifies that unknown cells not in the computational grid are rejected."""
    grid_cells = {"C00001", "C00002"}
    data = {
        "schema_version": "spatial-rainfall-replay-v1",
        "timestep_seconds": 60,
        "steps": [
            {
                "timestamp": 60,
                "cells": {
                    "C00001": 4.2,
                    "C99999": 7.3,  # Unknown cell
                },
            }
        ],
    }
    with pytest.raises(ValueError, match="Unknown cell ID 'C99999'"):
        SpatialRainfallReplay.load_from_dict(data, valid_cell_ids=grid_cells)


def test_spatial_strict_coverage():
    """Verifies strict coverage fails if any grid cell is missing from rainfall."""
    grid_cells = {"C00001", "C00002", "C00003"}
    data = {
        "schema_version": "spatial-rainfall-replay-v1",
        "timestep_seconds": 60,
        "steps": [
            {
                "timestamp": 60,
                "cells": {
                    "C00001": 4.2,
                    "C00002": 5.1,
                    # Missing C00003
                },
            }
        ],
    }
    with pytest.raises(ValueError, match="Strict coverage failed"):
        SpatialRainfallReplay.load_from_dict(data, valid_cell_ids=grid_cells, strict_coverage=True)
