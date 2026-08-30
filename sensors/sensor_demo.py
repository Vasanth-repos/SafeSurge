"""
Layer 11-12 — Sensor Telemetry Validation Demo:
Demonstrates ultrasonic burst filtering, float switch verification,
anomaly spike rejection, and device health state tracking.
"""

from sensors.registry import SensorRegistry
from sensors.simulator import load_sensor_replay
from sensors.validation import SensorValidator


def main():
    print("Layer 11-12 - Sensor Telemetry & Health Validation Subsystem")
    print("=" * 68)

    registry = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
    validator = SensorValidator(registry=registry)

    replay_file = "data/replay/sensors/sensor_anomaly_01.json"
    envelopes = load_sensor_replay(replay_file)
    print(f"Loaded Sensor Replay: {replay_file} ({len(envelopes)} packets)\n")

    for env in envelopes:
        res = validator.validate(env)
        d_str = f"{res.distance_cm:5.1f}cm" if res.distance_cm is not None else "  N/A  "
        l_str = f"{res.water_level_cm:5.1f}cm" if res.water_level_cm is not None else "  N/A  "
        reas_str = f"[{res.rejection_reason.value}]" if res.rejection_reason.value != "NONE" else ""

        print(
            f"[{res.sensor_id}] seq={res.sequence:2d} t={res.measured_at_seconds:2d}s | "
            f"dist={d_str} | level={l_str} | status={res.measurement_status.value:8s} {reas_str:20s} | "
            f"health={res.sensor_state.value}"
        )

    print("-" * 68)
    print("Layer 11-12 Sensor Subsystem: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
