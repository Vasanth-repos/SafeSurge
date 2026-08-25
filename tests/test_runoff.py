"""
Layer 4 (Hardened) — Runoff Generation Engine Tests:
Verifies SCS-CN cumulative monotonicity (0 -> 10 -> 20 -> 30 mm), timestamp integrity,
Layer 3 replay integration, Curve Number physical sanity, mass balance conservation,
spatial rainfall processing, and event reset isolation.
"""

import pytest
import math
from pathlib import Path
from flood_engine.runoff import RunoffEngine, compute_scs_cn_potential_retention, compute_cumulative_scs_cn_runoff
from replay.rainfall import load_rainfall_replay


def test_scs_cn_monotonicity_0_10_20_30():
    """
    Verifies cumulative sequence P = 0, 10, 20, 30 mm (fed as increments 0, 10, 10, 10 mm)
    produces strictly non-decreasing cumulative runoff: Q(0) <= Q(10) <= Q(20) <= Q(30),
    Delta Q >= 0, Q <= P, and V >= 0.
    """
    engine = RunoffEngine(
        cell_areas_m2={"C00001": 900.0},
        curve_numbers={"C00001": 85.0},
        default_cn=85.0,
        expected_timestep_seconds=60,
    )

    steps = [
        engine.process_timestep(60, 0.0),
        engine.process_timestep(120, 10.0),
        engine.process_timestep(180, 10.0),
        engine.process_timestep(240, 10.0),
    ]

    q_vals = [s.cell_states["C00001"].cumulative_runoff_mm for s in steps]
    p_vals = [s.cell_states["C00001"].cumulative_rainfall_mm for s in steps]
    dq_vals = [s.cell_states["C00001"].incremental_runoff_mm for s in steps]
    v_vals = [s.cell_states["C00001"].runoff_volume_m3 for s in steps]

    # Cumulative rainfall checkpoints: 0, 10, 20, 30
    assert p_vals == [0.0, 10.0, 20.0, 30.0]

    # Monotonicity checks
    assert q_vals[0] <= q_vals[1] <= q_vals[2] <= q_vals[3]
    for q, p in zip(q_vals, p_vals):
        assert q <= p
    for dq in dq_vals:
        assert dq >= 0.0
    for v in v_vals:
        assert v >= 0.0

    # Explicit numerical checks for CN 85: S = 44.82mm, Ia = 8.96mm
    # For P=10mm: Q ≈ (10 - 8.96)^2 / (10 - 8.96 + 44.82) ≈ 0.0234 mm
    assert math.isclose(q_vals[1], 0.0234, abs_tol=1e-3)
    assert q_vals[3] > 6.0


def test_timestamp_integrity_and_monotonicity():
    """Verifies that timestamp disorder, duplicates, or non-conforming step sizes are rejected."""
    engine = RunoffEngine(
        cell_areas_m2={"C00001": 100.0},
        expected_timestep_seconds=60,
    )

    engine.process_timestep(60, 5.0)

    # 1. Reject duplicate timestamp
    with pytest.raises(ValueError, match="strictly greater"):
        engine.process_timestep(60, 5.0)

    # 2. Reject backwards timestamp
    with pytest.raises(ValueError, match="strictly greater"):
        engine.process_timestep(30, 5.0)

    # 3. Reject non-matching step size (e.g. 180s instead of expected 60s step from 60s)
    with pytest.raises(ValueError, match="Timestep spacing"):
        engine.process_timestep(180, 5.0)


def test_layer3_rainfall_replay_integration():
    """
    End-to-end integration: Replays storm_01.json (2, 4, 6 mm) directly into RunoffEngine
    and verifies cumulative rainfall progresses 2 -> 6 -> 12 mm.
    """
    replay = load_rainfall_replay("data/replay/rainfall/storm_01.json")
    engine = RunoffEngine(
        cell_areas_m2={"C00001": 100.0},
        default_cn=90.0,
        expected_timestep_seconds=60,
    )

    runoff_steps = []
    for step in replay.replay():
        r_step = engine.process_replay_step(step)
        runoff_steps.append(r_step)

    assert len(runoff_steps) == 3
    cum_p = [s.cell_states["C00001"].cumulative_rainfall_mm for s in runoff_steps]
    assert cum_p == [2.0, 6.0, 12.0]

    # Verify cumulative mass balance
    bal = engine.mass_balance()
    # Total rain: 12 mm on 100 m² = 1.2 m³
    assert math.isclose(bal["cumulative_rainfall_volume_m3"], 1.2)
    assert bal["is_conserved"] is True


def test_cn_monotonicity_sanity():
    """Verifies that under identical precipitation, higher CN produces higher runoff: Q_70 < Q_85 < Q_95."""
    engine = RunoffEngine(
        cell_areas_m2={
            "C00001": 100.0,
            "C00002": 100.0,
            "C00003": 100.0,
        },
        curve_numbers={
            "C00001": 70.0,
            "C00002": 85.0,
            "C00003": 95.0,
        },
        expected_timestep_seconds=60,
    )

    step = engine.process_timestep(60, 25.0)
    q_70 = step.cell_states["C00001"].cumulative_runoff_mm
    q_85 = step.cell_states["C00002"].cumulative_runoff_mm
    q_95 = step.cell_states["C00003"].cumulative_runoff_mm

    assert q_70 < q_85 < q_95


