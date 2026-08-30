"""
Sensor reading validation: physical range, spike/rate-of-rise, and heartbeat checks.
"""



def validate_sensor_reading(
    water_level_cm: float,
    prev_water_level_cm: float | None,
    dt_seconds: float = 60.0,
    r_critical_cm_min: float = 5.0,
    min_cm: float = 0.0,
    max_physical_depth_cm: float = 300.0,
    heartbeat: bool = True,
) -> str:
    """
    Validates a raw sensor telemetry reading.
    Returns quality flag: 'VALID', 'OUT_OF_RANGE', 'RATE_SPIKE', or 'MISSING_HEARTBEAT'.
    """
    if not heartbeat:
        return "MISSING_HEARTBEAT"

    if water_level_cm < min_cm or water_level_cm > max_physical_depth_cm:
        return "OUT_OF_RANGE"

    if prev_water_level_cm is not None:
        dt_minutes = max(dt_seconds / 60.0, 0.01)
        rate_of_rise_cm_min = abs(water_level_cm - prev_water_level_cm) / dt_minutes
        if rate_of_rise_cm_min > r_critical_cm_min:
            return "RATE_SPIKE"

    return "VALID"
