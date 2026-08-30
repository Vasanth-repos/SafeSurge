"""
Sensor and hydrological anomaly detection.
"""


from sensor.health import SensorNode


def detect_sensor_anomalies(
    sensor: SensorNode,
    model_predicted_depth_cm: float,
    prev_reading_cm: float | None,
    dt_seconds: float = 60.0,
    r_critical_cm_min: float = 5.0,
    tau_disagreement_cm: float = 10.0,
    drain_capacity_factor: float = 1.0,
) -> list[str]:
    """
    Detects sensor spikes, physical rate anomalies, model disagreements,
    sensor/float inconsistencies, and drainage capacity anomalies.
    """
    flags: list[str] = []

    if sensor.last_reading_cm is None:
        return ["NORMAL"]

    # 1. Check rapid rise
    if prev_reading_cm is not None:
        dt_min = max(dt_seconds / 60.0, 0.01)
        rate = abs(sensor.last_reading_cm - prev_reading_cm) / dt_min
        if rate > r_critical_cm_min:
            flags.append("RAPID_RISE")

    # 2. Check model-sensor disagreement
    disagreement = abs(sensor.last_reading_cm - model_predicted_depth_cm)
    if disagreement > tau_disagreement_cm:
        flags.append("MODEL_DISAGREEMENT")

    # 3. Check sensor/float inconsistency
    if sensor.float_state and sensor.last_reading_cm < 2.0 and sensor.last_quality_flag == "VALID" or not sensor.float_state and sensor.last_reading_cm > 40.0:
        flags.append("SENSOR_INCONSISTENCY")

    # 4. Correlate with drainage condition
    if ("RAPID_RISE" in flags or "MODEL_DISAGREEMENT" in flags) and drain_capacity_factor < 0.7:
        # Never say "detected blockage"
        flags.append("POSSIBLE_CAPACITY_ANOMALY")

    if not flags:
        flags.append("NORMAL")

    return flags
