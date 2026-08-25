"""
Layer 23 — End-to-End Deterministic Replay Engine:
Executes reproducible, seed-locked storm scenarios across all physical and sensing layers,
generating time-indexed immutable SimulationSnapshot sequences.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Mapping, Sequence
import math
import json
from pathlib import Path
from shapely.geometry import LineString, Polygon

from flood_engine.snapshot import (
    SimulationSnapshot,
    CellSnapshot,
    RoadSnapshot,
    SensorSnapshot,
    ForecastSnapshot,
    MassBalanceSnapshot,
    SystemStatus,
    RainfallStatus,
)
from diagnostics.mass_balance import MassBalanceDiagnostic, evaluate_timestep_balance
from replay.faults import FaultInjectionEngine, Fault, FaultType
from sensors.registry import SensorRegistry
from sensors.validation import SensorValidator
from fusion.pipeline import FusionPipeline
from fusion.models import SensorObservation
from anomalies.detector import AnomalyDetector
from roads.models import Road
from roads.mapping import RoadSpatialMapper
from roads.risk import RoadRiskEngine
from routing.graph import DirectedRoadGraph
from routing.router import EmergencyRouter
from routing.models import RoadEdge


class ReplayStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReplayEngine:
    def __init__(
        self,
        config_path: str = "config.yaml",
        random_seed: int = 42,
    ):
        self.config_path = config_path
        self.random_seed = random_seed
        self.status = ReplayStatus.IDLE

        self.sensor_registry = SensorRegistry.load_from_yaml("data/sensors/registry.yaml")
        self.sensor_validator = SensorValidator(self.sensor_registry)
        self.fusion_pipeline = FusionPipeline.load_from_config(config_path)
        self.anomaly_detector = AnomalyDetector()
        self.road_risk_engine = RoadRiskEngine()
        self.mass_balance_diagnostic = MassBalanceDiagnostic()
        self.fault_engine = FaultInjectionEngine()

        self._build_catchment()

    def _build_catchment(self):
        # 10x10 computational grid (100 cells)
        self.cell_coords: Dict[str, Tuple[float, float]] = {}
        self.cell_geometries: Dict[str, Polygon] = {}
        self.cell_elevations: Dict[str, float] = {}

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

        # Road Network
        self.roads = [
            Road("R001", "A", "B", LineString([(5.0, 5.0), (45.0, 5.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
            Road("R002", "B", "D", LineString([(45.0, 5.0), (45.0, 45.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
            Road("R003", "A", "C", LineString([(5.0, 5.0), (5.0, 45.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
            Road("R004", "C", "D", LineString([(5.0, 45.0), (45.0, 45.0)]), length_m=40.0, nominal_travel_time_seconds=60.0),
        ]
        self.road_mapper = RoadSpatialMapper(self.roads, self.cell_geometries)

        # Directed Road Graph
        edges = [
            RoadEdge("R001", "A", "B", 60.0, 40.0),
            RoadEdge("R002", "B", "D", 60.0, 40.0),
            RoadEdge("R003", "A", "C", 60.0, 40.0),
            RoadEdge("R004", "C", "D", 60.0, 40.0),
        ]
        self.directed_graph = DirectedRoadGraph(edges)
        self.router = EmergencyRouter(self.directed_graph)

        self.sensor_coords = {
            "S001": (15.0, 15.0),
            "S002": (45.0, 25.0),
        }

    def run_scenario(
        self,
        scenario_name: str,
        total_minutes: int = 180,
        timestep_seconds: int = 60,
        faults: Optional[Sequence[Fault]] = None,
    ) -> List[SimulationSnapshot]:
        """
        Executes full deterministic scenario replay and returns list of immutable snapshots.
        """
        self.status = ReplayStatus.RUNNING
        self.mass_balance_diagnostic.reset()
        self.sensor_validator.reset()
        self.fusion_pipeline.reset()

        if faults:
            self.fault_engine = FaultInjectionEngine(faults)
        else:
            self.fault_engine = FaultInjectionEngine()

        snapshots: List[SimulationSnapshot] = []
        num_steps = (total_minutes * 60) // timestep_seconds + 1

        prev_storage_m3 = 0.0
        prev_depths_cm = {cid: 0.0 for cid in self.cell_coords}
        prev_t = 0

        for step_idx in range(num_steps):
            t = step_idx * timestep_seconds

            # 1. Rainfall & Fault Injection
            is_rain_missing = self.fault_engine.is_rainfall_unavailable(t)
            if is_rain_missing:
                rain_status = RainfallStatus.MISSING
                rain_mm = 0.0
            else:
                # Synthetic storm profile (peak around t=60m, tapering off by t=180m)
                norm_t = min(1.0, t / (total_minutes * 60))
                base_rain_mm = 15.0 * math.sin(norm_t * math.pi)
                rain_mm = self.fault_engine.apply_rainfall_multiplier(t, base_rain_mm)
                rain_status = RainfallStatus.VALID if rain_mm > 0 else RainfallStatus.ZERO

            # 2. Runoff & Surface Storage Calculation
            runoff_input_m3 = (rain_mm / 1000.0) * 10000.0 * 0.4  # Runoff volume across domain
            active_fault_list = [f.fault_type.value for f in self.fault_engine.get_active_faults(t)]

            # 3. Model Flood Depth Field
            model_depths = {}
            for cid, (x, y) in self.cell_coords.items():
                ne_factor = ((x / 50.0) ** 3) * (math.exp(-((y - 25.0) / 15.0) ** 2))
                int_factor = math.sin(min(math.pi, (step_idx / max(1, num_steps)) * math.pi))
                d = max(0.0, 45.0 * ne_factor * int_factor)
                model_depths[cid] = d

            # 4. Sensor Telemetry Ingestion with Fault Injection
            observations = []
            sensor_snapshots_list = []
            for sid, sc in self.sensor_coords.items():
                loc_id = "C012" if sid == "S001" else "C025"
                nom_depth = model_depths.get(loc_id, 5.0)
                obs_depth, s_stat, is_mod = self.fault_engine.apply_sensor_override(sid, t, nom_depth, "ONLINE")

                if obs_depth is not None and s_stat == "ONLINE":
                    observations.append(
                        SensorObservation(sid, loc_id, t, obs_depth, s_stat, "ACCEPTED")
                    )

                sensor_snapshots_list.append(
                    SensorSnapshot(
                        sensor_id=sid,
                        location_id=loc_id,
                        status=s_stat,
                        last_valid_reading_cm=obs_depth if obs_depth is not None else nom_depth,
                        last_valid_timestamp_seconds=t,
                        age_seconds=0 if s_stat == "ONLINE" else 120,
                        bias_cm=0.0,
                    )
                )

            # 5. Fusion & Spatial Propagation
            fusion_result = self.fusion_pipeline.step(
                timestamp_seconds=t,
                model_depth_cm_by_cell=model_depths,
                cell_coords_m_by_id=self.cell_coords,
                sensor_observations=observations,
                sensor_coords_m_by_id=self.sensor_coords,
            )

            # 6. Anomaly Detection
            anomalies = []
            for cid in self.cell_coords:
                curr_d = fusion_result.cells[cid].corrected_depth_cm
                prev_d = prev_depths_cm.get(cid, 0.0)
                assessment = self.anomaly_detector.evaluate_cell(
                    cell_id=cid,
                    timestamp_seconds=t,
                    current_depth_cm=curr_d,
                    previous_depth_cm=prev_d if step_idx > 0 else None,
                    previous_timestamp_seconds=prev_t if step_idx > 0 else None,
                    original_model_depth_cm=model_depths[cid],
                )
                if assessment.primary.value != "NORMAL":
                    anomalies.append(assessment.to_dict())

            # 7. Road Exposure & Risk
            cell_depth_map = {cid: cr.corrected_depth_cm for cid, cr in fusion_result.cells.items()}
            cell_conf_map = {cid: cr.confidence.score for cid, cr in fusion_result.cells.items()}

            road_risks_dict = self.road_risk_engine.evaluate_all(
                timestamp_seconds=t,
                exposures_by_road=self.road_mapper.get_all_exposures(),
                cell_depths_by_id=cell_depth_map,
                cell_confidences_by_id=cell_conf_map,
            )
            road_snapshots = [
                RoadSnapshot(
                    road_id=rr.road_id,
                    from_node=self.roads[i].from_node,
                    to_node=self.roads[i].to_node,
                    mean_depth_cm=rr.mean_depth_cm,
                    max_relevant_depth_cm=rr.max_relevant_depth_cm,
                    affected_fraction=rr.affected_fraction,
                    risk=rr.risk,
                    confidence=rr.confidence,
                )
                for i, rr in enumerate(road_risks_dict.values())
            ]

            # 8. Mass Balance Accounting
            cap_factor = self.fault_engine.get_capacity_factor("E001", t, default_factor=1.0)
            avail_storage = prev_storage_m3 + runoff_input_m3
            drainage_m3 = min(avail_storage * 0.15 * cap_factor, 20.0)
            boundary_outflow_m3 = max(0.0, (avail_storage - 100.0) * 0.05) if avail_storage > 100.0 else 0.0
            current_storage_m3 = max(0.0, avail_storage - drainage_m3 - boundary_outflow_m3)

            mb_snapshot = self.mass_balance_diagnostic.record_step(
                runoff_input_m3=runoff_input_m3,
                previous_storage_m3=prev_storage_m3,
                current_storage_m3=current_storage_m3,
                drainage_m3=drainage_m3,
                boundary_outflow_m3=boundary_outflow_m3,
            )

            # 9. System Status & Degradation Evaluation
            degraded_reasons = []
            sys_status = SystemStatus.NORMAL
            if is_rain_missing:
                sys_status = SystemStatus.UNAVAILABLE
                degraded_reasons.append("Rainfall telemetry unavailable")
            elif any(s.status != "ONLINE" for s in sensor_snapshots_list):
                sys_status = SystemStatus.DEGRADED
                degraded_reasons.extend([f"Sensor {s.sensor_id} {s.status.lower()}" for s in sensor_snapshots_list if s.status != "ONLINE"])

            # 10. Assemble Cell Snapshots
            cell_snapshots = tuple(
                CellSnapshot(
                    cell_id=cid,
                    row=int(cid[1:3]),
                    col=int(cid[3:]) if len(cid) > 3 else 0,
                    elevation_m=self.cell_elevations[cid],
                    model_depth_cm=cr.model_depth_cm,
                    correction_cm=cr.correction_cm,
                    corrected_depth_cm=cr.corrected_depth_cm,
                    risk="UNSAFE" if cr.corrected_depth_cm >= 25 else ("HIGH" if cr.corrected_depth_cm >= 15 else ("WATCH" if cr.corrected_depth_cm >= 5 else "SAFE")),
                    confidence=cr.confidence.score,
                    status="VALID",
                )
                for cid, cr in fusion_result.cells.items()
            )

            forecast_obj = ForecastSnapshot(
                status="AVAILABLE" if not is_rain_missing else "UNAVAILABLE",
                depth_cm=max(cell_depth_map.values()),
                lower_depth_cm=max(0.0, max(cell_depth_map.values()) - 5.0),
                upper_depth_cm=max(cell_depth_map.values()) + 7.0,
                confidence=min(cell_conf_map.values()),
            )

            snap = SimulationSnapshot(
                simulation_id=scenario_name,
                timestamp_seconds=t,
                simulation_status="COMPLETED" if step_idx == num_steps - 1 else "RUNNING",
                system_status=sys_status.value,
                rainfall_status=rain_status.value,
                flood_cells=cell_snapshots,
                road_risks=tuple(road_snapshots),
                drainage_states=(),
                sensor_states=tuple(sensor_snapshots_list),
                anomalies=tuple(anomalies),
                forecast=forecast_obj,
                mass_balance=mb_snapshot,
                active_faults=tuple(active_fault_list),
                degraded_reasons=tuple(degraded_reasons),
            )
            snapshots.append(snap)

            # Update loop state
            prev_storage_m3 = current_storage_m3
            prev_depths_cm = cell_depth_map
            prev_t = t

        self.status = ReplayStatus.COMPLETED
        return snapshots
