"""
Layer 15 — Multi-Criteria Confidence & Trust Estimator:
Computes transparent, anti-circular confidence scores [0, 1] based on:
1. Spatial Coverage (distance decay to nearest sensor)
2. Telemetry Freshness (time latency decay)
3. Historical Agreement (Mean Absolute Error against ORIGINAL MODEL depth)
4. Evidence History Factor (warm-up scaling factor)
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from fusion.history import SensorHistoryTracker
from fusion.models import CellConfidence, ObservationHistoryRecord
from fusion.spatial import calculate_freshness


def calculate_coverage(distance_m: float, max_distance_m: float = 1000.0) -> float:
    """C_c = clip(1 - d_nearest / D_max, 0, 1)"""
    if distance_m < 0 or max_distance_m <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (float(distance_m) / float(max_distance_m))))


def calculate_agreement(
    history_records: list[ObservationHistoryRecord],
    scale_cm: float = 20.0,
    minimum_observations: int = 5,
) -> tuple[float, int]:
    """
    Computes agreement against ORIGINAL model depth:
    MAE = (1/N) * sum(|H_sensor - H_ORIGINAL_model|)
    C_a = clip(1 - MAE / scale_cm, 0, 1)

    If observations < minimum_observations:
        returns (0.0, N) to conservatively reflect unverified agreement.
    """
    n = len(history_records)
    if n < minimum_observations or scale_cm <= 0:
        return 0.0, n

    # Anti-circularity guarantee: uses record.model_depth_cm (original model)
    mae = sum(abs(rec.observed_depth_cm - rec.model_depth_cm) for rec in history_records) / n
    agreement = max(0.0, min(1.0, 1.0 - (mae / scale_cm)))
    return float(agreement), n


def calculate_history_factor(
    observation_count: int,
    target_count: int = 10,
) -> float:
    """H = clip(N / N_target, 0, 1)"""
    if target_count <= 0 or observation_count <= 0:
        return 0.0
    return max(0.0, min(1.0, float(observation_count) / float(target_count)))


class ConfidenceEstimator:
    def __init__(
        self,
        weight_coverage: float = 0.30,
        weight_freshness: float = 0.30,
        weight_agreement: float = 0.40,
        max_distance_m: float = 1000.0,
        max_sensor_age_seconds: float = 180.0,
        agreement_scale_cm: float = 20.0,
        minimum_agreement_observations: int = 5,
        target_history_observations: int = 10,
    ):
        self.w_c = float(weight_coverage)
        self.w_f = float(weight_freshness)
        self.w_a = float(weight_agreement)

        self.max_distance_m = float(max_distance_m)
        self.max_sensor_age_seconds = float(max_sensor_age_seconds)
        self.agreement_scale_cm = float(agreement_scale_cm)
        self.minimum_agreement_observations = int(minimum_agreement_observations)
        self.target_history_observations = int(target_history_observations)

    def estimate_cell_confidence(
        self,
        cell_id: str,
        cell_coords_m: tuple[float, float],
        sensor_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_health_by_id: Mapping[str, str],
        sensor_last_updated_by_id: Mapping[str, int],
        history_tracker: SensorHistoryTracker,
        current_timestamp_seconds: int,
    ) -> CellConfidence:
        """
        Estimates multi-factor confidence for a given cell.
        """
        cx, cy = cell_coords_m

        # Find closest valid sensor
        nearest_sid: str | None = None
        min_dist_m: float = float("inf")

        for sid, (sx, sy) in sensor_coords_m_by_id.items():
            health = sensor_health_by_id.get(sid, "OFFLINE")
            if health not in ("ONLINE", "STALE"):
                continue

            dist = math.hypot(cx - sx, cy - sy)
            if dist < min_dist_m:
                min_dist_m = dist
                nearest_sid = sid

        if nearest_sid is None or min_dist_m > self.max_distance_m:
            # No nearby sensor -> confidence = 0
            return CellConfidence(
                cell_id=cell_id,
                score=0.0,
                coverage=0.0,
                freshness=0.0,
                agreement=0.0,
                history_factor=0.0,
                nearest_sensor_id=None,
                sensor_age_seconds=None,
                agreement_observation_count=0,
            )

        # 1. Coverage
        c_cov = calculate_coverage(min_dist_m, self.max_distance_m)

        # 2. Freshness
        t_last = sensor_last_updated_by_id.get(nearest_sid, current_timestamp_seconds)
        age_s = max(0, current_timestamp_seconds - t_last)
        c_fresh = calculate_freshness(age_s, self.max_sensor_age_seconds)

        # 3. Agreement & History
        history = history_tracker.get_history(nearest_sid)
        c_agree, n_obs = calculate_agreement(
            history_records=history,
            scale_cm=self.agreement_scale_cm,
            minimum_observations=self.minimum_agreement_observations,
        )
        h_factor = calculate_history_factor(n_obs, self.target_history_observations)

        # 4. Base & Final Confidence
        c_base = (self.w_c * c_cov) + (self.w_f * c_fresh) + (self.w_a * c_agree)
        c_final = max(0.0, min(1.0, c_base * h_factor))

        return CellConfidence(
            cell_id=cell_id,
            score=c_final,
            coverage=c_cov,
            freshness=c_fresh,
            agreement=c_agree,
            history_factor=h_factor,
            nearest_sensor_id=nearest_sid,
            sensor_age_seconds=age_s,
            agreement_observation_count=n_obs,
        )

    def estimate_grid(
        self,
        cell_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_health_by_id: Mapping[str, str],
        sensor_last_updated_by_id: Mapping[str, int],
        history_tracker: SensorHistoryTracker,
        current_timestamp_seconds: int,
    ) -> dict[str, CellConfidence]:
        return {
            cid: self.estimate_cell_confidence(
                cell_id=cid,
                cell_coords_m=coords,
                sensor_coords_m_by_id=sensor_coords_m_by_id,
                sensor_health_by_id=sensor_health_by_id,
                sensor_last_updated_by_id=sensor_last_updated_by_id,
                history_tracker=history_tracker,
                current_timestamp_seconds=current_timestamp_seconds,
            )
            for cid, coords in cell_coords_m_by_id.items()
        }
