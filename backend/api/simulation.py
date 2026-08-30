"""
API Endpoints — Simulation Lifecycle & Snapshot Inspection:
Retrieves simulation status, active snapshots, and diagnostics.
"""


from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_simulation_manager
from backend.services.simulation_manager import SimulationManager

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


@router.get("/{simulation_id}")
def get_simulation_status(
    simulation_id: str,
    manager: SimulationManager = Depends(get_simulation_manager),
):
    sim = manager.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SIMULATION_NOT_FOUND", "simulation_id": simulation_id},
        )

    return {
        "simulation_id": sim.simulation_id,
        "status": sim.status.value,
        "scenario": sim.scenario,
        "snapshots_count": len(sim.snapshots),
        "available_timestamps": sorted(sim.snapshots.keys()),
    }
