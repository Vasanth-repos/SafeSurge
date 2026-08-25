"""
Sensor health and lifecycle state machine (ONLINE, STALE, OFFLINE, INVALID).
"""

from typing import Dict, Any, Optional


class SensorNode:
    def __init__(
        self,
        sensor_id: int,
        name: str,
        cell_id: int,
        sensor_type: str = "ultrasonic",  # 'ultrasonic' | 'float'
        installation_height_cm: float = 150.0,
        latitude: float = 0.0,
        longitude: float = 0.0,
    ):
        self.sensor_id = sensor_id
        self.name = name
        self.cell_id = cell_id
        self.sensor_type = sensor_type
        self.installation_height_cm = installation_height_cm
        self.latitude = latitude
        self.longitude = longitude

        # Runtime state
        self.status: str = "ONLINE"  # 'ONLINE', 'STALE', 'OFFLINE', 'INVALID'
        self.missed_heartbeats: int = 0
        self.last_valid_reading_cm: Optional[float] = None
        self.last_reading_cm: Optional[float] = None
        self.last_quality_flag: str = "VALID"
        self.current_bias: float = 0.0
        self.recent_errors: list = []
        self.battery: int = 100
        self.signal_quality: float = 1.0
        self.float_state: bool = False
        self.redundancy_state: Optional[str] = None  # e.g., 'WATER_PRESENT_DEPTH_UNKNOWN'

    def update_health(
        self,
        received_heartbeat: bool,
        quality_flag: str,
        float_state: bool = False,
        stale_threshold: int = 3,
        offline_threshold: int = 6,
    ):
        self.last_quality_flag = quality_flag
        self.float_state = float_state

        if not received_heartbeat:
            self.missed_heartbeats += 1
        else:
            self.missed_heartbeats = 0

        if quality_flag in ("INVALID_RANGE", "INVALID_SPIKE", "RATE_SPIKE", "OUT_OF_RANGE"):
            self.status = "INVALID"
            if float_state:
                self.redundancy_state = "WATER_PRESENT_DEPTH_UNKNOWN"
            else:
                self.redundancy_state = None
        elif self.missed_heartbeats >= offline_threshold:
            self.status = "OFFLINE"
            self.redundancy_state = None
        elif self.missed_heartbeats >= stale_threshold:
            self.status = "STALE"
            self.redundancy_state = None
        else:
            self.status = "ONLINE"
            self.redundancy_state = None

    def is_usable_for_fusion(self) -> bool:
        return self.status == "ONLINE" and self.last_quality_flag == "VALID"
