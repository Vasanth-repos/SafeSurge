"""
Pydantic schemas for API requests and responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class RainfallIngestRequest(BaseModel):
    ts: str | None = None
    cell_id: int | None = None
    rainfall_mm: float = Field(..., ge=0.0, description="Rainfall depth in mm for current timestep")
    forecast_horizon_min: int | None = 0
    source: str | None = "replay"


class SensorReadingRequest(BaseModel):
    sensor_id: int
    ts: str | None = None
    water_level_cm: float
    float_state: bool | None = False
    battery: int | None = 100
    signal_quality: float | None = 1.0
    heartbeat: bool = True


class SensorStatusResponse(BaseModel):
    sensor_id: int
    name: str
    cell_id: int
    status: str  # ONLINE, STALE, OFFLINE, INVALID
    sensor_type: str
    last_reading_cm: float | None
    last_valid_reading_cm: float | None
    last_quality_flag: str
    battery: int
    signal_quality: float
    current_bias_cm: float
    float_state: bool


class SimulateRequest(BaseModel):
    scenario_name: str | None = "flash_flood"
    duration_steps: int | None = 10
    dt_seconds: float | None = 60.0


class GridCellResponse(BaseModel):
    cell_id: int
    row: int
    col: int
    elevation: float
    raw_depth_cm: float
    fused_depth_cm: float
    storage_m3: float
    risk_level: str
    confidence: float
    has_inlet: bool
    has_sensor: bool


class RoadRiskResponse(BaseModel):
    road_id: str
    name: str
    from_node: str
    to_node: str
    predicted_depth_cm: float
    risk_level: str
    data_quality: str
    confidence: float


class SafeRouteRequest(BaseModel):
    origin: str
    destination: str
    mode: str | None = "emergency"  # 'vehicle', 'emergency', 'pedestrian'
    forecast_minutes: int | None = 0


class SafeRouteResponse(BaseModel):
    success: bool
    error: str | None = None
    origin: str
    destination: str
    mode: str
    path_nodes: list[str]
    segments: list[dict[str, Any]]
    eta_minutes: float
    flood_exposure_score: float
    confidence: float


class MassBalanceResponse(BaseModel):
    step: int
    input_total_m3: float
    storage_total_m3: float
    drained_total_m3: float
    boundary_outflow_m3: float
    balance_error_m3: float
    status: str  # PASS / FAIL


class FaultInjectionRequest(BaseModel):
    fault_type: str  # 'sensor_disconnect', 'sensor_spike', 'sensor_out_of_range', 'drain_blockage', 'drain_restore'
    target_id: int   # sensor_id or inlet_id
    value: float | None = None
