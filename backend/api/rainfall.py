"""
Rainfall ingestion API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from backend.models.schemas import RainfallIngestRequest

router = APIRouter(prefix="/api/rainfall", tags=["Rainfall"])


def get_sim_service():
    from backend.app import sim_service
    return sim_service


@router.post("/ingest")
def ingest_rainfall(payload: RainfallIngestRequest, sim=Depends(get_sim_service)):
    """
    Ingests rainfall data for a specific cell or catchment-wide.
    """
    rain_input = {payload.cell_id: payload.rainfall_mm} if payload.cell_id is not None else payload.rainfall_mm
    res = sim.step(rainfall_input=rain_input)
    return {
        "status": "success",
        "step": res["step"],
        "rainfall_mm": payload.rainfall_mm,
        "mass_balance": res["mass_balance"],
    }
