"""
Layer 13 — Sensor-to-Model Spatiotemporal Matching:
Matches validated sensor observations to computational cell model depths
and verifies temporal alignment tolerances.
"""

from __future__ import annotations

from collections.abc import Mapping

from fusion.models import SensorObservation


def match_sensor_to_model(
    observation: SensorObservation,
    model_depth_cm_by_cell: Mapping[str, float],
    model_timestamp_seconds: int,
    max_time_difference_seconds: int = 30,
) -> tuple[bool, float | None, float | None]:
    """
    Matches sensor observation to grid cell:
    1. Checks if observation.cell_id exists in model output.
    2. Checks |t_sensor - t_model| <= max_time_difference_seconds.
    3. Calculates residual: e = observed_depth_cm - model_depth_cm.

    Returns:
        (is_matched, model_depth_cm, residual_cm)
    """
    if observation.cell_id not in model_depth_cm_by_cell:
        return False, None, None

    dt = abs(observation.timestamp_seconds - model_timestamp_seconds)
    if dt > max_time_difference_seconds:
        return False, None, None

    model_depth = float(model_depth_cm_by_cell[observation.cell_id])
    residual = float(observation.observed_depth_cm - model_depth)
    return True, model_depth, residual
