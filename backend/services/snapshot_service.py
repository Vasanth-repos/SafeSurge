import os
from pathlib import Path
from typing import Any

from flood_engine.snapshot import SimulationSnapshot
from replay.scenarios import ScenarioRunner


class SnapshotService:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.runner = ScenarioRunner(config_path=config_path)
        # In-memory snapshot store: (simulation_id, timestamp_seconds) -> SimulationSnapshot
        self._store: dict[tuple[str, int], SimulationSnapshot] = {}
        self.active_simulation_id: str | None = None
        self._initialize_baseline_storm()

    def _initialize_baseline_storm(self):
        """Pre-loads default baseline storm (180 minutes, 181 snapshots)."""
        snapshots = self.runner.run("config/scenarios/storm_01.yaml")
        for snap in snapshots:
            self._store[(snap.simulation_id, snap.timestamp_seconds)] = snap
        self.active_simulation_id = "storm_01"

    def ensure_scenario_loaded(self, scenario_id: str) -> str:
        """Loads a scenario into memory if not already cached."""
        matching = [t for (s, t) in self._store if s == scenario_id]
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
        stem = Path(scenario_yaml_path).stem
        for snap in snapshots:
            self._store[(snap.simulation_id, snap.timestamp_seconds)] = snap
            if stem != snap.simulation_id:
                self._store[(stem, snap.timestamp_seconds)] = snap
        self.active_simulation_id = sim_id
        return sim_id

    def get_snapshot(
        self,
        simulation_id: str | None = None,
        timestamp_seconds: int | None = None,
    ) -> SimulationSnapshot | None:
        sim_id = simulation_id or self.active_simulation_id
        if not sim_id:
            return None

        # Check if scenario is loaded
        matching = [t for (s, t) in self._store if s == sim_id]
        if not matching:
            self.ensure_scenario_loaded(sim_id)
            matching = [t for (s, t) in self._store if s == sim_id]

        if not matching:
            return None

        if timestamp_seconds is None:
            target_t = max(matching)
        else:
            target_t = min(matching, key=lambda t: abs(t - timestamp_seconds))

        return self._store.get((sim_id, target_t))

    def get_all_timestamps(self, simulation_id: str | None = None) -> list[int]:
        sim_id = simulation_id or self.active_simulation_id
        if not sim_id:
            return []
        return sorted([t for (s, t) in self._store if s == sim_id])

    def get_dashboard_state(
        self,
        lead_time_minutes: int = 0,
        scenario_id: str | None = None,
        fault_spike: bool = False,
        fault_offline: bool = False,
        fault_blockage: bool = False,
    ) -> dict[str, Any]:
        if scenario_id:
            actual_id = self.ensure_scenario_loaded(scenario_id)
            sim_id = actual_id or scenario_id
        else:
            sim_id = self.active_simulation_id or "storm_01"

        target_t = lead_time_minutes * 60
        snap = self.get_snapshot(sim_id, target_t)
        if not snap and scenario_id:
            snap = self.get_snapshot(scenario_id, target_t)
        if not snap:
            snap = self.get_snapshot(self.active_simulation_id, target_t)
        if not snap:
            return {"status": "NO_ACTIVE_SIMULATION"}

        # Base snapshot structures
        system_status = snap.system_status
        degraded_reasons = list(snap.degraded_reasons)
        forecast_dict = snap.forecast.to_dict() if snap.forecast else None
        sensor_list = [s.to_dict() for s in snap.sensor_states]
        cell_list = [c.to_dict() for c in snap.flood_cells]
        road_list = [r.to_dict() for r in snap.road_risks]
        anomalies_list = list(snap.anomalies)
        active_faults_list = list(snap.active_faults)
        drainage_list = list(snap.drainage_states)

        # Apply Dynamic Interactive Fault Injections
        int_factor = max(0.2, (lead_time_minutes / 60.0) if lead_time_minutes <= 60 else (1.0 - (lead_time_minutes - 60) / 120.0))

        if fault_offline:
            system_status = "DEGRADED"
            reason = "Sensor S001 telemetry lost (heartbeat dropout)"
            if reason not in degraded_reasons:
                degraded_reasons.append(reason)
            active_faults_list.append("SENSOR_OFFLINE:S001")
            for s in sensor_list:
                if s.get("sensor_id") == "S001":
                    s["status"] = "OFFLINE"
                    s["last_valid_reading_cm"] = None
                    s["age_seconds"] = 1800
            if forecast_dict:
                forecast_dict["confidence"] = 0.88

        if fault_spike:
            system_status = "DEGRADED"
            reason = "Sensor S001 rate spike anomaly (+90cm spike rejected by Kalman/Z-score filter)"
            if reason not in degraded_reasons:
                degraded_reasons.append(reason)
            active_faults_list.append("SENSOR_SPIKE:S001")
            for s in sensor_list:
                if s.get("sensor_id") == "S001":
                    s["status"] = "STALE"
                    s["last_valid_reading_cm"] = 90.0
            anomalies_list.append({
                "sensor_id": "S001",
                "type": "RATE_OF_RISE",
                "depth_cm": 90.0,
                "status": "REJECTED"
            })

        if fault_blockage:
            system_status = "DEGRADED"
            reason = "Culvert E001 inlet capacity degraded 70% (debris clog)"
            if reason not in degraded_reasons:
                degraded_reasons.append(reason)
            active_faults_list.append("CAPACITY_REDUCTION:E001:0.3")
            drainage_list = ["CLOGGED" if d == "INLET_E001" else d for d in drainage_list]
            if "INLET_E001_CLOGGED" not in drainage_list:
                drainage_list.append("INLET_E001_CLOGGED")

            # Increase water backing up in lowland East cells
            extra_depth = 7.5 * int_factor
            for c in cell_list:
                r_idx = c.get("row", 0)
                c_idx = c.get("col", 0)
                if r_idx >= 5 and c_idx >= 7:
                    c["depth_cm"] = round(c["depth_cm"] + extra_depth, 1)
                    if c["depth_cm"] >= 25.0:
                        c["risk"] = "UNSAFE"
                    elif c["depth_cm"] >= 15.0:
                        c["risk"] = "HIGH"

            # Update affected roads (R005, R002, R009)
            for rd in road_list:
                if rd.get("road_id") in ["R005", "R002", "R009"]:
                    rd["mean_depth_cm"] = round(rd.get("mean_depth_cm", 0.0) + extra_depth, 1)
                    rd["max_relevant_depth_cm"] = round(rd.get("max_relevant_depth_cm", 0.0) + extra_depth, 1)
                    if rd["max_relevant_depth_cm"] >= 25.0:
                        rd["risk"] = "UNSAFE"
                    elif rd["max_relevant_depth_cm"] >= 15.0:
                        rd["risk"] = "HIGH"

        # Compute dynamic safe route for emergency dispatch (Origin A -> Hospital D)
        road_map = {r["road_id"]: r for r in road_list}
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
            d = r.get("max_relevant_depth_cm", r.get("mean_depth_cm", 0.0))
            risk = r.get("risk", "SAFE")
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
                    depth = r_obj.get("max_relevant_depth_cm", r_obj.get("mean_depth_cm", 0.0)) if r_obj else 0.0
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

        # Real-time Physics-Guided ML Surrogate Nowcast
        try:
            from ml.infer import predict_catchment_depths
            ml_res = predict_catchment_depths(
                lead_time_minutes=lead_time_minutes,
                scenario_id=sim_id,
                drain_capacity_factor=0.3 if fault_blockage else 1.0,
            )
            ml_data = {
                "available": True,
                "peak_depth_cm": ml_res["peak_depth_cm"],
                "mean_depth_cm": ml_res["mean_depth_cm"],
                "inference_time_ms": ml_res["inference_time_ms"],
                "model_architecture": ml_res["model_architecture"],
                "cell_depths": ml_res["cell_depths"],
            }
        except Exception:
            ml_data = {"available": False}

        return {
            "simulation_id": snap.simulation_id,
            "timestamp_seconds": snap.timestamp_seconds,
            "system_status": system_status,
            "rainfall_status": snap.rainfall_status,
            "degraded_reasons": degraded_reasons,
            "forecast": forecast_dict,
            "cells": cell_list,
            "roads": road_list,
            "drainage": drainage_list,
            "sensors": sensor_list,
            "anomalies": anomalies_list,
            "mass_balance": snap.mass_balance.to_dict(),
            "active_faults": active_faults_list,
            "safe_route": best_route,
            "ml_nowcast": ml_data,
        }


