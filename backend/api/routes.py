"""
Safe route planning API endpoints.
"""

from fastapi import APIRouter, Depends
from backend.models.schemas import SafeRouteRequest, SafeRouteResponse

router = APIRouter(prefix="/api/routes", tags=["Routing"])


def get_sim_service():
    from backend.app import sim_service
    return sim_service


@router.post("/safe", response_model=SafeRouteResponse)
def compute_safe_route_endpoint(payload: SafeRouteRequest, sim=Depends(get_sim_service)):
    """
    Computes flood-aware multi-objective shortest path avoiding unsafe flooded corridors.
    """
    res = sim.compute_safe_route(
        origin=payload.origin,
        destination=payload.destination,
        mode=payload.mode or "emergency",
    )
    return res


@router.get("/nodes")
def get_road_nodes(sim=Depends(get_sim_service)):
    """
    Returns all road junction nodes and their coordinates.
    """
    nodes = []
    for nid, pos in sim.roads.nodes.items():
        nodes.append({
            "node_id": nid,
            "row": pos[0],
            "col": pos[1],
        })
    return nodes
