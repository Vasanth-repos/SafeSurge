"""
Layer 12 — Sensor Health & Heartbeat State Machine:
Evaluates device communication health based on packet arrival age (ONLINE, STALE, OFFLINE, INVALID).
"""

from __future__ import annotations

from sensors.models import SensorState


def evaluate_sensor_health(
    now_received_seconds: int,
    last_received_seconds: int | None,
    stale_after_seconds: int = 30,
    offline_after_seconds: int = 180,
) -> SensorState:
    """
    Evaluates communication connectivity:
    - If never received: OFFLINE
    - If clock skewed (received in future vs now): INVALID
    - If age > offline_after_seconds: OFFLINE
    - If age > stale_after_seconds: STALE
    - Otherwise: ONLINE
    """
    if last_received_seconds is None:
        return SensorState.OFFLINE

    age = now_received_seconds - last_received_seconds
    if age < 0:
        return SensorState.INVALID

    if age > offline_after_seconds:
        return SensorState.OFFLINE

    if age > stale_after_seconds:
        return SensorState.STALE

    return SensorState.ONLINE


class SensorHealthTracker:
    def __init__(
        self,
        stale_after_seconds: int = 30,
        offline_after_seconds: int = 180,
    ):
        self.stale_after_seconds = stale_after_seconds
        self.offline_after_seconds = offline_after_seconds
        self._last_received_by_sensor: dict[str, int] = {}

    def record_heartbeat(self, sensor_id: str, received_at_seconds: int) -> None:
        self._last_received_by_sensor[sensor_id] = received_at_seconds

    def get_state(self, sensor_id: str, now_seconds: int) -> SensorState:
        last_rec = self._last_received_by_sensor.get(sensor_id)
        return evaluate_sensor_health(
            now_received_seconds=now_seconds,
            last_received_seconds=last_rec,
            stale_after_seconds=self.stale_after_seconds,
            offline_after_seconds=self.offline_after_seconds,
        )

    def reset(self) -> None:
        self._last_received_by_sensor.clear()
