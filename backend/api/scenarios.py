"""
Simulation scenarios, replay execution, fault injection, and drainage topology endpoints.
"""

from typing import Dict, Any, List, Optional
import os
import json
from fastapi import APIRouter, HTTPException, Depends
from backend.models.schemas import FaultInjectionRequest

router = APIRouter(prefix="/api", tags=["Scenarios & Faults"])


def get_sim_service():
    from backend.app import sim_service
    return sim_service


REPLAY_SCENARIOS = {
    "flash_flood": "replay/rainfall/flash_flood.json",
    "moderate_rain": "replay/rainfall/moderate_rain.json",
    "blockage_storm": "replay/rainfall/blockage_storm.json",
}


def load_replay_file(scenario_name: str) -> List[Dict[str, Any]]:
    path = REPLAY_SCENARIOS.get(scenario_name, "replay/rainfall/flash_flood.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_sensors_replay() -> Dict[str, List[Dict[str, Any]]]:
    path = "replay/sensors/sensors_replay.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/scenarios")
def list_scenarios():
    return {
        "scenarios": [
            {"id": "flash_flood", "name": "Flash Flood (Cloudburst 60mm/hr)", "steps": 10, "description": "High-intensity rainfall with rapid surface accumulation"},
            {"id": "moderate_rain", "name": "Monsoon Moderate Rain (15mm/hr)", "steps": 8, "description": "Steady continuous rain, fully managed by normal drainage"},
            {"id": "blockage_storm", "name": "Storm + Drainage Blockage (Inlet #3 @ 30%)", "steps": 7, "description": "Medium storm with simultaneous dynamic drain capacity failure"},
        ]
    }


@router.post("/scenarios/step")
def advance_scenario_step(scenario: str = "flash_flood", sim=Depends(get_sim_service)):
    """
    Advances simulation by one step using the scenario's scripted timeline.
    """
    rain_script = load_replay_file(scenario)
    sensors_script = load_sensors_replay()

    step_idx = sim.current_step
    if step_idx < len(rain_script):
        step_rain = rain_script[step_idx]
        rain_rate_mm_hr = float(step_rain.get("rainfall_mm_hr", 0.0))
        # Convert mm/hr to mm over timestep (dt = 60s -> 1/60 hr)
        dt_s = float(sim.config.get("timestep_s", 60.0))
        rain_mm_timestep = (rain_rate_mm_hr / 3600.0) * dt_s
        desc = step_rain.get("description", "")
    else:
        rain_mm_timestep = 0.0
        desc = "Storm ended, recession phase"

    # Specific scripted scenario actions (e.g. Blockage storm degrades Inlet 3 at step 2)
    if scenario == "blockage_storm" and step_idx == 2:
        sim.inject_fault("drain_blockage", target_id=3, value=0.3)

    # Collect sensor readings for this step
    sensor_inputs = {}
    for sid_str, telemetry_list in sensors_script.items():
        sid = int(sid_str)
        if step_idx < len(telemetry_list):
            sensor_inputs[sid] = telemetry_list[step_idx]

    step_result = sim.step(rainfall_input=rain_mm_timestep, sensor_readings=sensor_inputs, dt_seconds=dt_s)

    return {
        "step": step_result["step"],
        "scenario": scenario,
        "description": desc,
        "rainfall_mm_hr": rain_mm_timestep * (3600.0 / dt_s),
        "rainfall_mm_step": round(rain_mm_timestep, 3),
        "step_result": step_result,
    }


@router.post("/scenarios/reset")
def reset_simulation(sim=Depends(get_sim_service)):
    sim.reset()
    return {"status": "success", "message": "Simulation catchment reset to initial dry state"}


@router.post("/faults/inject")
def inject_fault_endpoint(payload: FaultInjectionRequest, sim=Depends(get_sim_service)):
    sim.inject_fault(payload.fault_type, payload.target_id, payload.value)
    return {
        "status": "success",
        "fault_type": payload.fault_type,
        "target_id": payload.target_id,
        "value": payload.value,
    }


@router.get("/drainage/network")
def get_drainage_network(sim=Depends(get_sim_service)):
    """
    Returns full drainage graph nodes, dynamic capacity factors, and edges for GIS visualization.
    """
    nodes = []
    for n in sim.drainage.nodes.values():
        r, c = divmod(n.cell_id, sim.cols)
        nodes.append({
            "node_id": n.node_id,
            "name": n.name,
            "cell_id": n.cell_id,
            "row": r,
            "col": c,
            "node_type": n.node_type,
            "base_capacity_m3_s": n.base_capacity_m3_s,
            "capacity_factor": n.capacity_factor,
            "effective_capacity_m3_s": round(n.effective_capacity_m3_s, 2),
            "captured_this_step_m3": round(n.captured_this_step_m3, 3),
        })

    edges = []
    for e in sim.drainage.edges.values():
        edges.append({
            "edge_id": e.edge_id,
            "from_node": e.from_node,
            "to_node": e.to_node,
            "length_m": e.length_m,
            "diameter_m": e.diameter_m,
            "slope": e.slope,
            "base_capacity_m3_s": e.base_capacity_m3_s,
        })

    return {
        "nodes": nodes,
        "edges": edges,
    }