def test_rainfall_and_area_physical_sanity():
    """Verifies that higher rainfall -> higher Q, larger area -> larger volume, 0 rain -> 0 Q."""
    engine = RunoffEngine(
        cell_areas_m2={
            "C_SMALL": 100.0,
            "C_LARGE": 500.0,
        },
        default_cn=90.0,
        expected_timestep_seconds=60,
    )

    # Step 1: 0 mm rain
    s1 = engine.process_timestep(60, 0.0)
    assert s1.cell_states["C_SMALL"].incremental_runoff_mm == 0.0
    assert s1.cell_states["C_SMALL"].runoff_volume_m3 == 0.0

    # Step 2: 20 mm rain
    s2 = engine.process_timestep(120, 20.0)
    v_small = s2.cell_states["C_SMALL"].runoff_volume_m3
    v_large = s2.cell_states["C_LARGE"].runoff_volume_m3

    assert v_small > 0.0
    # Larger area produces proportionally larger volume
    assert math.isclose(v_large, 5.0 * v_small, rel_tol=1e-4)


def test_mass_balance_conservation():
    """Verifies that total direct runoff volume <= total gross precipitation volume."""
    engine = RunoffEngine(
        cell_areas_m2={"C00001": 100.0, "C00002": 200.0},
        default_cn=85.0,
        expected_timestep_seconds=60,
    )

    for i in range(1, 6):
        engine.process_timestep(i * 60, 15.0)

    bal = engine.mass_balance()
    assert bal["is_conserved"] is True
    assert bal["cumulative_direct_runoff_volume_m3"] <= bal["cumulative_rainfall_volume_m3"]
    assert math.isclose(
        bal["cumulative_rainfall_volume_m3"],
        bal["cumulative_direct_runoff_volume_m3"] + bal["cumulative_non_runoff_volume_m3"],
        rel_tol=1e-5,
    )


def test_event_reset_isolation():
    """Verifies that reset() ensures Storm B does not inherit rainfall or runoff state from Storm A."""
    engine = RunoffEngine(
        cell_areas_m2={"C00001": 100.0},
        default_cn=85.0,
        expected_timestep_seconds=60,
    )

    # Storm A: heavy rainfall
    engine.process_timestep(60, 30.0)
    engine.process_timestep(120, 20.0)
    assert engine.cumulative_rainfall_mm["C00001"] == 50.0
    assert engine.cumulative_runoff_mm["C00001"] > 0.0

    # Reset
    engine.reset()
    assert engine.cumulative_rainfall_mm["C00001"] == 0.0
    assert engine.cumulative_runoff_mm["C00001"] == 0.0
    assert engine.last_timestamp_seconds is None

    # Storm B: fresh start with 0 mm
    step_b = engine.process_timestep(60, 0.0)
    assert step_b.cell_states["C00001"].cumulative_rainfall_mm == 0.0
    assert step_b.cell_states["C00001"].cumulative_runoff_mm == 0.0
    assert step_b.cell_states["C00001"].runoff_volume_m3 == 0.0


def test_spatial_rainfall_and_coverage():
    """Verifies spatial rainfall processing, unknown cell rejection, and missing cell detection."""
    engine = RunoffEngine(
        cell_areas_m2={"C00001": 100.0, "C00002": 100.0},
        expected_timestep_seconds=60,
    )

    # Unknown cell rejection
    with pytest.raises(ValueError, match="Unknown cell ID 'C99999'"):
        engine.process_timestep(60, {"C00001": 5.0, "C00002": 5.0, "C99999": 5.0})

    # Missing cell detection
    with pytest.raises(ValueError, match="Missing rainfall input"):
        engine.process_timestep(60, {"C00001": 5.0})  # Missing C00002

    # Valid spatial step
    s = engine.process_timestep(60, {"C00001": 10.0, "C00002": 15.0})
    assert s.cell_states["C00001"].cumulative_rainfall_mm == 10.0
    assert s.cell_states["C00002"].cumulative_rainfall_mm == 15.0


def test_from_cell_properties_file():
    """Verifies loading spatial Curve Numbers and land-use metadata from JSON file."""
    engine = RunoffEngine.from_cell_properties_file("data/grid/cell_hydrology_v1.json")

    assert "C00001" in engine.curve_numbers
    assert engine.curve_numbers["C00001"] == 92.0
    assert engine.land_uses["C00001"] == "dense_urban"

    assert engine.curve_numbers["C00002"] == 88.0
    assert engine.land_uses["C00002"] == "residential"

    assert engine.curve_numbers["C00003"] == 95.0
    assert engine.land_uses["C00003"] == "road_or_highly_impervious"
