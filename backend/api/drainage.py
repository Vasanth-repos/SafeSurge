"""
API Endpoints — Virtual Tank Drainage Network:
Exposes real-time telemetry, network graph topology, and node-level tank diagnostics.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.snapshots import get_snapshot_service
from flood_engine.tank_drainage import VirtualTankDrainageNetwork

router = APIRouter(prefix="/api/drainage", tags=["Drainage"])


@router.get("/status")
def get_drainage_status(
    lead_time_minutes: int = Query(0, ge=0, description="Current simulation lead time in minutes"),
    scenario_id: str | None = Query(None, description="Scenario ID (default storm_01)"),
    fault_blockage: bool = Query(False, description="Simulate culvert drainage blockage"),
):
    """Returns the executive network-wide status of all virtual drainage tanks."""
    service = get_snapshot_service()
    dash_state = service.get_dashboard_state(
        lead_time_minutes=lead_time_minutes,
        scenario_id=scenario_id,
        fault_blockage=fault_blockage,
    )
    tanks = dash_state.get("drainage_tanks", {})
    summary = dash_state.get("drainage_network_summary", {})
    return {
        "lead_time_minutes": lead_time_minutes,
        "scenario_id": dash_state.get("simulation_id", scenario_id or "storm_01"),
        "summary": summary,
        "tanks": tanks,
    }


@router.get("/network")
def get_drainage_network(
    lead_time_minutes: int = Query(0, ge=0, description="Current simulation lead time in minutes"),
    scenario_id: str | None = Query(None, description="Scenario ID"),
    fault_blockage: bool = Query(False, description="Simulate culvert drainage blockage"),
):
    """
    Returns the complete drainage network topology graph, including nodes,
    capacities, current storage, connecting conduits, coordinates, and flow status.
    """
    service = get_snapshot_service()
    dash_state = service.get_dashboard_state(
        lead_time_minutes=lead_time_minutes,
        scenario_id=scenario_id,
        fault_blockage=fault_blockage,
    )
    tanks = dash_state.get("drainage_tanks", {})
    summary = dash_state.get("drainage_network_summary", {})

    edges = [
        {"from_node": "D01", "to_node": "D02", "length_m": 180.0, "diameter_m": 0.8},
        {"from_node": "D02", "to_node": "D03", "length_m": 140.0, "diameter_m": 1.0},
        {"from_node": "D03", "to_node": "D04", "length_m": 160.0, "diameter_m": 1.2},
        {"from_node": "D04", "to_node": "D05", "length_m": 320.0, "diameter_m": 1.5},
        {"from_node": "D05", "to_node": "OUTLET", "length_m": 50.0, "diameter_m": 1.8},
    ]

    return {
        "network_id": "CHENNAI_URBAN_TRUNK_01",
        "lead_time_minutes": lead_time_minutes,
        "nodes": list(tanks.values()) if isinstance(tanks, dict) else tanks,
        "edges": edges,
        "summary": summary,
    }


@router.get("/nodes/{node_id}")
def get_drainage_node(
    node_id: str,
    lead_time_minutes: int = Query(0, ge=0),
    scenario_id: str | None = Query(None),
    fault_blockage: bool = Query(False),
):
    """Returns detailed telemetry, flow rates, and sensor agreement for a specific drainage tank node."""
    service = get_snapshot_service()
    dash_state = service.get_dashboard_state(
        lead_time_minutes=lead_time_minutes,
        scenario_id=scenario_id,
        fault_blockage=fault_blockage,
    )
    tanks = dash_state.get("drainage_tanks", {})
    nid = node_id.upper()
    if nid not in tanks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drainage node '{node_id}' not found. Available nodes: {list(tanks.keys())}",
        )
    return {
        "lead_time_minutes": lead_time_minutes,
        "node": tanks[nid],
    }
