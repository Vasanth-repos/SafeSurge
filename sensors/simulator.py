"""
Layer 11-12 — Sensor Simulator & Dataset Replay Engine:
Parses sensor replay JSON files and generates structured SensorEnvelope packets.
"""

from __future__ import annotations

from typing import List, Dict, Any, Union
from pathlib import Path
import json
from sensors.models import SensorEnvelope


def load_sensor_replay(path: Union[str, Path]) -> List[SensorEnvelope]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Sensor replay file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    sensor_id = str(data.get("sensor_id", "S001"))
    boot_id = str(data.get("boot_id", "boot-001"))

    envelopes = []
    for rd in data.get("readings", []):
        t_meas = int(rd.get("measured_at_seconds", 0))
        t_recv = int(rd.get("received_at_seconds", t_meas + 1))
        samples = tuple(rd.get("distance_samples_cm", []))
        float_trig = rd.get("float_triggered", None)

        env = SensorEnvelope(
            sensor_id=sensor_id,
            boot_id=boot_id,
            sequence=int(rd.get("sequence", 1)),
            measured_at_seconds=t_meas,
            received_at_seconds=t_recv,
            distance_samples_cm=samples,
            float_triggered=float_trig,
        )
        envelopes.append(env)

    return envelopes
