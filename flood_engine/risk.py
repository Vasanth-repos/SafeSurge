"""
Layer 10 — Risk Classification & Spatial Forecast State Engine:
Classifies computed flood depths (cm) into configurable prototype risk states
(SAFE, WATCH, HIGH, UNSAFE) while preserving data quality, timing context, and source.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Mapping, Sequence, Dict, List, Optional, Tuple, Any, Union
import math
from pathlib import Path
import yaml


class RiskState(str, Enum):
    SAFE = "SAFE"
    WATCH = "WATCH"
    HIGH = "HIGH"
    UNSAFE = "UNSAFE"


class DataStatus(str, Enum):
    VALID = "VALID"
    NO_DATA = "NO_DATA"
    INVALID = "INVALID"


class DataSource(str, Enum):
    MODEL = "MODEL"
    SENSOR = "SENSOR"
    FUSED = "FUSED"


@dataclass(frozen=True)
class RiskThresholds:
    watch_cm: float
    high_cm: float
    unsafe_cm: float

    def __post_init__(self):
        values = (self.watch_cm, self.high_cm, self.unsafe_cm)
        for v in values:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("Risk thresholds must be numeric.")
            if not math.isfinite(float(v)):
                raise ValueError("Risk thresholds must be finite.")

        w = float(self.watch_cm)
        h = float(self.high_cm)
        u = float(self.unsafe_cm)

        if w < 0:
            raise ValueError("watch_cm must be >= 0.")

        if not (w < h < u):
            raise ValueError(f"Thresholds must satisfy watch < high < unsafe, got ({w}, {h}, {u}).")


@dataclass(frozen=True)
class RiskProfile:
    profile_id: str
    description: str
    unit: str
    thresholds: RiskThresholds
    profile_type: str = "PROTOTYPE"

    def __post_init__(self):
        if not self.profile_id:
            raise ValueError("profile_id is required.")

        if self.unit != "cm":
            raise ValueError(f"Risk thresholds must use cm, got '{self.unit}'.")

        allowed_types = {"PROTOTYPE", "RESEARCH", "CITY_SPECIFIC"}
        if self.profile_type not in allowed_types:
            raise ValueError(f"Invalid risk profile type: '{self.profile_type}'. Allowed: {sorted(allowed_types)}")


def load_risk_profile(config: Mapping[str, Any]) -> RiskProfile:
    risk_config = config.get("risk", {})
    profile_config = risk_config.get("threshold_profile", {})

    thresholds_config = profile_config.get("thresholds", {})
    thresholds = RiskThresholds(
        watch_cm=float(thresholds_config.get("watch", 5.0)),
        high_cm=float(thresholds_config.get("high", 15.0)),
        unsafe_cm=float(thresholds_config.get("unsafe", 25.0)),
    )

    return RiskProfile(
        profile_id=str(profile_config.get("id", "prototype_v1")),
        description=str(profile_config.get("description", "Prototype depth classifications")),
        unit=str(profile_config.get("unit", "cm")),
        thresholds=thresholds,
        profile_type=str(profile_config.get("type", "PROTOTYPE")),
    )


def load_risk_profile_from_yaml(config_path: Union[str, Path] = "config.yaml") -> RiskProfile:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Configuration file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return load_risk_profile(cfg)


def classify_depth(
    depth_cm: float,
    profile: RiskProfile,
) -> RiskState:
    if depth_cm is None:
        raise ValueError("Cannot classify None depth.")

    if isinstance(depth_cm, bool):
        raise ValueError("Depth must be numeric.")

    try:
        depth = float(depth_cm)
    except (TypeError, ValueError) as exc:
        raise ValueError("Depth must be numeric.") from exc

    if not math.isfinite(depth):
        raise ValueError("Depth must be finite.")

    if depth < 0:
        raise ValueError(f"Depth cannot be negative: {depth}")

    t = profile.thresholds
    if depth < t.watch_cm:
        return RiskState.SAFE
    if depth < t.high_cm:
        return RiskState.WATCH
    if depth < t.unsafe_cm:
        return RiskState.HIGH
    return RiskState.UNSAFE


def validate_times(
    reference_time_seconds: int,
    valid_time_seconds: int,
) -> int:
    if isinstance(reference_time_seconds, bool) or not isinstance(reference_time_seconds, int) or reference_time_seconds < 0:
        raise ValueError("Reference time must be an integer >= 0.")
    if isinstance(valid_time_seconds, bool) or not isinstance(valid_time_seconds, int) or valid_time_seconds < 0:
        raise ValueError("Valid time must be an integer >= 0.")
    if valid_time_seconds < reference_time_seconds:
        raise ValueError(
            f"Valid time ({valid_time_seconds}s) cannot precede reference time ({reference_time_seconds}s)."
        )
    return valid_time_seconds - reference_time_seconds


@dataclass(frozen=True)
class RiskResult:
    location_id: str
    reference_time_seconds: int
    valid_time_seconds: int
    lead_time_seconds: int
    depth_cm: Optional[float]
    risk_state: Optional[RiskState]
    data_status: DataStatus
    source: DataSource
    risk_profile_id: str


@dataclass(frozen=True)
class RoadRiskResult:
    road_id: str
    reference_time_seconds: int
    valid_time_seconds: int
    lead_time_seconds: int
    weighted_depth_cm: Optional[float]
    max_intersecting_cell_depth_cm: Optional[float]
    coverage_fraction: float
    coverage_status: str
    risk_state: Optional[RiskState]
    data_status: DataStatus
    source: DataSource
    risk_profile_id: str


def classify_location(
    location_id: str,
    depth_cm: Optional[float],
    reference_time_seconds: int,
    valid_time_seconds: int,
    profile: RiskProfile,
    source: DataSource = DataSource.MODEL,
) -> RiskResult:
    if not location_id:
        raise ValueError("location_id is required.")

    lead_time = validate_times(reference_time_seconds, valid_time_seconds)

    if depth_cm is None:
        return RiskResult(
            location_id=location_id,
            reference_time_seconds=reference_time_seconds,
            valid_time_seconds=valid_time_seconds,
            lead_time_seconds=lead_time,
            depth_cm=None,
            risk_state=None,
            data_status=DataStatus.NO_DATA,
            source=source,
            risk_profile_id=profile.profile_id,
        )

    state = classify_depth(depth_cm, profile)

    return RiskResult(
        location_id=location_id,
        reference_time_seconds=reference_time_seconds,
        valid_time_seconds=valid_time_seconds,
        lead_time_seconds=lead_time,
        depth_cm=float(depth_cm),
        risk_state=state,
        data_status=DataStatus.VALID,
        source=source,
        risk_profile_id=profile.profile_id,
    )


def classify_cell_depths(
    cell_depths: Mapping[str, Any],
    reference_time_seconds: int,
    profile: RiskProfile,
) -> Dict[str, RiskResult]:
    results = {}
    for cell_id, cd in cell_depths.items():
        v_time = int(getattr(cd, "timestamp_seconds", reference_time_seconds))
        d_val = getattr(cd, "depth_cm", None)
        src_str = getattr(cd, "source", "MODEL")
        try:
            src = DataSource(src_str)
        except ValueError:
            src = DataSource.MODEL

        results[cell_id] = classify_location(
            location_id=cell_id,
            depth_cm=d_val,
            reference_time_seconds=reference_time_seconds,
            valid_time_seconds=v_time,
            profile=profile,
            source=src,
        )
    return results


def classify_road_depths(
    road_depths: Mapping[str, Any],
    reference_time_seconds: int,
    profile: RiskProfile,
) -> Dict[str, RoadRiskResult]:
    results = {}
    for road_id, rd in road_depths.items():
        v_time = int(getattr(rd, "timestamp_seconds", reference_time_seconds))
        lead = validate_times(reference_time_seconds, v_time)
        w_depth = getattr(rd, "weighted_depth_cm", None)
        max_d = getattr(rd, "max_intersecting_cell_depth_cm", None)
        cov_frac = float(getattr(rd, "coverage_fraction", 0.0))
        cov_stat = str(getattr(rd, "coverage_status", "NO_COVERAGE"))
        src_str = getattr(rd, "source", "MODEL")
        try:
            src = DataSource(src_str)
        except ValueError:
            src = DataSource.MODEL

        if w_depth is None or cov_stat == "NO_COVERAGE":
            risk = None
            d_status = DataStatus.NO_DATA
        else:
            risk = classify_depth(w_depth, profile)
            d_status = DataStatus.VALID

        results[road_id] = RoadRiskResult(
            road_id=road_id,
            reference_time_seconds=reference_time_seconds,
            valid_time_seconds=v_time,
            lead_time_seconds=lead,
            weighted_depth_cm=w_depth,
            max_intersecting_cell_depth_cm=max_d,
            coverage_fraction=cov_frac,
            coverage_status=cov_stat,
            risk_state=risk,
            data_status=d_status,
            source=src,
            risk_profile_id=profile.profile_id,
        )
    return results


def serialize_risk(result: RiskResult) -> Dict[str, Any]:
    return {
        "location_id": result.location_id,
        "reference_time_seconds": result.reference_time_seconds,
        "valid_time_seconds": result.valid_time_seconds,
        "lead_time_seconds": result.lead_time_seconds,
        "depth_cm": round(result.depth_cm, 4) if result.depth_cm is not None else None,
        "risk_state": result.risk_state.value if result.risk_state else None,
        "data_status": result.data_status.value,
        "source": result.source.value,
        "risk_profile_id": result.risk_profile_id,
    }


def serialize_road_risk(result: RoadRiskResult) -> Dict[str, Any]:
    return {
        "road_id": result.road_id,
        "reference_time_seconds": result.reference_time_seconds,
        "valid_time_seconds": result.valid_time_seconds,
        "lead_time_seconds": result.lead_time_seconds,
        "weighted_depth_cm": round(result.weighted_depth_cm, 4) if result.weighted_depth_cm is not None else None,
        "max_intersecting_cell_depth_cm": (
            round(result.max_intersecting_cell_depth_cm, 4) if result.max_intersecting_cell_depth_cm is not None else None
        ),
        "coverage_fraction": round(result.coverage_fraction, 4),
        "coverage_status": result.coverage_status,
        "risk_state": result.risk_state.value if result.risk_state else None,
        "data_status": result.data_status.value,
        "source": result.source.value,
        "risk_profile_id": result.risk_profile_id,
    }


class RiskEngine:
    def __init__(
        self,
        profile: Optional[RiskProfile] = None,
        config: Optional[Mapping[str, Any]] = None,
    ):
        if profile is not None:
            self.profile = profile
        elif config is not None:
            self.profile = load_risk_profile(config)
        else:
            self.profile = load_risk_profile_from_yaml("config.yaml")

    def classify_cells(
        self,
        cell_depths: Mapping[str, Any],
        reference_time_seconds: int,
    ) -> Dict[str, RiskResult]:
        return classify_cell_depths(
            cell_depths=cell_depths,
            reference_time_seconds=reference_time_seconds,
            profile=self.profile,
        )

    def classify_roads(
        self,
        road_depths: Mapping[str, Any],
        reference_time_seconds: int,
    ) -> Dict[str, RoadRiskResult]:
        return classify_road_depths(
            road_depths=road_depths,
            reference_time_seconds=reference_time_seconds,
            profile=self.profile,
        )

    def classify(
        self,
        depth_result: Any,
        reference_time_seconds: int,
    ) -> Dict[str, Any]:
        cells = self.classify_cells(
            cell_depths=getattr(depth_result, "cells", {}),
            reference_time_seconds=reference_time_seconds,
        )
        roads = self.classify_roads(
            road_depths=getattr(depth_result, "roads", {}),
            reference_time_seconds=reference_time_seconds,
        )
        return {
            "reference_time_seconds": reference_time_seconds,
            "valid_time_seconds": getattr(depth_result, "timestamp_seconds", reference_time_seconds),
            "lead_time_seconds": validate_times(
                reference_time_seconds,
                getattr(depth_result, "timestamp_seconds", reference_time_seconds),
            ),
            "risk_profile_id": self.profile.profile_id,
            "cells": {cid: serialize_risk(cr) for cid, cr in cells.items()},
            "roads": {rid: serialize_road_risk(rr) for rid, rr in roads.items()},
        }
