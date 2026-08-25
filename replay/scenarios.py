"""
Replay Scenarios Registry & Loader (Layer 23):
Loads scenario definitions with embedded faults and executes replay pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from replay.engine import ReplayEngine, SimulationSnapshot
from replay.faults import Fault, FaultType


def load_scenario_from_yaml(yaml_path: str) -> Dict[str, Any]:
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"Scenario configuration not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_faults_from_dict(faults_data: List[Dict[str, Any]]) -> List[Fault]:
    faults = []
    for fd in faults_data:
        faults.append(
            Fault(
                fault_id=fd["fault_id"],
                fault_type=FaultType(fd["fault_type"]),
                start_seconds=int(fd["start_seconds"]),
                end_seconds=int(fd["end_seconds"]),
                parameters=fd.get("parameters", {}),
            )
        )
    return faults


class ScenarioRunner:
    def __init__(self, config_path: str = "config.yaml"):
        self.engine = ReplayEngine(config_path=config_path)

    def run(self, yaml_path: str) -> List[SimulationSnapshot]:
        data = load_scenario_from_yaml(yaml_path)
        s_id = data.get("scenario_id", "custom_storm")
        tot_min = int(data.get("total_minutes", 180))
        dt = int(data.get("timestep_seconds", 60))
        faults = parse_faults_from_dict(data.get("faults", []))
        return self.engine.run_scenario(
            scenario_name=s_id,
            total_minutes=tot_min,
            timestep_seconds=dt,
            faults=faults,
        )
