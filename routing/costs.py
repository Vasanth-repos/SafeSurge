"""
Layer 18 — Policy Routing Cost Calculator:
Computes policy travel impedance: Cost = TravelTime + RiskPenalty[risk] + mu * (1 - Confidence).
Blocks UNSAFE roads with infinite cost when unsafe_edges_blocked is enabled.
"""

from __future__ import annotations

from collections.abc import Mapping


def calculate_cost(
    travel_time_seconds: float,
    risk: str,
    confidence: float,
    risk_penalties: Mapping[str, float],
    uncertainty_weight: float = 120.0,
    unsafe_edges_blocked: bool = True,
) -> float:
    """
    Computes routing edge traversal cost:
    - If risk == 'UNSAFE' and unsafe_edges_blocked: return float('inf')
    - Cost = travel_time_seconds + risk_penalty + uncertainty_weight * (1.0 - confidence)
    """
    if risk == "UNSAFE" and unsafe_edges_blocked:
        return float("inf")

    if not (0.0 <= confidence <= 1.0):
        # Clip or raise if invalid
        confidence = max(0.0, min(1.0, float(confidence)))

    risk_penalty = float(risk_penalties.get(risk, 0.0))
    uncertainty = 1.0 - float(confidence)

    return float(travel_time_seconds) + risk_penalty + (float(uncertainty_weight) * uncertainty)
