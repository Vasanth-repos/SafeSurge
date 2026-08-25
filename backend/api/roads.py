"""
API Endpoints — Road Exposure & Risk States:
Returns road-level aggregated depths, exposure fractions, risk classifications, and confidence.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from backend.dependencies import get_simulation_manager
from backend.services.simulation_manager import SimulationManager

router = APIRouter(prefix="/api/roads", tags=["Roads"])


@router.get("/risk")
def get_roads_risk(
    simulation_id: Optional[str] = None,
    timestamp_seconds: Optional[int] = None,
    manager: SimulationManager = Depends(get_simulation_manager),
):
    sim_id = simulation_id or manager.active_simulation_id
    if not sim_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "NO_ACTIVE_SIMULATION"},
        )

    snapshot = manager.get_snapshot(sim_id, timestamp_seconds)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SNAPSHOT_NOT_FOUND", "simulation_id": sim_id},
        )

    return {
        "simulation_id": snapshot.simulation_id,
        "timestamp_seconds": snapshot.timestamp_seconds,
        "roads": list(snapshot.road_risks.values()),
    }
