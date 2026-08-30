"""
Layers 13–15 — Historical Observation Window Tracker:
Maintains chronological rolling windows of accepted (sensor, original model) pairs
for anti-circular agreement evaluation and historical sample weighting.
"""

from __future__ import annotations

from collections import deque

from fusion.models import ObservationHistoryRecord


class SensorHistoryTracker:
    def __init__(self, max_history_steps: int = 10):
        self.max_history_steps = max_history_steps
        self._history_by_sensor: dict[str, deque[ObservationHistoryRecord]] = {}

    def record_observation(
        self,
        sensor_id: str,
        timestamp_seconds: int,
        model_depth_cm: float,
        observed_depth_cm: float,
        residual_cm: float,
    ) -> None:
        if sensor_id not in self._history_by_sensor:
            self._history_by_sensor[sensor_id] = deque(maxlen=self.max_history_steps)

        record = ObservationHistoryRecord(
            timestamp_seconds=int(timestamp_seconds),
            model_depth_cm=float(model_depth_cm),
            observed_depth_cm=float(observed_depth_cm),
            residual_cm=float(residual_cm),
        )
        self._history_by_sensor[sensor_id].append(record)

    def get_history(self, sensor_id: str) -> list[ObservationHistoryRecord]:
        if sensor_id not in self._history_by_sensor:
            return []
        return list(self._history_by_sensor[sensor_id])

    def get_history_count(self, sensor_id: str) -> int:
        if sensor_id not in self._history_by_sensor:
            return 0
        return len(self._history_by_sensor[sensor_id])

    def reset(self) -> None:
        self._history_by_sensor.clear()
