"""
Layer 11 — Ultrasonic Burst Echo Filtering:
Filters burst echo samples, eliminates non-finite & out-of-range echoes,
and aggregates representative distance using median calculation.
"""

from __future__ import annotations

from typing import Sequence, Tuple, Optional
import math
from statistics import median


def filter_echoes(
    samples: Sequence[Optional[float]],
    min_distance_cm: float,
    max_distance_cm: float,
    minimum_valid_samples: int,
) -> Tuple[Optional[float], int]:
    """
    Filters raw echo burst:
    1. Removes None and non-finite values.
    2. Validates against physical sensor distance bounds [min_distance_cm, max_distance_cm].
    3. Requires at least minimum_valid_samples valid readings.
    4. Computes median of valid samples to prevent spike bias.
    """
    valid = []
    for value in samples:
        if value is None:
            continue
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue

        if not math.isfinite(val):
            continue

        if min_distance_cm <= val <= max_distance_cm:
            valid.append(val)

    count = len(valid)
    if count < minimum_valid_samples:
        return None, count

    return float(median(valid)), count
