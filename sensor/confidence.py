"""
Composite confidence scoring: coverage, freshness, and windowed agreement.
"""

from typing import List
import numpy as np


def compute_confidence_score(
    sensor_coverage: float,
    freshness: float,
    recent_errors_window: List[float],
    wc: float = 0.3,
    wf: float = 0.2,
    wa: float = 0.5,
    e_max_cm: float = 20.0,
) -> float:
    """
    Computes normalized confidence score C in [0.0, 1.0] from:
    - coverage: fraction of online sensor nodes
    - freshness: time freshness metric
    - agreement: A_s = clip(1 - MAE / E_max, 0, 1) over window of N timesteps
    """
    if recent_errors_window:
        mae = float(np.mean(np.abs(recent_errors_window)))
        agreement = float(np.clip(1.0 - (mae / e_max_cm), 0.0, 1.0))
    else:
        # If no sensors / no recent readings, default baseline model agreement
        agreement = 0.5

    c = (
        wc * float(np.clip(sensor_coverage, 0.0, 1.0))
        + wf * float(np.clip(freshness, 0.0, 1.0))
        + wa * float(np.clip(agreement, 0.0, 1.0))
    )

    return float(np.clip(c, 0.0, 1.0))
