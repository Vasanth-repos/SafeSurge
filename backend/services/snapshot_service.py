"""
Snapshot Service (Layers 20–25):
Central store and query coordinator for immutable time-indexed SimulationSnapshots.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
from flood_engine.snapshot import SimulationSnapshot
from replay.engine import ReplayEngine
from replay.scenarios import ScenarioRunner


class SnapshotService:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.runner = ScenarioRunner(config_path=config_path)
        # In-memory snapshot store: (simulation_id, timestamp_seconds) -> SimulationSnapshot
        self._store: Dict[Tuple[str, int], SimulationSnapshot] = {}
        self.active_simulation_id: Optional[str] = None
        self._initialize_baseline_storm()

    def _initialize_baseline_storm(self):
        """Pre-loads default baseline storm (180 minutes, 181 snapshots)."""
        snapshots = self.runner.run("config/scenarios/storm_01.yaml")
        for snap in snapshots:
            self._store[(snap.simulation_id, snap.timestamp_seconds)] = snap
        self.active_simulation_id = "storm_01"

    def run_scenario(self, scenario_yaml_path: str) -> str:
        snapshots = self.runner.run(scenario_yaml_path)
        sim_id = snapshots[0].simulation_id if snapshots else "custom_storm"
        for snap in snapshots:
            self._store[(snap.simulation_id, snap.timestamp_seconds)] = snap
        self.active_simulation_id = sim_id
        return sim_id

    def get_snapshot(
        self,
        simulation_id: Optional[str] = None,
        timestamp_seconds: Optional[int] = None,
    ) -> Optional[SimulationSnapshot]:
        sim_id = simulation_id or self.active_simulation_id
        if not sim_id:
            return None

        if timestamp_seconds is None:
            # Return latest or initial available timestamp
            matching = [t for (s, t) in self._store.keys() if s == sim_id]
            if not matching:
                return None
            target_t = max(matching)
        else:
            # Find exact or nearest timestamp
            matching = [t for (s, t) in self._store.keys() if s == sim_id]
            if not matching:
                return None
            target_t = min(matching, key=lambda t: abs(t - timestamp_seconds))

        return self._store.get((sim_id, target_t))

    def get_all_timestamps(self, simulation_id: Optional[str] = None) -> List[int]:
        sim_id = simulation_id or self.active_simulation_id
        if not sim_id:
            return []
        return sorted([t for (s, t) in self._store.keys() if s == sim_id])

    def get_dashboard_state(self, lead_time_minutes: int = 0) -> Dict[str, Any]:
        sim_id = self.active_simulation_id
        target_t = lead_time_minutes * 60
        snap = self.get_snapshot(sim_id, target_t)
        if not snap:
            return {"status": "NO_ACTIVE_SIMULATION"}

        return {
            "simulation_id": snap.simulation_id,
            "timestamp_seconds": snap.timestamp_seconds,
            "system_status": snap.system_status,
            "rainfall_status": snap.rainfall_status,
            "degraded_reasons": list(snap.degraded_reasons),
            "forecast": snap.forecast.to_dict() if snap.forecast else None,
            "cells": [c.to_dict() for c in snap.flood_cells],
            "roads": [r.to_dict() for r in snap.road_risks],
            "drainage": list(snap.drainage_states),
            "sensors": [s.to_dict() for s in snap.sensor_states],
            "anomalies": list(snap.anomalies),
            "mass_balance": snap.mass_balance.to_dict(),
            "active_faults": list(snap.active_faults),
        }
