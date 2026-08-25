"""
Mass balance and system health diagnostics endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends
from backend.models.schemas import MassBalanceResponse

router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostics"])


def get_sim_service():
    from backend.app import sim_service
    return sim_service


@router.get("/mass_balance", response_model=MassBalanceResponse)
def get_mass_balance_diagnostic(sim=Depends(get_sim_service)):
    """
    Returns current mass conservation diagnostic verification status.
    """
    if sim.diagnostic.history:
        latest = sim.diagnostic.history[-1]
    else:
        latest = {
            "step": 0,
            "input_total_m3": 0.0,
            "storage_total_m3": 0.0,
            "drained_total_m3": 0.0,
            "boundary_outflow_m3": 0.0,
            "balance_error_m3": 0.0,
            "status": "PASS",
        }
    return latest


@router.get("/history", response_model=List[MassBalanceResponse])
def get_mass_balance_history(sim=Depends(get_sim_service)):
    """
    Returns historical mass balance logs across simulation steps.
    """
    return sim.diagnostic.history


@router.get("/events")
def get_event_logs(sim=Depends(get_sim_service)):
    """
    Returns audit event logs (anomalies, sensor rejections, fault injections).
    """
    return sim.event_logs
