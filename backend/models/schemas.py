"""
Pydantic schemas for API requests and responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RainfallIngestRequest(BaseModel):
    ts: Optional[str] = None
    cell_id: Optional[int] = None
    rainfall_mm: float = Field(..., ge=0.0, description="Rainfall depth in mm for current timestep")
    forecast_horizon_min: Optional[int] = 0
    source: Optional[str] = "replay"


class SensorReadingRequest(BaseModel):
    sensor_id: int
    ts: Optional[str] = None
    water_level_cm: float
    float_state: Optional[bool] = False
    battery: Optional[int] = 100
    signal_quality: Optional[float] = 1.0
    heartbeat: bool = True


class SensorStatusResponse(BaseModel):
    sensor_id: int
    name: str
    cell_id: int
    status: str  # ONLINE, STALE, OFFLINE, INVALID
    sensor_type: str
    last_reading_cm: Optional[float]
    last_valid_reading_cm: Optional[float]
    last_quality_flag: str
    battery: int
    signal_quality: float
    current_bias_cm: float
    float_state: bool


class SimulateRequest(BaseModel):
    scenario_name: Optional[str] = "flash_flood"
    duration_steps: Optional[int] = 10
    dt_seconds: Optional[float] = 60.0


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
    mode: Optional[str] = "emergency"  # 'vehicle', 'emergency', 'pedestrian'
    forecast_minutes: Optional[int] = 0


class SafeRouteResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    origin: str
    destination: str
    mode: str
    path_nodes: List[str]
    segments: List[Dict[str, Any]]
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
    value: Optional[float] = None
