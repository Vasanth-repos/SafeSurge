"""
Layer 10 — Flood Risk Classification Unit Tests:
Verifies exact risk boundary thresholds, invalid input rejections, timing validations,
profile preservation, data status tracking, and serialization.
"""


import pytest

from flood_engine.risk import (
    DataSource,
    DataStatus,
    RiskProfile,
    RiskState,
    RiskThresholds,
    classify_depth,
    classify_location,
    load_risk_profile,
    serialize_risk,
)


@pytest.fixture
def profile():
    return RiskProfile(
        profile_id="prototype_v1",
        description="Prototype depth classifications for hackathon visualization.",
        unit="cm",
        thresholds=RiskThresholds(
            watch_cm=5.0,
            high_cm=15.0,
            unsafe_cm=25.0,
        ),
    )


def test_zero_depth_safe(profile):
    """Verifies 0.0 cm is SAFE."""
    assert classify_depth(0.0, profile) == RiskState.SAFE


def test_exact_boundaries(profile):
    """Verifies exact threshold transitions at 5.0, 15.0, and 25.0 cm."""
    assert classify_depth(4.999, profile) == RiskState.SAFE
    assert classify_depth(5.0, profile) == RiskState.WATCH
    assert classify_depth(14.999, profile) == RiskState.WATCH
    assert classify_depth(15.0, profile) == RiskState.HIGH
    assert classify_depth(24.999, profile) == RiskState.HIGH
    assert classify_depth(25.0, profile) == RiskState.UNSAFE
    assert classify_depth(40.0, profile) == RiskState.UNSAFE


def test_negative_depth_rejected(profile):
    """Verifies rejection of negative depth values."""
    with pytest.raises(ValueError, match="cannot be negative"):
        classify_depth(-0.1, profile)


def test_nan_and_infinite_depth_rejected(profile):
    """Verifies rejection of NaN and infinite depths."""
    with pytest.raises(ValueError, match="finite"):
        classify_depth(float("nan"), profile)
    with pytest.raises(ValueError, match="finite"):
        classify_depth(float("inf"), profile)


def test_invalid_threshold_order():
    """Verifies rejection of thresholds not strictly satisfying watch < high < unsafe."""
    with pytest.raises(ValueError, match="watch < high < unsafe"):
        RiskThresholds(watch_cm=15.0, high_cm=10.0, unsafe_cm=25.0)
    with pytest.raises(ValueError, match="watch < high < unsafe"):
        RiskThresholds(watch_cm=5.0, high_cm=25.0, unsafe_cm=20.0)


def test_negative_threshold_rejected():
    """Verifies rejection of negative watch threshold."""
    with pytest.raises(ValueError, match="watch_cm must be >= 0"):
        RiskThresholds(watch_cm=-1.0, high_cm=10.0, unsafe_cm=20.0)


def test_none_depth_returns_no_data(profile):
    """Verifies missing depth results in NO_DATA status and null risk_state."""
    result = classify_location(
        location_id="C104",
        depth_cm=None,
        reference_time_seconds=0,
        valid_time_seconds=600,
        profile=profile,
    )
    assert result.risk_state is None
    assert result.data_status == DataStatus.NO_DATA
    assert result.lead_time_seconds == 600
    assert result.risk_profile_id == "prototype_v1"


def test_forecast_lead_times(profile):
    """Verifies current and forecast lead time calculations."""
    # Current (lead = 0)
    res_now = classify_location("C104", 18.4, 600, 600, profile)
    assert res_now.lead_time_seconds == 0
    assert res_now.risk_state == RiskState.HIGH
    assert res_now.data_status == DataStatus.VALID

    # Forecast +30 min (lead = 1800s)
    res_future = classify_location("C104", 18.4, 600, 2400, profile)
    assert res_future.lead_time_seconds == 1800
    assert res_future.risk_state == RiskState.HIGH


def test_invalid_time_rejection(profile):
    """Verifies rejection when valid_time precedes reference_time."""
    with pytest.raises(ValueError, match="cannot precede"):
        classify_location("C104", 18.4, 1000, 500, profile)


def test_profile_preservation_and_serialization(profile):
    """Verifies full serialization contract."""
    res = classify_location("C104", 18.4, 0, 600, profile, source=DataSource.MODEL)
    serialized = serialize_risk(res)

    assert serialized["location_id"] == "C104"
    assert serialized["reference_time_seconds"] == 0
    assert serialized["valid_time_seconds"] == 600
    assert serialized["lead_time_seconds"] == 600
    assert serialized["depth_cm"] == pytest.approx(18.4)
    assert serialized["risk_state"] == "HIGH"
    assert serialized["data_status"] == "VALID"
    assert serialized["source"] == "MODEL"
    assert serialized["risk_profile_id"] == "prototype_v1"


def test_load_risk_profile_from_config():
    """Verifies loading from dict matching config.yaml structure."""
    cfg = {
        "risk": {
            "threshold_profile": {
                "id": "prototype_v1",
                "type": "PROTOTYPE",
                "unit": "cm",
                "description": "Standard test profile",
                "thresholds": {"watch": 5.0, "high": 15.0, "unsafe": 25.0},
            }
        }
    }
    p = load_risk_profile(cfg)
    assert p.profile_id == "prototype_v1"
    assert p.thresholds.watch_cm == 5.0
    assert p.thresholds.high_cm == 15.0
    assert p.thresholds.unsafe_cm == 25.0
