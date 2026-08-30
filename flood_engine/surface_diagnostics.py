"""
Layer 5 Surface Diagnostics:
Classifies surface flood depth into standard risk tiers without altering physical mass conservation.
"""

from typing import Any

import numpy as np

RISK_TIERS = [
    ("CRITICAL",  0.60),  # >= 60 cm
    ("SEVERE",    0.30),  # 30 - 60 cm
    ("HAZARDOUS", 0.15),  # 15 - 30 cm
    ("WARNING",   0.05),  # 5 - 15 cm
    ("NORMAL",    0.00),  # < 5 cm
]


def classify_depth_risk(depth_m: float) -> str:
    """Classifies water depth into risk tier."""
    d = float(depth_m)
    for name, threshold in RISK_TIERS:
        if d >= threshold:
            return name
    return "NORMAL"


def summarize_grid_depths(depths_by_cell: dict[str, float]) -> dict[str, Any]:
    """Generates statistical and risk category summaries across all computational cells."""
    if not depths_by_cell:
        return {
            "max_depth_m": 0.0,
            "mean_depth_m": 0.0,
            "flooded_cells_count": 0,
            "risk_counts": {name: 0 for name, _ in RISK_TIERS},
        }

    vals = list(depths_by_cell.values())
    risk_counts = {name: 0 for name, _ in RISK_TIERS}

    for d in vals:
        tier = classify_depth_risk(d)
        risk_counts[tier] += 1

    return {
        "max_depth_m": round(float(np.max(vals)), 4),
        "mean_depth_m": round(float(np.mean(vals)), 4),
        "flooded_cells_count": sum(1 for d in vals if d >= 0.05),
        "risk_counts": risk_counts,
    }
