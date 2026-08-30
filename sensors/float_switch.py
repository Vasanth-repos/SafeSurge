"""
Layer 11-12 — Float Switch Consistency Validation:
Validates binary contact closure consistency against continuous ultrasonic water level.
"""

from __future__ import annotations


def validate_float_consistency(
    water_level_cm: float | None,
    float_triggered: bool | None,
    trigger_level_cm: float,
    tolerance_cm: float = 3.0,
) -> bool:
    """
    Validates agreement between float switch state and continuous water level:
    - If float_triggered is None: No float data -> Consistent (True).
    - If water_level_cm is None: Cannot evaluate conflict -> Consistent (True).
    - If float_triggered == True: Water level must be >= (trigger_level_cm - tolerance_cm).
    - If float_triggered == False: Water level must be <= (trigger_level_cm + tolerance_cm).
    """
    if float_triggered is None or water_level_cm is None:
        return True

    lower_bound = trigger_level_cm - tolerance_cm
    upper_bound = trigger_level_cm + tolerance_cm

    if float_triggered:
        return water_level_cm >= lower_bound

    return water_level_cm <= upper_bound
