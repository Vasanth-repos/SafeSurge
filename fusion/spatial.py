"""
Layer 14 — Spatial Bias Correction & Inverse-Distance Weighting:
Interpolates local sensor residual biases spatially across the 2D computational domain
using freshness, quality, and distance decay, with dry-cell and radius bounds.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from fusion.models import SensorBiasState


def calculate_freshness(age_seconds: float, max_age_seconds: float = 180.0) -> float:
    """F = clip(1 - age / T_max, 0, 1)"""
    if age_seconds < 0:
        return 0.0
    if max_age_seconds <= 0:
        return 1.0 if age_seconds == 0 else 0.0
    return max(0.0, min(1.0, 1.0 - (float(age_seconds) / float(max_age_seconds))))


class SpatialBiasCorrector:
    def __init__(
        self,
        power: float = 2.0,
        max_distance_m: float = 1000.0,
        max_absolute_correction_cm: float = 15.0,
        minimum_model_depth_for_spatial_correction_cm: float = 1.0,
        max_sensor_age_seconds: float = 180.0,
        epsilon: float = 1e-6,
    ):
        self.power = float(power)
        self.max_distance_m = float(max_distance_m)
        self.max_absolute_correction_cm = float(max_absolute_correction_cm)
        self.minimum_model_depth_for_spatial_correction_cm = float(minimum_model_depth_for_spatial_correction_cm)
        self.max_sensor_age_seconds = float(max_sensor_age_seconds)
        self.epsilon = float(epsilon)

    def calculate_cell_correction(
        self,
        cell_id: str,
        cell_model_depth_cm: float,
        cell_coords_m: tuple[float, float],
        sensor_states: Mapping[str, SensorBiasState],
        sensor_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_health_by_id: Mapping[str, str],
        sensor_qualities_by_id: Mapping[str, float],
        current_timestamp_seconds: int,
        sensor_cell_id_by_id: Mapping[str, str] | None = None,
    ) -> float:
        """
        Calculates spatial correction C_i for a single computational cell.
        """
        cx, cy = cell_coords_m

        # Filter eligible sensors
        weights = []
        biases = []

        for sid, state in sensor_states.items():
            if not state.is_eligible or state.last_updated_seconds is None:
                continue

            health = sensor_health_by_id.get(sid, "OFFLINE")
            if health != "ONLINE":
                # OFFLINE / STALE / INVALID sensors have zero live spatial propagation
                continue

            if sid not in sensor_coords_m_by_id:
                continue

            sx, sy = sensor_coords_m_by_id[sid]
            dist_m = math.hypot(cx - sx, cy - sy)

            # Exact colocated sensor cell
            is_colocated = (
                (sensor_cell_id_by_id and sensor_cell_id_by_id.get(sid) == cell_id)
                or dist_m <= self.epsilon
            )
            if is_colocated:
                return max(
                    -self.max_absolute_correction_cm,
                    min(self.max_absolute_correction_cm, state.bias_cm),
                )

            if dist_m > self.max_distance_m:
                continue

            age_s = max(0, current_timestamp_seconds - state.last_updated_seconds)
            freshness = calculate_freshness(age_s, self.max_sensor_age_seconds)
            if freshness <= 0.0:
                continue

            quality = float(sensor_qualities_by_id.get(sid, 1.0))
            w = (freshness * quality) / ((dist_m + self.epsilon) ** self.power)
            weights.append(w)
            biases.append(state.bias_cm)

        if not weights:
            return 0.0

        # Dry-cell protection: do not spread non-colocated bias to dry ground
        if cell_model_depth_cm < self.minimum_model_depth_for_spatial_correction_cm:
            return 0.0

        weight_sum = sum(weights)
        if weight_sum <= self.epsilon:
            return 0.0

        raw_correction = sum(w * b for w, b in zip(weights, biases)) / weight_sum
        return max(
            -self.max_absolute_correction_cm,
            min(self.max_absolute_correction_cm, raw_correction),
        )

    def correct_grid(
        self,
        model_depth_cm_by_cell: Mapping[str, float],
        cell_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_states: Mapping[str, SensorBiasState],
        sensor_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_health_by_id: Mapping[str, str],
        sensor_qualities_by_id: Mapping[str, float],
        current_timestamp_seconds: int,
        sensor_cell_id_by_id: Mapping[str, str] | None = None,
    ) -> dict[str, tuple[float, float]]:
        """
        Returns {cell_id: (correction_cm, corrected_depth_cm)} for every cell.
        """
        results = {}
        for cid, model_d in model_depth_cm_by_cell.items():
            coords = cell_coords_m_by_id.get(cid, (0.0, 0.0))
            corr = self.calculate_cell_correction(
                cell_id=cid,
                cell_model_depth_cm=model_d,
                cell_coords_m=coords,
                sensor_states=sensor_states,
                sensor_coords_m_by_id=sensor_coords_m_by_id,
                sensor_health_by_id=sensor_health_by_id,
                sensor_qualities_by_id=sensor_qualities_by_id,
                current_timestamp_seconds=current_timestamp_seconds,
                sensor_cell_id_by_id=sensor_cell_id_by_id,
            )
            corrected = max(0.0, model_d + corr)
            results[cid] = (corr, corrected)
        return results
