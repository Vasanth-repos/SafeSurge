"""
Layer 11 — Sensor Registry:
Loads, parses, and validates per-sensor hardware configurations and geometry references.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any, Union
from pathlib import Path
import yaml


@dataclass(frozen=True)
class SensorConfig:
    sensor_id: str
    enabled: bool
    location_id: str
    reference_height_cm: float
    min_distance_cm: float
    max_distance_cm: float
    min_level_cm: float
    max_level_cm: float
    samples_per_measurement: int
    minimum_valid_samples: int
    float_enabled: bool
    float_trigger_level_cm: float
    float_tolerance_cm: float

    def __post_init__(self):
        if not self.sensor_id:
            raise ValueError("sensor_id is required.")
        if self.reference_height_cm <= 0:
            raise ValueError(f"reference_height_cm must be > 0, got {self.reference_height_cm}")
        if not (self.min_distance_cm < self.max_distance_cm):
            raise ValueError("min_distance_cm must be < max_distance_cm.")
        if not (self.min_level_cm < self.max_level_cm):
            raise ValueError("min_level_cm must be < max_level_cm.")
        if self.minimum_valid_samples <= 0 or self.minimum_valid_samples > self.samples_per_measurement:
            raise ValueError("minimum_valid_samples must be between 1 and samples_per_measurement.")


class SensorRegistry:
    def __init__(self, sensors: Optional[Dict[str, SensorConfig]] = None):
        self._sensors: Dict[str, SensorConfig] = dict(sensors) if sensors else {}

    def register(self, config: SensorConfig) -> None:
        self._sensors[config.sensor_id] = config

    def get(self, sensor_id: str) -> Optional[SensorConfig]:
        return self._sensors.get(sensor_id)

    def __contains__(self, sensor_id: str) -> bool:
        return sensor_id in self._sensors

    def __len__(self) -> int:
        return len(self._sensors)

    @classmethod
    def load_from_yaml(cls, path: Union[str, Path] = "data/sensors/registry.yaml") -> SensorRegistry:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Sensor registry file not found: {p}")

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        sensors_dict = {}
        for sid, sdata in data.get("sensors", {}).items():
            dist = sdata.get("distance", {})
            level = sdata.get("level", {})
            ultra = sdata.get("ultrasonic", {})
            fsw = sdata.get("float_switch", {})

            cfg = SensorConfig(
                sensor_id=str(sid),
                enabled=bool(sdata.get("enabled", True)),
                location_id=str(sdata.get("location_id", "")),
                reference_height_cm=float(sdata.get("reference_height_cm", 100.0)),
                min_distance_cm=float(dist.get("min_cm", 2.0)),
                max_distance_cm=float(dist.get("max_cm", 400.0)),
                min_level_cm=float(level.get("min_cm", 0.0)),
                max_level_cm=float(level.get("max_cm", 95.0)),
                samples_per_measurement=int(ultra.get("samples_per_measurement", 5)),
                minimum_valid_samples=int(ultra.get("minimum_valid_samples", 3)),
                float_enabled=bool(fsw.get("enabled", True)),
                float_trigger_level_cm=float(fsw.get("trigger_level_cm", 20.0)),
                float_tolerance_cm=float(fsw.get("tolerance_cm", 3.0)),
            )
            sensors_dict[sid] = cfg

        return cls(sensors_dict)
