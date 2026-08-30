"""
Simulation Service: Core orchestrator coupling hydrological flood engine,
drainage network, sensor validation/fusion, road risk routing, and mass conservation.
"""

import os
from typing import Any

import numpy as np
import yaml

from flood_engine.conservation import MassBalanceDiagnostic
from flood_engine.routing import compute_surface_outflows
from flood_engine.runoff import CellRunoffState
from flood_engine.storage import GridCellState, synchronous_storage_update
from replay.catchment_data import generate_demo_catchment
from routing.road_graph import RoadNetwork
from routing.safe_route import find_safe_route
from sensor.anomaly import detect_sensor_anomalies
from sensor.confidence import compute_confidence_score
from sensor.fusion import (
    apply_fused_depth_correction,
    propagate_spatial_bias,
    update_sensor_bias,
)
from sensor.health import SensorNode
from sensor.validation import validate_sensor_reading


class SimulationService:
    def __init__(self, config_path: str = "config/defaults.yaml"):
        self.config_path = config_path
        self.load_config()
        self.reset()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                "timestep_s": 60.0,
                "max_routing_fraction": 0.5,
                "routing_coeff": 0.1,
                "bias_smoothing_alpha": 0.3,
                "confidence_weights": {"coverage": 0.4, "freshness": 0.3, "agreement": 0.3},
                "sensor_critical_rate_cm_min": 5.0,
                "sensor_stale_missed_hb": 3,
                "sensor_offline_missed_hb": 6,
                "max_physical_depth_cm": 300.0,
                "grid": {"cell_size_m": 10.0, "rows": 20, "cols": 20, "tolerance_m3": 0.05},
                "routing_penalties": {"lambda_risk": 10.0, "mu_uncertainty": 5.0},
            }

    def reset(self):
        """Re-initializes catchment, flood engine, sensors, and diagnostics to initial dry state."""
        grid_cfg = self.config.get("grid", {})
        self.rows = grid_cfg.get("rows", 20)
        self.cols = grid_cfg.get("cols", 20)
        self.cell_size_m = grid_cfg.get("cell_size_m", 10.0)
        self.tolerance_m3 = grid_cfg.get("tolerance_m3", 0.05)
        self.current_step = 0

        # Generate catchment
        catchment = generate_demo_catchment(rows=self.rows, cols=self.cols, cell_size_m=self.cell_size_m)
        self.elevation_grid: np.ndarray = catchment["elevation_grid"]
        self.flow_dirs: dict[int, int | None] = catchment["flow_dirs"]
        self.cn_grid: np.ndarray = catchment["cn_grid"]
        self.drainage = catchment["drainage"]
        self.roads: RoadNetwork = catchment["roads"]
        self.sensor_list: list[SensorNode] = catchment["sensors"]
        self.sensors: dict[int, SensorNode] = {s.sensor_id: s for s in self.sensor_list}

        # Spatial lookup caches
        self.cell_positions: dict[int, tuple[int, int]] = {}
        self.elevations: dict[int, float] = {}
        self.cells: dict[int, GridCellState] = {}
        self.runoff_states: dict[int, CellRunoffState] = {}
        self.fused_depths_cm: dict[int, float] = {}
        self.cell_confidences: dict[int, float] = {}
        self.sensor_positions: dict[int, tuple[int, int]] = {}

        for r in range(self.rows):
            for c in range(self.cols):
                cid = r * self.cols + c
                elev = float(self.elevation_grid[r, c])
                cn = float(self.cn_grid[r, c])
                self.cell_positions[cid] = (r, c)
                self.elevations[cid] = elev
                self.cells[cid] = GridCellState(cell_id=cid, row=r, col=c, elevation=elev, cn_value=cn)
                self.runoff_states[cid] = CellRunoffState(cn_value=cn, area_m2=self.cell_size_m ** 2)
                self.fused_depths_cm[cid] = 0.0
                self.cell_confidences[cid] = 0.8

        for s in self.sensor_list:
            sr, sc = divmod(s.cell_id, self.cols)
            self.sensor_positions[s.sensor_id] = (sr, sc)

        # Diagnostics & event logs
        self.diagnostic = MassBalanceDiagnostic(tolerance_m3=self.tolerance_m3)
        self.event_logs: list[dict[str, Any]] = []
        self.active_faults: dict[str, Any] = {}

        # Initial road risk update
        self.roads.update_all_risks(self.fused_depths_cm, self.cell_confidences)

    def log_event(self, component: str, event_type: str, payload: dict[str, Any]):
        self.event_logs.append({
            "step": self.current_step,
            "component": component,
            "event_type": event_type,
            "payload": payload,
        })

    def step(
        self,
        rainfall_input: Any = 0.0,
        sensor_readings: dict[int, dict[str, Any]] | None = None,
        dt_seconds: float | None = None,
    ) -> dict[str, Any]:
        """
        Advances the entire nowcasting & response pipeline by one timestep.
        """
        dt = dt_seconds or float(self.config.get("timestep_s", 60.0))
        self.current_step += 1

        # 1. Compute Incremental Runoff per cell (SCS-CN)
        incremental_runoffs: dict[int, float] = {}
        total_input_m3 = 0.0

        for cid, cell in self.cells.items():
            r_val_mm = 0.0
            if isinstance(rainfall_input, dict):
                r_val_mm = float(rainfall_input.get(cid, rainfall_input.get("all", 0.0)))
            elif isinstance(rainfall_input, (int, float)):
                r_val_mm = float(rainfall_input)

            delta_q_m3 = self.runoff_states[cid].compute_incremental_runoff(r_val_mm)
            incremental_runoffs[cid] = delta_q_m3
            total_input_m3 += delta_q_m3

        # 2. Slope-weighted surface routing
        k = float(self.config.get("routing_coeff", 0.1))
        f_max = float(self.config.get("max_routing_fraction", 0.5))
        current_storages = {cid: cell.storage_m3 for cid, cell in self.cells.items()}

        internal_outflows, cell_inflows, boundary_outflow_m3 = compute_surface_outflows(
            cell_storages=current_storages,
            flow_dir=self.flow_dirs,
            elevations=self.elevations,
            cell_positions=self.cell_positions,
            dt=dt,
            k=k,
            f_max=f_max,
            cell_size_m=self.cell_size_m,
        )

        # 3. Dynamic Drainage Capture
        drain_captures: dict[int, float] = {}
        timestep_drained_m3 = 0.0

        for cid, cell in self.cells.items():
            avail = cell.storage_m3 + incremental_runoffs[cid] + cell_inflows[cid] - internal_outflows[cid]
            cap_m3 = self.drainage.compute_capture(cid, avail, dt)
            drain_captures[cid] = cap_m3
            timestep_drained_m3 += cap_m3

        # 4. Synchronous Storage Update
        synchronous_storage_update(
            cells=self.cells,
            incremental_runoffs=incremental_runoffs,
            surface_inflows=cell_inflows,
            surface_outflows=internal_outflows,
            drain_captures=drain_captures,
        )

        # Current total storage in catchment
        current_total_storage_m3 = sum(c.storage_m3 for c in self.cells.values())

        # 5. Mass Balance Verification
        mb_entry = self.diagnostic.record_step(
            step_index=self.current_step,
            timestep_input_m3=total_input_m3,
            current_total_storage_m3=current_total_storage_m3,
            timestep_drained_m3=timestep_drained_m3,
            timestep_boundary_outflow_m3=boundary_outflow_m3,
        )

        # 6. Sensor Ingestion, Validation & Health Update
        sensor_readings = sensor_readings or {}
        active_biases: dict[int, float] = {}
        r_crit = float(self.config.get("sensor_critical_rate_cm_min", 5.0))
        max_phys = float(self.config.get("max_physical_depth_cm", 300.0))
        alpha = float(self.config.get("bias_smoothing_alpha", 0.3))
        stale_thresh = int(self.config.get("sensor_stale_missed_hb", 3))
        offline_thresh = int(self.config.get("sensor_offline_missed_hb", 6))

        for sid, sensor in self.sensors.items():
            # Check fault injection
            fault = self.active_faults.get(f"sensor_{sid}")
            reading_data = sensor_readings.get(sid)

            if fault == "disconnect":
                # Simulated connection lost
                sensor.update_health(received_heartbeat=False, quality_flag="STALE",
                                     stale_threshold=stale_thresh, offline_threshold=offline_thresh)
                continue

            if reading_data is not None:
                val = float(reading_data.get("water_level_cm", 0.0))
                hb = bool(reading_data.get("heartbeat", True))
                if fault == "spike":
                    val += 80.0  # Injected high spike
                elif fault == "out_of_range":
                    val = 999.0  # Injected impossible range

                # Validate
                prev_val = sensor.last_valid_reading_cm
                q_flag = validate_sensor_reading(
                    water_level_cm=val,
                    prev_water_level_cm=prev_val,
                    dt_seconds=dt,
                    r_critical_cm_min=r_crit,
                    max_physical_depth_cm=max_phys,
                    heartbeat=hb,
                )

                sensor.last_reading_cm = val
                sensor.battery = int(reading_data.get("battery", sensor.battery))
                sensor.signal_quality = float(reading_data.get("signal_quality", sensor.signal_quality))
                sensor.float_state = bool(reading_data.get("float_state", False))

                sensor.update_health(
                    received_heartbeat=hb,
                    quality_flag=q_flag,
                    float_state=sensor.float_state,
                    stale_threshold=stale_thresh,
                    offline_threshold=offline_thresh,
                )

                # Anomaly detection
                cell_pred_depth = self.cells[sensor.cell_id].depth_cm
                inlet_node = self.drainage.get_inlet_for_cell(sensor.cell_id)
                cap_factor = inlet_node.capacity_factor if inlet_node else 1.0
                anomalies = detect_sensor_anomalies(
                    sensor=sensor,
                    model_predicted_depth_cm=cell_pred_depth,
                    prev_reading_cm=prev_val,
                    dt_seconds=dt,
                    r_critical_cm_min=r_crit,
                    drain_capacity_factor=cap_factor,
                )
                if anomalies and anomalies != ["NORMAL"]:
                    self.log_event("sensor", "ANOMALY_DETECTED", {"sensor_id": sid, "flags": anomalies})

                if sensor.is_usable_for_fusion():
                    sensor.last_valid_reading_cm = val
                    new_bias, raw_err = update_sensor_bias(
                        predicted_depth_cm=cell_pred_depth,
                        observed_depth_cm=val,
                        prev_bias=sensor.current_bias,
                        alpha=alpha,
                    )
                    sensor.current_bias = new_bias
                    sensor.recent_errors.append(raw_err)
                    if len(sensor.recent_errors) > 10:
                        sensor.recent_errors.pop(0)
                    active_biases[sid] = new_bias
                else:
                    self.log_event("sensor", "READING_REJECTED", {"sensor_id": sid, "quality_flag": q_flag})

        # 7. Spatial Bias Propagation & Confidence Computation
        cw = self.config.get("confidence_weights", {})
        wc, wf, wa = cw.get("coverage", 0.3), cw.get("freshness", 0.2), cw.get("agreement", 0.5)
        online_sensor_count = sum(1 for s in self.sensors.values() if s.status == "ONLINE")
        total_sensors = max(1, len(self.sensors))
        coverage_ratio = online_sensor_count / total_sensors

        for cid, cell in self.cells.items():
            r, c = self.cell_positions[cid]
            if active_biases:
                propagated_bias = propagate_spatial_bias(
                    target_pos=(r, c),
                    active_sensor_biases=active_biases,
                    sensor_positions=self.sensor_positions,
                    cell_size_m=self.cell_size_m,
                )
                fused_depth = apply_fused_depth_correction(cell.depth_cm, propagated_bias)
            else:
                fused_depth = cell.depth_cm

            self.fused_depths_cm[cid] = fused_depth

            # Confidence for this cell
            all_errors = [e for s in self.sensors.values() for e in s.recent_errors]
            freshness = 1.0 if online_sensor_count > 0 else 0.2
            self.cell_confidences[cid] = compute_confidence_score(
                sensor_coverage=coverage_ratio,
                freshness=freshness,
                recent_errors_window=all_errors,
                wc=wc,
                wf=wf,
                wa=wa,
            )

        # 8. Update Road Network Risk Levels
        self.roads.update_all_risks(self.fused_depths_cm, self.cell_confidences)

        return {
            "step": self.current_step,
            "total_storage_m3": round(current_total_storage_m3, 3),
            "total_input_m3": round(total_input_m3, 3),
            "timestep_drained_m3": round(timestep_drained_m3, 3),
            "boundary_outflow_m3": round(boundary_outflow_m3, 3),
            "mass_balance": mb_entry,
            "active_sensor_count": len(active_biases),
        }

    def inject_fault(self, fault_type: str, target_id: int, value: Any = None):
        """
        Injects real-time operational faults for demo testing and resilience verification.
        """
        if fault_type in ("sensor_disconnect", "sensor_spike", "sensor_out_of_range"):
            key = f"sensor_{target_id}"
            mode = fault_type.replace("sensor_", "")
            self.active_faults[key] = mode
            self.log_event("fault_injection", "SENSOR_FAULT", {"sensor_id": target_id, "mode": mode})
        elif fault_type == "sensor_restore":
            self.active_faults.pop(f"sensor_{target_id}", None)
            if target_id in self.sensors:
                self.sensors[target_id].missed_heartbeats = 0
                self.sensors[target_id].status = "ONLINE"
            self.log_event("fault_injection", "SENSOR_RESTORED", {"sensor_id": target_id})
        elif fault_type == "drain_blockage":
            node = self.drainage.nodes.get(target_id)
            if node:
                factor = float(value) if value is not None else 0.3  # Severe drop
                node.set_capacity_factor(factor)
                self.log_event("fault_injection", "DRAIN_CAPACITY_DEGRADED", {"node_id": target_id, "factor": factor})
        elif fault_type == "drain_restore":
            node = self.drainage.nodes.get(target_id)
            if node:
                node.set_capacity_factor(1.0)
                self.log_event("fault_injection", "DRAIN_RESTORED", {"node_id": target_id})

    def compute_safe_route(
        self,
        origin: str,
        destination: str,
        mode: str = "emergency",
    ) -> dict[str, Any]:
        p = self.config.get("routing_penalties", {})
        l_risk = float(p.get("lambda_risk", 10.0))
        mu_unc = float(p.get("mu_uncertainty", 5.0))
        return find_safe_route(
            network=self.roads,
            origin=origin,
            destination=destination,
            mode=mode,
            lambda_risk=l_risk,
            mu_uncertainty=mu_unc,
        )

    def get_grid_state(self) -> list[dict[str, Any]]:
        cells_out = []
        for cid, cell in self.cells.items():
            fused_d = self.fused_depths_cm[cid]
            if fused_d < 5.0:
                risk = "SAFE"
            elif fused_d < 15.0:
                risk = "WATCH"
            elif fused_d < 30.0:
                risk = "HIGH"
            else:
                risk = "UNSAFE"

            cells_out.append({
                "cell_id": cid,
                "row": cell.row,
                "col": cell.col,
                "elevation": round(cell.elevation, 2),
                "raw_depth_cm": round(cell.depth_cm, 2),
                "fused_depth_cm": round(fused_d, 2),
                "storage_m3": round(cell.storage_m3, 3),
                "risk_level": risk,
                "confidence": round(self.cell_confidences[cid], 2),
                "has_inlet": cell.cell_id in self.drainage.cell_to_node,
                "has_sensor": any(s.cell_id == cell.cell_id for s in self.sensor_list),
            })
        return cells_out

    def get_roads_state(self) -> list[dict[str, Any]]:
        roads_out = []
        for r in self.roads.roads.values():
            roads_out.append({
                "road_id": r.road_id,
                "name": r.name,
                "from_node": r.u_node,
                "to_node": r.v_node,
                "predicted_depth_cm": round(r.predicted_depth_cm, 1),
                "risk_level": r.risk_level,
                "data_quality": r.data_quality,
                "confidence": round(r.confidence, 2),
            })
        return roads_out

    def get_sensors_state(self) -> list[dict[str, Any]]:
        sensors_out = []
        for s in self.sensors.values():
            sensors_out.append({
                "sensor_id": s.sensor_id,
                "name": s.name,
                "cell_id": s.cell_id,
                "status": s.status,
                "sensor_type": s.sensor_type,
                "last_reading_cm": round(s.last_reading_cm, 1) if s.last_reading_cm is not None else None,
                "last_valid_reading_cm": round(s.last_valid_reading_cm, 1) if s.last_valid_reading_cm is not None else None,
                "last_quality_flag": s.last_quality_flag,
                "battery": s.battery,
                "signal_quality": s.signal_quality,
                "current_bias_cm": round(s.current_bias, 2),
                "float_state": s.float_state,
                "redundancy_state": s.redundancy_state,
            })
        return sensors_out
