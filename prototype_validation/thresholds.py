"""
Layer 26 — Invariant Thresholds & Tolerances:
Configurable physical limits and evaluation tolerances for prototype validation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationThresholds:
    # Mass Balance Tolerances
    mass_balance_absolute_tolerance_m3: float = 5.0
    mass_balance_relative_tolerance: float = 0.005

    # Storage & Depth Boundaries
    min_storage_tolerance_m3: float = -1e-6
    min_depth_tolerance_cm: float = -1e-6

    # Routing Invariants
    routing_fraction_max: float = 1.0
    routing_fraction_min: float = 0.0

    # Risk Boundaries (cm)
    risk_watch_cm: float = 5.0
    risk_high_cm: float = 15.0
    risk_unsafe_cm: float = 25.0

    # Sensor Disagreement Threshold (cm)
    sensor_disagreement_threshold_cm: float = 20.0

    # Timing Synchronicity (seconds)
    max_timestamp_drift_seconds: int = 0
