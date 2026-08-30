
from fastapi import APIRouter, Query

from backend.api.snapshots import get_snapshot_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/state")
def get_dashboard_state(
    lead_time_minutes: int = Query(0, ge=0),
    scenario_id: str | None = Query(None),
    fault_spike: bool = Query(False),
    fault_offline: bool = Query(False),
    fault_blockage: bool = Query(False),
):
    service = get_snapshot_service()
    return service.get_dashboard_state(
        lead_time_minutes=lead_time_minutes,
        scenario_id=scenario_id,
        fault_spike=fault_spike,
        fault_offline=fault_offline,
        fault_blockage=fault_blockage,
    )

