"""
API Endpoints — Rainfall Replay & Storm Execution:
Initiates and controls storm replay simulation lifecycles.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from backend.schemas import ReplayRequest
from backend.dependencies import get_simulation_manager
from backend.services.simulation_manager import SimulationManager

router = APIRouter(prefix="/api/rainfall", tags=["Rainfall"])


@router.post("/replay", status_code=status.HTTP_200_OK)
def trigger_replay(
    request: ReplayRequest,
    manager: SimulationManager = Depends(get_simulation_manager),
):
    try:
        instance = manager.start_simulation(scenario=request.scenario)
        return {
            "simulation_id": instance.simulation_id,
            "status": instance.status.value,
            "scenario": instance.scenario,
            "forecast_minutes": instance.forecast_minutes,
        }
    except RuntimeError as e:
        if "SIMULATION_ALREADY_RUNNING" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "SIMULATION_ALREADY_RUNNING"},
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
