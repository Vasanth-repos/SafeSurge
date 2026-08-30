"""
Layer 5 (Canonical) — Dynamic Surface Storage & D8 Routing Engine:
Simulates time-evolving surface cell storage balance, synchronous 2D slope-weighted
D8 downhill routing, boundary outflow discharge, and local water depths with strict mass conservation.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flood_engine.config import load_config
from flood_engine.d8 import D8Terrain
from flood_engine.grid import ComputationalGrid
from flood_engine.surface_diagnostics import summarize_grid_depths


@dataclass
class CellSurfaceState:
    cell_id: str
    old_storage_m3: float
    runoff_input_m3: float
    upstream_inflow_m3: float
    available_water_m3: float
    routing_fraction: float
    surface_outflow_m3: float
    drainage_capture_m3: float
    new_storage_m3: float
    water_depth_m: float
    downstream_cell: str | None
    terminal_state: str


@dataclass
class SurfaceStep:
    timestamp_seconds: int
    timestep_seconds: int
    cells: dict[str, CellSurfaceState]
    total_runoff_input_m3: float
    total_upstream_inflow_m3: float
    total_surface_outflow_m3: float
    total_drainage_capture_m3: float
    total_boundary_outflow_m3: float
    total_storage_m3: float
    mass_balance_error_m3: float


class SurfaceStorageEngine:
    def __init__(
        self,
        grid: ComputationalGrid,
        terrain: D8Terrain,
        routing_coefficient_k: float | None = None,
        max_routing_fraction: float | None = None,
        boundary_condition: str = "open",
        effective_areas_m2: dict[str, float] | None = None,
        expected_timestep_seconds: int = 60,
        config_path: str | Path | None = "config.yaml",
    ):
        self.grid = grid
        self.terrain = terrain
        self.boundary_condition = boundary_condition.lower()
        self.expected_timestep_seconds = int(expected_timestep_seconds)

        # Load parameter defaults from config if available
        cfg_k = 0.0008
        cfg_fmax = 0.35
        if config_path and Path(config_path).exists():
            cfg = load_config(Path(config_path))
            cfg_k = float(cfg.get("surface", {}).get("routing_coefficient", 0.0008))
            cfg_fmax = float(cfg.get("surface", {}).get("max_routing_fraction", 0.35))
            self.expected_timestep_seconds = int(cfg.get("simulation", {}).get("timestep_seconds", self.expected_timestep_seconds))

        self.routing_coefficient_k = float(routing_coefficient_k if routing_coefficient_k is not None else cfg_k)
        self.max_routing_fraction = float(max_routing_fraction if max_routing_fraction is not None else cfg_fmax)

        # Effective surface ponding area per cell
        self.effective_areas_m2: dict[str, float] = {}
        eff_map = effective_areas_m2 or {}
        for cid in self.terrain.cells:
            area = float(eff_map.get(cid, self.grid.cell_area_m2))
            if area <= 0.0:
                raise ValueError(f"Effective area for {cid} must be positive, got {area}")
            self.effective_areas_m2[cid] = area

        # Pre-compute routing fractions f_i per cell
        self.routing_fractions: dict[str, float] = {}
        for cid, cell in self.terrain.cells.items():
            if cell.state == "downstream" and cell.slope_ratio > 0.0:
                # f = clip(k * sqrt(s) * dt, 0, f_max)
                f_val = self.routing_coefficient_k * math.sqrt(cell.slope_ratio) * self.expected_timestep_seconds
                self.routing_fractions[cid] = min(self.max_routing_fraction, max(0.0, float(f_val)))
            elif cell.state in ("boundary_exit", "outlet") and self.boundary_condition == "open":
                # Boundary outflow fraction based on local slope
                f_val = self.routing_coefficient_k * math.sqrt(max(1e-4, cell.slope_ratio)) * self.expected_timestep_seconds
                self.routing_fractions[cid] = min(self.max_routing_fraction, max(0.05, float(f_val)))
            else:
                self.routing_fractions[cid] = 0.0

        # State storage (m³)
        self.storage_m3: dict[str, float] = {cid: 0.0 for cid in self.terrain.cells}
        self.cumulative_runoff_input_m3: float = 0.0
        self.cumulative_boundary_outflow_m3: float = 0.0
        self.cumulative_drainage_capture_m3: float = 0.0
        self.last_timestamp_seconds: int | None = None
        self.history: list[SurfaceStep] = []

    @property
    def cell_ids(self) -> list[str]:
        return list(self.terrain.cells.keys())

    @property
    def dt_seconds(self) -> float:
        return float(self.expected_timestep_seconds)

    def storage(self, cell_id: str) -> float:
        return float(self.storage_m3.get(cell_id, 0.0))

    def reset(self) -> None:
        """Resets all cell storage levels, boundary discharges, and timestamp history."""
        for cid in self.storage_m3:
            self.storage_m3[cid] = 0.0
        self.cumulative_runoff_input_m3 = 0.0
        self.cumulative_boundary_outflow_m3 = 0.0
        self.cumulative_drainage_capture_m3 = 0.0
        self.last_timestamp_seconds = None
        self.history.clear()

    def route_available_water(
        self,
        available_surface_m3_by_cell: dict[str, float],
        dt_seconds: float | None = None,
    ) -> tuple[dict[str, float], float, dict[str, CellSurfaceState]]:
        """
        Routes remaining available surface water across the D8 terrain network:
        O_t = min(S_avail, f * S_avail)
        S_{t+1} = S_avail - O_t + I_downstream
        """
        outflows_m3: dict[str, float] = {}
        inflows_m3: dict[str, float] = {cid: 0.0 for cid in self.terrain.cells}
        step_boundary_outflow_m3 = 0.0

        for cid, cell in self.terrain.cells.items():
            avail = max(0.0, float(available_surface_m3_by_cell.get(cid, 0.0)))
            f = self.routing_fractions[cid]
            outflow = min(avail, f * avail)
            outflows_m3[cid] = outflow

            if cell.state == "downstream" and cell.downstream_cell is not None:
                inflows_m3[cell.downstream_cell] += outflow
            elif cell.state in ("boundary_exit", "outlet") and self.boundary_condition == "open":
                step_boundary_outflow_m3 += outflow

        new_storage_by_cell: dict[str, float] = {}
        cell_states: dict[str, CellSurfaceState] = {}

        for cid, cell in sorted(self.terrain.cells.items()):
            avail = max(0.0, float(available_surface_m3_by_cell.get(cid, 0.0)))
            i_in = inflows_m3[cid]
            o_out = outflows_m3[cid]
            s_new = max(0.0, avail - o_out + i_in)

            self.storage_m3[cid] = s_new
            new_storage_by_cell[cid] = s_new

            eff_area = self.effective_areas_m2[cid]
            depth_m = s_new / eff_area

            cell_states[cid] = CellSurfaceState(
                cell_id=cid,
                old_storage_m3=avail,
                runoff_input_m3=0.0,
                upstream_inflow_m3=i_in,
                available_water_m3=avail + i_in,
                routing_fraction=self.routing_fractions[cid],
                surface_outflow_m3=o_out,
                drainage_capture_m3=0.0,
                new_storage_m3=s_new,
                water_depth_m=depth_m,
                downstream_cell=cell.downstream_cell,
                terminal_state=cell.state,
            )

        return new_storage_by_cell, step_boundary_outflow_m3, cell_states

    def validate_timestamp(self, timestamp_seconds: int, dt_seconds: int | None = None) -> None:
        """Enforces strictly advancing timestamps and timestep validation."""
        if not isinstance(timestamp_seconds, (int, float)) or math.isnan(timestamp_seconds) or math.isinf(timestamp_seconds):
            raise ValueError(f"Invalid timestamp: {timestamp_seconds}")
        t = int(timestamp_seconds)

        if self.last_timestamp_seconds is not None:
            if t <= self.last_timestamp_seconds:
                raise ValueError(f"Timestamp ({t}s) must be strictly greater than previous ({self.last_timestamp_seconds}s).")
            actual_dt = t - self.last_timestamp_seconds
            expected_dt = dt_seconds or self.expected_timestep_seconds
            if actual_dt != expected_dt:
                raise ValueError(f"Timestep spacing ({actual_dt}s) does not match expected ({expected_dt}s).")

    def step(
        self,
        timestamp_seconds: int,
        runoff_volume_m3_by_cell: float | dict[str, float],
        drainage_capture_m3_by_cell: dict[str, float] | None = None,
        dt_seconds: int | None = None,
    ) -> SurfaceStep:
        """
        Advances the 2D surface storage and D8 routing simulation by one timestep:
        1. Ingests incremental direct runoff volume R_t
        2. Computes synchronous cell outflows O_t = f * (S_t + R_t)
        3. Routes outflows to downstream neighbors or boundary discharge
        4. Applies mass balance: S_{t+1} = S_t + R_t + I_t - O_t - D_t
        5. Computes water depth h_{t+1} = S_{t+1} / A_eff
        """
        dt = int(dt_seconds or self.expected_timestep_seconds)
        self.validate_timestamp(timestamp_seconds, dt_seconds=dt)
        t = int(timestamp_seconds)

        # 1. Parse & validate runoff input
        r_map: dict[str, float] = {}
        if isinstance(runoff_volume_m3_by_cell, (int, float)):
            val = float(runoff_volume_m3_by_cell)
            if val < 0.0 or math.isnan(val) or math.isinf(val):
                raise ValueError(f"Invalid runoff volume: {val}")
            for cid in self.terrain.cells:
                r_map[cid] = val
        elif isinstance(runoff_volume_m3_by_cell, dict):
            for cid in runoff_volume_m3_by_cell:
                if cid not in self.terrain.cells:
                    raise ValueError(f"Unknown cell ID '{cid}' in runoff input.")
            missing = set(self.terrain.cells.keys()) - set(runoff_volume_m3_by_cell.keys())
            if missing:
                raise ValueError(f"Missing runoff input for {len(missing)} cells.")
            for cid, val in runoff_volume_m3_by_cell.items():
                if not isinstance(val, (int, float)) or val < 0.0 or math.isnan(val) or math.isinf(val):
                    raise ValueError(f"Invalid runoff volume for cell {cid}: {val}")
                r_map[cid] = float(val)
        else:
            raise TypeError("runoff_volume_m3_by_cell must be a float or Dict[str, float].")

        # 2. Parse drainage capture (Layer 5 constraint: must be 0.0)
        d_map: dict[str, float] = {cid: 0.0 for cid in self.terrain.cells}
        if drainage_capture_m3_by_cell is not None:
            for cid, d_val in drainage_capture_m3_by_cell.items():
                if d_val > 1e-9:
                    raise ValueError(f"Drainage capture is not active in Layer 5 (must be 0.0, got {d_val} at {cid}).")
                d_map[cid] = 0.0

        # 3. Synchronous Outflow Calculation
        # Outflow is evaluated from available water S_t + R_t before receiving new upstream inflow I_t
        outflows_m3: dict[str, float] = {}
        inflows_m3: dict[str, float] = {cid: 0.0 for cid in self.terrain.cells}
        step_boundary_outflow_m3 = 0.0

        for cid, cell in self.terrain.cells.items():
            s_old = self.storage_m3[cid]
            r_in = r_map[cid]
            avail = s_old + r_in

            f = self.routing_fractions[cid]
            outflow = min(avail, f * avail)
            outflows_m3[cid] = outflow

            # Route to destination
            if cell.state == "downstream" and cell.downstream_cell is not None:
                inflows_m3[cell.downstream_cell] += outflow
            elif cell.state in ("boundary_exit", "outlet") and self.boundary_condition == "open":
                step_boundary_outflow_m3 += outflow
            else:
                # Sinks retain water
                pass

        # 4. Storage Update & Water Depth
        cell_states: dict[str, CellSurfaceState] = {}
        step_runoff_total = sum(r_map.values())
        step_inflow_total = sum(inflows_m3.values())
        step_outflow_total = sum(outflows_m3.values())
        step_drainage_total = sum(d_map.values())
        total_new_storage = 0.0

        for cid, cell in sorted(self.terrain.cells.items()):
            s_old = self.storage_m3[cid]
            r_in = r_map[cid]
            i_in = inflows_m3[cid]
            o_out = outflows_m3[cid]
            d_cap = d_map[cid]

            # S_{t+1} = S_t + R_t + I_t - O_t - D_t
            s_new = max(0.0, s_old + r_in + i_in - o_out - d_cap)
            self.storage_m3[cid] = s_new
            total_new_storage += s_new

            eff_area = self.effective_areas_m2[cid]
            depth_m = s_new / eff_area

            cell_states[cid] = CellSurfaceState(
                cell_id=cid,
                old_storage_m3=s_old,
                runoff_input_m3=r_in,
                upstream_inflow_m3=i_in,
                available_water_m3=s_old + r_in + i_in,
                routing_fraction=self.routing_fractions[cid],
                surface_outflow_m3=o_out,
                drainage_capture_m3=d_cap,
                new_storage_m3=s_new,
                water_depth_m=depth_m,
                downstream_cell=cell.downstream_cell,
                terminal_state=cell.state,
            )

        # 5. Cumulative Tracking & Mass Balance Error
        self.cumulative_runoff_input_m3 += step_runoff_total
        self.cumulative_boundary_outflow_m3 += step_boundary_outflow_m3
        self.cumulative_drainage_capture_m3 += step_drainage_total
        self.last_timestamp_seconds = t

        # Mass balance check: Total Input - Total Storage - Boundary Discharge - Drainage Capture ≈ 0
        error_m3 = (
            self.cumulative_runoff_input_m3
            - total_new_storage
            - self.cumulative_boundary_outflow_m3
            - self.cumulative_drainage_capture_m3
        )

        step_result = SurfaceStep(
            timestamp_seconds=t,
            timestep_seconds=dt,
            cells=cell_states,
            total_runoff_input_m3=step_runoff_total,
            total_upstream_inflow_m3=step_inflow_total,
            total_surface_outflow_m3=step_outflow_total,
            total_drainage_capture_m3=step_drainage_total,
            total_boundary_outflow_m3=step_boundary_outflow_m3,
            total_storage_m3=total_new_storage,
            mass_balance_error_m3=error_m3,
        )
        self.history.append(step_result)
        return step_result

    def mass_balance(self) -> dict[str, Any]:
        """Returns cumulative mass conservation accounting."""
        total_current_storage = sum(self.storage_m3.values())
        error_m3 = (
            self.cumulative_runoff_input_m3
            - total_current_storage
            - self.cumulative_boundary_outflow_m3
            - self.cumulative_drainage_capture_m3
        )
        is_conserved = abs(error_m3) <= 1e-5

        return {
            "cumulative_runoff_input_m3": round(self.cumulative_runoff_input_m3, 6),
            "current_surface_storage_m3": round(total_current_storage, 6),
            "cumulative_boundary_outflow_m3": round(self.cumulative_boundary_outflow_m3, 6),
            "cumulative_drainage_capture_m3": round(self.cumulative_drainage_capture_m3, 6),
            "mass_balance_error_m3": round(error_m3, 8),
            "is_conserved": is_conserved,
        }

    def get_water_depths_by_cell(self) -> dict[str, float]:
        """Returns mapping of cell_id to water depth in meters."""
        return {cid: self.storage_m3[cid] / self.effective_areas_m2[cid] for cid in self.terrain.cells}

    def get_diagnostics(self) -> dict[str, Any]:
        """Returns spatial depth risk summary across the computational domain."""
        depths = self.get_water_depths_by_cell()
        return summarize_grid_depths(depths)
