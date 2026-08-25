"""
API Endpoints — Flood Grid & Nowcast Forecast:
Returns fused grid depths, original model depths, risk classifications, and anomaly detections.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from backend.dependencies import get_simulation_manager
from backend.services.simulation_manager import SimulationManager

router = APIRouter(prefix="/api/flood", tags=["Flood"])


@router.get("/grid")
def get_flood_grid(
    simulation_id: Optional[str] = None,
    timestamp_seconds: Optional[int] = None,
    manager: SimulationManager = Depends(get_simulation_manager),
):
    from backend.app import sim_service
    if simulation_id is None and timestamp_seconds is None:
        # Legacy 20x20 grid query
        return sim_service.get_grid_state()

    sim_id = simulation_id or manager.active_simulation_id
    if not sim_id:
        return sim_service.get_grid_state()

    snapshot = manager.get_snapshot(sim_id, timestamp_seconds)
    if not snapshot:
        return sim_service.get_grid_state()

    return {
        "simulation_id": snapshot.simulation_id,
        "timestamp_seconds": snapshot.timestamp_seconds,
        "flood_grid": snapshot.flood_grid,
        "anomalies": snapshot.anomalies,
    }


@router.get("/roads")
def get_flood_roads():
    from backend.app import sim_service
    return sim_service.get_roads_state()


@router.get("/forecast")
def get_flood_forecast(
    simulation_id: Optional[str] = None,
    lead_time_minutes: int = Query(30, ge=0),
    manager: SimulationManager = Depends(get_simulation_manager),
):
    sim_id = simulation_id or manager.active_simulation_id
    if not sim_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "NO_ACTIVE_SIMULATION"},
        )

    target_t = lead_time_minutes * 60
    snapshot = manager.get_snapshot(sim_id, target_t)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "FORECAST_NOT_FOUND", "simulation_id": sim_id, "lead_time_minutes": lead_time_minutes},
        )

    return {
        "simulation_id": snapshot.simulation_id,
        "lead_time_minutes": lead_time_minutes,
        "timestamp_seconds": snapshot.timestamp_seconds,
        "flood_grid": snapshot.flood_grid,
        "anomalies": snapshot.anomalies,
    }
