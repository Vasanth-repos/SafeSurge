"""
API Endpoints — Emergency Safe Routing:
Calculates dynamic risk-avoidance shortest paths and returns route explanation and avoided roads.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from backend.schemas import RouteRequest
from backend.dependencies import get_simulation_manager
from backend.services.simulation_manager import SimulationManager

router = APIRouter(prefix="/api/routes", tags=["Routes"])


@router.post("/safe")
def calculate_safe_route(
    request: RouteRequest,
    manager: SimulationManager = Depends(get_simulation_manager),
):
    from backend.app import sim_service
    if request.simulation_id is not None:
        try:
            route_result = manager.route_emergency(
                simulation_id=request.simulation_id,
                origin=request.origin,
                destination=request.destination,
                lead_time_minutes=request.lead_time_minutes,
            )
            return route_result.to_dict()
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": str(e)},
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            )

    # Legacy routing via sim_service
    res = sim_service.compute_safe_route(
        origin=request.origin,
        destination=request.destination,
        mode=request.mode,
    )
    return res
