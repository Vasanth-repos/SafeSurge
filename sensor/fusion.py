"""
Sensor data fusion: exponential smoothing bias correction and spatial IDW propagation.
"""

import math


def update_sensor_bias(
    predicted_depth_cm: float,
    observed_depth_cm: float,
    prev_bias: float = 0.0,
    alpha: float = 0.3,
) -> tuple[float, float]:
    """
    Computes new bias: new_bias = alpha * (observed - predicted) + (1 - alpha) * prev_bias
    Returns (new_bias, raw_error).
    """
    error = observed_depth_cm - predicted_depth_cm
    new_bias = alpha * error + (1.0 - alpha) * prev_bias
    return new_bias, error


def propagate_spatial_bias(
    target_pos: tuple[int, int],
    active_sensor_biases: dict[int, float],
    sensor_positions: dict[int, tuple[int, int]],
    cell_size_m: float = 10.0,
) -> float:
    """
    Propagates sensor biases across the catchment using Inverse Distance Weighting (IDW):
    w_i = 1 / (1 + distance_m)
    """
    if not active_sensor_biases:
        return 0.0

    r_target, c_target = target_pos
    weights_sum = 0.0
    weighted_bias = 0.0

    for sid, bias in active_sensor_biases.items():
        if sid not in sensor_positions:
            continue
        sr, sc = sensor_positions[sid]
        dist_cells = math.sqrt((r_target - sr) ** 2 + (c_target - sc) ** 2)
        dist_m = dist_cells * cell_size_m

        w = 1.0 / (1.0 + dist_m)
        weighted_bias += w * bias
        weights_sum += w

    if weights_sum > 0.0:
        return weighted_bias / weights_sum
    return 0.0


def apply_fused_depth_correction(predicted_depth_cm: float, bias_cm: float) -> float:
    """
    Applies calibrated bias to predicted depth while maintaining physical non-negativity.
    """
    return max(0.0, predicted_depth_cm + bias_cm)
