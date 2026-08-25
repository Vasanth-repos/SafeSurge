"""
Layer 17 — Road Risk Classification Engine:
Classifies aggregated road exposure depths into SAFE, WATCH, HIGH, UNSAFE states.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence
from roads.models import Road, RoadRisk, RoadCellExposure
from roads.exposure import calculate_road_depth, calculate_road_confidence


def classify_road_risk(
    depth_cm: float,
    watch_cm: float = 5.0,
    high_cm: float = 15.0,
    unsafe_cm: float = 25.0,
) -> str:
    """
    Classifies road flood risk based on depth:
    < watch_cm -> SAFE
    watch_cm .. high_cm -> WATCH
    high_cm .. unsafe_cm -> HIGH
    >= unsafe_cm -> UNSAFE
    """
    if depth_cm >= unsafe_cm:
        return "UNSAFE"
    if depth_cm >= high_cm:
        return "HIGH"
    if depth_cm >= watch_cm:
        return "WATCH"
    return "SAFE"


class RoadRiskEngine:
    def __init__(
        self,
        watch_cm: float = 5.0,
        high_cm: float = 15.0,
        unsafe_cm: float = 25.0,
        minimum_exposure_fraction: float = 0.10,
    ):
        self.watch_cm = float(watch_cm)
        self.high_cm = float(high_cm)
        self.unsafe_cm = float(unsafe_cm)
        self.min_exposure_frac = float(minimum_exposure_fraction)

    def evaluate_road(
        self,
        road_id: str,
        timestamp_seconds: int,
        exposures: Sequence[RoadCellExposure],
        cell_depths_by_id: Mapping[str, float],
        cell_confidences_by_id: Mapping[str, float],
    ) -> RoadRisk:
        mean_d, max_rel_d, aff_frac = calculate_road_depth(
            exposures=exposures,
            cell_depths_by_id=cell_depths_by_id,
            minimum_exposure_fraction=self.min_exposure_frac,
        )

        w_conf, min_conf = calculate_road_confidence(
            exposures=exposures,
            cell_confidences_by_id=cell_confidences_by_id,
        )

        # Classify risk using mean depth (or max relevant depth if significantly flooded)
        eval_depth = max(mean_d, max_rel_d * aff_frac)
        risk_level = classify_road_risk(
            depth_cm=eval_depth,
            watch_cm=self.watch_cm,
            high_cm=self.high_cm,
            unsafe_cm=self.unsafe_cm,
        )

        return RoadRisk(
            road_id=road_id,
            timestamp_seconds=timestamp_seconds,
            mean_depth_cm=mean_d,
            max_relevant_depth_cm=max_rel_d,
            affected_fraction=aff_frac,
            risk=risk_level,
            confidence=w_conf,
            minimum_cell_confidence=min_conf,
        )

    def evaluate_all(
        self,
        timestamp_seconds: int,
        exposures_by_road: Mapping[str, Sequence[RoadCellExposure]],
        cell_depths_by_id: Mapping[str, float],
        cell_confidences_by_id: Mapping[str, float],
    ) -> Dict[str, RoadRisk]:
        return {
            r_id: self.evaluate_road(
                road_id=r_id,
                timestamp_seconds=timestamp_seconds,
                exposures=exps,
                cell_depths_by_id=cell_depths_by_id,
                cell_confidences_by_id=cell_confidences_by_id,
            )
            for r_id, exps in exposures_by_road.items()
        }
