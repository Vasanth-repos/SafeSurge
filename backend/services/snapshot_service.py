import os
from pathlib import Path
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

    def ensure_scenario_loaded(self, scenario_id: str) -> str:
        """Loads a scenario into memory if not already cached."""
        matching = [t for (s, t) in self._store.keys() if s == scenario_id]
        if matching:
            self.active_simulation_id = scenario_id
            return scenario_id

        # Look for YAML scenario file
        yaml_candidates = [
            f"config/scenarios/{scenario_id}.yaml",
            f"config/scenarios/{scenario_id}.yml",
        ]
        for ypath in yaml_candidates:
            if os.path.exists(ypath):
                return self.run_scenario(ypath)

        # Fallback to active simulation if not found
        return self.active_simulation_id or "storm_01"

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

        # Check if scenario is loaded
        matching = [t for (s, t) in self._store.keys() if s == sim_id]
        if not matching:
            self.ensure_scenario_loaded(sim_id)
            matching = [t for (s, t) in self._store.keys() if s == sim_id]

        if not matching:
            return None

        if timestamp_seconds is None:
            target_t = max(matching)
        else:
            target_t = min(matching, key=lambda t: abs(t - timestamp_seconds))

        return self._store.get((sim_id, target_t))

    def get_all_timestamps(self, simulation_id: Optional[str] = None) -> List[int]:
        sim_id = simulation_id or self.active_simulation_id
        if not sim_id:
            return []
        return sorted([t for (s, t) in self._store.keys() if s == sim_id])

    def get_dashboard_state(
        self,
        lead_time_minutes: int = 0,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if scenario_id:
            self.ensure_scenario_loaded(scenario_id)
            sim_id = scenario_id
        else:
            sim_id = self.active_simulation_id or "storm_01"

        target_t = lead_time_minutes * 60
        snap = self.get_snapshot(sim_id, target_t)
        if not snap:
            return {"status": "NO_ACTIVE_SIMULATION"}

        # Compute dynamic safe route for emergency dispatch (Origin A -> Hospital D)
        road_map = {r.road_id: r for r in snap.road_risks}
        graph_def = [
            ("R001", "A", "B", 50.0),
            ("R002", "B", "E", 30.0),
            ("R003", "A", "W", 30.0),
            ("R004", "C", "D", 40.0),
            ("R005", "E", "D", 30.0),
            ("R006", "A", "M", 35.0),
            ("R007", "M", "D", 35.0),
            ("R008", "W", "M", 30.0),
            ("R009", "M", "E", 25.0),
            ("R010", "W", "C", 30.0),
        ]
        
        # Dijkstra search
        adj = {}
        for rid, u, v, base_t in graph_def:
            adj.setdefault(u, []).append((v, rid, base_t))
            adj.setdefault(v, []).append((u, rid, base_t))

        def get_edge_weight(rid, base_t):
            r = road_map.get(rid)
            if not r:
                return base_t
            d = getattr(r, "max_relevant_depth_cm", getattr(r, "mean_depth_cm", 0.0))
            risk = getattr(r, "risk", "SAFE")
            if risk == "UNSAFE" or d >= 25.0:
                return float("inf")
            elif risk == "HIGH" or d >= 15.0:
                return base_t + 500.0 + d * 10.0
            elif risk == "WATCH" or d >= 5.0:
                return base_t + 20.0 + d * 2.0
            return base_t

        # Dijkstra algorithm
        import heapq
        pq = [(0.0, "A", ["A"], [], 0.0, 0.0)]
        visited = set()
        best_route = None

        while pq:
            cost, curr, path, rids, total_time, max_d = heapq.heappop(pq)
            if curr == "D":
                best_route = {
                    "success": True,
                    "origin": "A",
                    "destination": "D",
                    "path": path,
                    "road_ids": rids,
                    "eta_seconds": round(total_time, 1),
                    "max_exposure_depth_cm": round(max_d, 1),
                }
                break

            if curr in visited:
                continue
            visited.add(curr)

            for neighbor, rid, base_t in adj.get(curr, []):
                if neighbor in visited:
                    continue
                w = get_edge_weight(rid, base_t)
                if w < float("inf"):
                    r_obj = road_map.get(rid)
                    depth = getattr(r_obj, "max_relevant_depth_cm", getattr(r_obj, "mean_depth_cm", 0.0)) if r_obj else 0.0
                    heapq.heappush(
                        pq,
                        (
                            cost + w,
                            neighbor,
                            path + [neighbor],
                            rids + [rid],
                            total_time + base_t,
                            max(max_d, depth),
                        ),
                    )

        if not best_route:
            best_route = {
                "success": False,
                "origin": "A",
                "destination": "D",
                "path": ["A", "W", "C", "D"],
                "road_ids": ["R003", "R010", "R004"],
                "eta_seconds": 100.0,
                "max_exposure_depth_cm": 0.0,
            }

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
            "safe_route": best_route,
        }

