"""
Layer 17 — Road Depth & Confidence Exposure Aggregator:
Computes exposure-weighted mean flood depth, relevant maximum inundation depth,
affected road length fraction, and confidence metrics.
"""

from __future__ import annotations

from typing import List, Mapping, Optional, Sequence, Tuple
from roads.models import RoadCellExposure


def calculate_road_depth(
    exposures: Sequence[RoadCellExposure],
    cell_depths_by_id: Mapping[str, float],
    minimum_exposure_fraction: float = 0.10,
) -> Tuple[float, float, float]:
    """
    Computes:
    1. Exposure-weighted mean depth: H_mean = sum(f_i * H_i) / sum(f_i)
    2. Relevant maximum depth: max(H_i) for cells with f_i >= minimum_exposure_fraction
    3. Affected fraction: sum(f_i) for cells where H_i > 0

    Returns:
        (mean_depth_cm, max_relevant_depth_cm, affected_fraction)
    """
    if not exposures:
        return 0.0, 0.0, 0.0

    total_frac = sum(exp.exposure_fraction for exp in exposures)
    if total_frac <= 0.0:
        return 0.0, 0.0, 0.0

    weighted_depth_sum = 0.0
    affected_frac = 0.0
    relevant_depths = []

    for exp in exposures:
        d = float(cell_depths_by_id.get(exp.cell_id, 0.0))
        weighted_depth_sum += exp.exposure_fraction * d

        if d > 0.0:
            affected_frac += exp.exposure_fraction

        if exp.exposure_fraction >= minimum_exposure_fraction:
            relevant_depths.append(d)

    mean_depth = weighted_depth_sum / total_frac
    max_relevant = max(relevant_depths) if relevant_depths else (max(cell_depths_by_id.get(e.cell_id, 0.0) for e in exposures) if exposures else 0.0)

    return mean_depth, max_relevant, min(1.0, affected_frac)


def calculate_road_confidence(
    exposures: Sequence[RoadCellExposure],
    cell_confidences_by_id: Mapping[str, float],
) -> Tuple[float, float]:
    """
    Computes:
    1. Exposure-weighted confidence: C_road = sum(f_i * C_i) / sum(f_i)
    2. Minimum cell confidence across all intersecting cells.

    Returns:
        (weighted_confidence, min_confidence)
    """
    if not exposures:
        return 0.0, 0.0

    total_frac = sum(exp.exposure_fraction for exp in exposures)
    if total_frac <= 0.0:
        return 0.0, 0.0

    weighted_conf_sum = 0.0
    cell_confs = []

    for exp in exposures:
        c = float(cell_confidences_by_id.get(exp.cell_id, 0.0))
        weighted_conf_sum += exp.exposure_fraction * c
        cell_confs.append(c)

    weighted_conf = weighted_conf_sum / total_frac
    min_conf = min(cell_confs) if cell_confs else 0.0

    return weighted_conf, min_conf
