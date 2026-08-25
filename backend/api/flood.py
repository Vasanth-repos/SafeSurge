"""
Flood simulation, 2D grid depth, forecast, and road risk endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from backend.models.schemas import GridCellResponse, RoadRiskResponse, SimulateRequest

router = APIRouter(prefix="/api/flood", tags=["Flood"])


def get_sim_service():
    from backend.app import sim_service
    return sim_service


@router.post("/simulate")
def run_simulation(payload: SimulateRequest, sim=Depends(get_sim_service)):
    """
    Executes a multi-step simulation scenario.
    """
    steps_run = 0
    results = []
    for _ in range(payload.duration_steps or 10):
        # Default step with standard rain
        r_step = sim.step(rainfall_input=20.0, dt_seconds=payload.dt_seconds)
        results.append(r_step)
        steps_run += 1

    return {
        "status": "completed",
        "scenario": payload.scenario_name,
        "steps_executed": steps_run,
        "final_mass_balance": results[-1]["mass_balance"] if results else None,
    }


@router.get("/grid", response_model=List[GridCellResponse])
def get_flood_grid(ts: Optional[str] = None, sim=Depends(get_sim_service)):
    """
    Returns 2D spatial grid state with raw depth, fused depth, storage, and confidence.
    """
    return sim.get_grid_state()


@router.get("/roads", response_model=List[RoadRiskResponse])
def get_road_risks(ts: Optional[str] = None, sim=Depends(get_sim_service)):
    """
    Returns the road segment flood exposure and risk classifications.
    """
    return sim.get_roads_state()


@router.get("/forecast")
def get_forecast(cell_id: int = Query(...), forecast_time: Optional[str] = None, sim=Depends(get_sim_service)):
    """
    Gets nowcast depth bounds and confidence for a specific cell.
    """
    if cell_id not in sim.cells:
        raise HTTPException(status_code=404, detail=f"Cell ID {cell_id} not found")

    cell = sim.cells[cell_id]
    fused_d = sim.fused_depths_cm[cell_id]
    conf = sim.cell_confidences[cell_id]

    # Uncertainty bounds based on confidence
    uncertainty_margin = (1.0 - conf) * 15.0
    lower_bound = max(0.0, fused_d - uncertainty_margin)
    upper_bound = fused_d + uncertainty_margin

    return {
        "cell_id": cell_id,
        "predicted_depth_cm": round(fused_d, 2),
        "lower_bound_cm": round(lower_bound, 2),
        "upper_bound_cm": round(upper_bound, 2),
        "confidence": round(conf, 2),
    }
