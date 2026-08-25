from typing import Optional
from fastapi import APIRouter, Query
from backend.api.snapshots import get_snapshot_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/state")
def get_dashboard_state(
    lead_time_minutes: int = Query(0, ge=0),
    scenario_id: Optional[str] = Query(None),
):
    service = get_snapshot_service()
    return service.get_dashboard_state(
        lead_time_minutes=lead_time_minutes,
        scenario_id=scenario_id,
    )
