"""
Layer 19 — Backend Pydantic Request & Response Schemas:
Enforces strict input validation and uniform JSON responses across all API endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ReplayRequest(BaseModel):
    scenario: str = Field(..., description="Storm scenario file or identifier")


class RouteRequest(BaseModel):
    simulation_id: Optional[str] = Field(None, description="Active simulation identifier")
    origin: str = Field(..., description="Origin node identifier")
    destination: str = Field(..., description="Destination node identifier")
    lead_time_minutes: int = Field(0, ge=0, description="Nowcast forecast lead time in minutes")
    mode: str = Field("vehicle", description="Transportation mode")


class SensorReadingRequest(BaseModel):
    sensor_id: str = Field(..., description="Sensor identifier")
    timestamp_seconds: int = Field(..., ge=0, description="Measurement epoch timestamp in seconds")
    distance_cm: float = Field(..., description="Measured ultrasonic echo distance in cm")
    float_state: str = Field("DRY", description="Float switch contact state (e.g. WATER_PRESENT or DRY)")
    boot_id: str = Field("boot-001", description="Device boot session identifier")
    sequence: int = Field(1, ge=0, description="Device packet sequence number")
