"""
Layer 19 — Simulation Manager & Immutable Snapshot Store:
Orchestrates end-to-end multi-layer simulation runs, prevents duplicate replays,
and stores immutable time-indexed simulation snapshots.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from shapely.geometry import LineString, Polygon

from anomalies.detector import AnomalyDetector
from flood_engine.risk import RiskEngine
from fusion.models import SensorObservation
from fusion.pipeline import FusionPipeline
from roads.mapping import RoadSpatialMapper
from roads.models import Road, RoadRisk
from roads.risk import RoadRiskEngine
from routing.graph import DirectedRoadGraph
from routing.models import RoadEdge
from routing.router import EmergencyRouter
from sensors.registry import SensorRegistry
from sensors.validation import SensorValidator


class SimulationStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SimulationSnapshot:
    simulation_id: str
    timestamp_seconds: int
    flood_grid: dict[str, Any]
    anomalies: dict[str, Any]
    road_risks: dict[str, Any]
    sensor_states: dict[str, Any]


@dataclass
class SimulationInstance:
    simulation_id: str
    scenario: str
    status: SimulationStatus = SimulationStatus.IDLE
    current_timestamp_seconds: int = 0
    forecast_minutes: int = 180
    snapshots: dict[int, SimulationSnapshot] = None

    def __post_init__(self):
        if self.snapshots is None:
            self.snapshots = {}


class SimulationManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._simulations: dict[str, SimulationInstance] = {}
        self.active_simulation_id: str | None = None

        # Base engine initialization
        self.sensor_registry = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
        self.sensor_validator = SensorValidator(self.sensor_registry)
        self.fusion_pipeline = FusionPipeline.load_from_config(config_path)
        self.anomaly_detector = AnomalyDetector()
        self.risk_engine = RiskEngine.load_from_config(config_path)
        self.road_risk_engine = RoadRiskEngine()

        # Build synthetic demo catchment grid & road network topology
        self._build_demo_topology()

    def _build_demo_topology(self):
        # 10x10 grid (100 cells, 10m x 10m)
        self.cell_coords: dict[str, tuple[float, float]] = {}
        self.cell_geometries: dict[str, Polygon] = {}
        self.cell_elevations: dict[str, float] = {}

        for r in range(10):
            for c in range(10):
                cid = f"C{r*10 + c + 1:03d}"
                x = c * 10.0 + 5.0
                y = r * 10.0 + 5.0
                self.cell_coords[cid] = (x, y)
                self.cell_geometries[cid] = Polygon([
                    (c * 10.0, r * 10.0),
                    ((c + 1) * 10.0, r * 10.0),
                    ((c + 1) * 10.0, (r + 1) * 10.0),
                    (c * 10.0, (r + 1) * 10.0),
                ])
                self.cell_elevations[cid] = 20.0 - (r + c) * 0.5

        # Demo Road Network
        # R001: A -> B (across top row C001..C005)
        # R002: B -> D (down east side C005..C045)
        # R003: A -> C (down west side C001..C041)
        # R004: C -> D (across bottom row C041..C045)
        self.roads = [
            Road("R001", "A", "B", LineString([(5.0, 5.0), (45.0, 5.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
            Road("R002", "B", "D", LineString([(45.0, 5.0), (45.0, 45.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
            Road("R003", "A", "C", LineString([(5.0, 5.0), (5.0, 45.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
            Road("R004", "C", "D", LineString([(5.0, 45.0), (45.0, 45.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
        ]
        self.road_mapper = RoadSpatialMapper(self.roads, self.cell_geometries)

        # Directed Road Graph for routing
        edges = [
            RoadEdge("R001", "A", "B", 60.0, 40.0),
            RoadEdge("R002", "B", "D", 60.0, 40.0),
            RoadEdge("R003", "A", "C", 60.0, 40.0),
            RoadEdge("R004", "C", "D", 60.0, 40.0),
        ]
        self.directed_graph = DirectedRoadGraph(edges)
        self.router = EmergencyRouter(self.directed_graph)

        # Sensor positions
        self.sensor_coords = {
            "S001": (15.0, 15.0),  # near C012
            "S002": (45.0, 25.0),  # near C025
        }

    def start_simulation(self, scenario: str) -> SimulationInstance:
        # Prevent competing/duplicate runs
        for sim in self._simulations.values():
            if sim.status == SimulationStatus.RUNNING:
                raise RuntimeError("SIMULATION_ALREADY_RUNNING")

        sim_id = f"sim_{int(time.time())}"
        instance = SimulationInstance(
            simulation_id=sim_id,
            scenario=scenario,
            status=SimulationStatus.RUNNING,
        )
        self._simulations[sim_id] = instance
        self.active_simulation_id = sim_id

        # Generate complete deterministic simulation replay snapshots (t=0 to 1800s in 60s steps)
        self._run_simulation_replay(instance)
        instance.status = SimulationStatus.COMPLETED
        return instance

    def _run_simulation_replay(self, instance: SimulationInstance):
        prev_depths = {cid: 0.0 for cid in self.cell_coords}
        prev_t = 0

        # Run 30-minute storm replay (31 snapshots: t=0, 60, 120, ..., 1800)
        for step_idx in range(31):
            t = step_idx * 60

            # 1. Physics model synthetic hydrograph
            model_depths = {}
            for cid, (x, y) in self.cell_coords.items():
                # North-East corridor accumulation (R002: high x, y in 5..35)
                ne_factor = ((x / 50.0) ** 3) * (math.exp(-((y - 25.0) / 15.0) ** 2))
                intensity = math.sin(min(math.pi, (step_idx / 30.0) * math.pi))
                # Base model depth in cm
                d = max(0.0, 45.0 * ne_factor * intensity)
                model_depths[cid] = d

            # 2. Sensor observations at telemetry interval
            observations = []
            if t > 0 and t % 60 == 0:
                s1_depth = model_depths.get("C012", 5.0) + 3.0  # Slightly biased
                observations.append(
                    SensorObservation("S001", "C012", t, s1_depth, "ONLINE", "ACCEPTED")
                )

            # 3. Sensor Fusion Step
            fusion_result = self.fusion_pipeline.step(
                timestamp_seconds=t,
                model_depth_cm_by_cell=model_depths,
                cell_coords_m_by_id=self.cell_coords,
                sensor_observations=observations,
                sensor_coords_m_by_id=self.sensor_coords,
            )

            # 4. Anomaly Evaluation
            anomalies = {}
            for cid in self.cell_coords:
                curr_d = fusion_result.cells[cid].corrected_depth_cm
                prev_d = prev_depths.get(cid, 0.0)
                assessment = self.anomaly_detector.evaluate_cell(
                    cell_id=cid,
                    timestamp_seconds=t,
                    current_depth_cm=curr_d,
                    previous_depth_cm=prev_d if step_idx > 0 else None,
                    previous_timestamp_seconds=prev_t if step_idx > 0 else None,
                    original_model_depth_cm=model_depths[cid],
                )
                anomalies[cid] = assessment.to_dict()

            # 5. Road Exposure & Risk
            cell_depth_map = {cid: cr.corrected_depth_cm for cid, cr in fusion_result.cells.items()}
            cell_conf_map = {cid: cr.confidence.score for cid, cr in fusion_result.cells.items()}

            road_risks = self.road_risk_engine.evaluate_all(
                timestamp_seconds=t,
                exposures_by_road=self.road_mapper.get_all_exposures(),
                cell_depths_by_id=cell_depth_map,
                cell_confidences_by_id=cell_conf_map,
            )

            # 6. Store Immutable Snapshot
            snapshot = SimulationSnapshot(
                simulation_id=instance.simulation_id,
                timestamp_seconds=t,
                flood_grid=fusion_result.to_dict(),
                anomalies=anomalies,
                road_risks={r_id: rr.to_dict() for r_id, rr in road_risks.items()},
                sensor_states={sid: b for sid, b in fusion_result.sensor_biases.items()},
            )
            instance.snapshots[t] = snapshot

            # Update memory
            prev_depths = cell_depth_map
            prev_t = t

    def get_simulation(self, simulation_id: str) -> SimulationInstance | None:
        return self._simulations.get(simulation_id)

    def get_snapshot(self, simulation_id: str, timestamp_seconds: int | None = None) -> SimulationSnapshot | None:
        sim = self.get_simulation(simulation_id)
        if not sim or not sim.snapshots:
            return None

        if timestamp_seconds is None:
            # Return latest available snapshot
            latest_t = max(sim.snapshots.keys())
            return sim.snapshots[latest_t]

        # Find closest snapshot
        available_ts = sorted(sim.snapshots.keys())
        closest_t = min(available_ts, key=lambda t: abs(t - timestamp_seconds))
        return sim.snapshots.get(closest_t)

    def route_emergency(
        self,
        simulation_id: str,
        origin: str,
        destination: str,
        lead_time_minutes: int = 0,
    ):
        sim = self.get_simulation(simulation_id)
        if not sim:
            raise KeyError(f"Simulation {simulation_id} not found")

        target_t = lead_time_minutes * 60
        snapshot = self.get_snapshot(simulation_id, target_t)
        if not snapshot:
            raise KeyError(f"No snapshot for simulation {simulation_id} at lead time {lead_time_minutes}m")

        # Build dynamic road states from snapshot
        road_risks_dict = snapshot.road_risks
        road_risks_objs = {
            r_id: RoadRisk(
                road_id=r_id,
                timestamp_seconds=data["timestamp_seconds"],
                mean_depth_cm=data["mean_depth_cm"],
                max_relevant_depth_cm=data["max_relevant_depth_cm"],
                affected_fraction=data["affected_fraction"],
                risk=data["risk"],
                confidence=data["confidence"],
                minimum_cell_confidence=data["minimum_cell_confidence"],
            )
            for r_id, data in road_risks_dict.items()
        }

        edge_states = self.directed_graph.build_dynamic_states(road_risks_objs)
        return self.router.find_route(
            origin=origin,
            destination=destination,
            simulation_id=simulation_id,
            timestamp_seconds=snapshot.timestamp_seconds,
            edge_states=edge_states,
        )
