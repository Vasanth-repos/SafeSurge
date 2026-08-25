"""
API Endpoints — Dashboard State (Layer 20):
Returns unified coherent snapshot representation for web GIS dashboard rendering.
"""

from fastapi import APIRouter, Query
from backend.api.snapshots import get_snapshot_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/state")
def get_dashboard_state(
    lead_time_minutes: int = Query(0, ge=0),
):
    service = get_snapshot_service()
    return service.get_dashboard_state(lead_time_minutes)
