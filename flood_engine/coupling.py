"""
Layer 7 — Surface ↔ Drainage Coupling Engine:
Orchestrates surface inundation capture into drainage network inlets,
routes remaining surface flood waters downhill via D8, transmits pipe flows in Layer 6,
queues 1-timestep delayed surcharge back onto the surface, and maintains strict system-wide mass conservation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Dict, List, Optional, Tuple, Any, Union
import math
from pathlib import Path

from flood_engine.config import load_config
from flood_engine.surface import SurfaceStorageEngine, CellSurfaceState
from flood_engine.drainage import StatefulDrainageNetwork, DrainageStepResult

EPSILON_M3 = 1e-9


@dataclass(frozen=True)
class DrainageInlet:
    inlet_id: str
    node_id: str
    base_capacity_m3_s: float
    blockage_factor: float = 1.0
    operational_factor: float = 1.0

    def __post_init__(self):
        if not self.inlet_id:
            raise ValueError("inlet_id cannot be empty")
        if not self.node_id:
            raise ValueError("node_id cannot be empty")
        if self.base_capacity_m3_s < 0:
            raise ValueError("base_capacity_m3_s must be >= 0")
        if not (0.0 <= self.blockage_factor <= 1.0):
            raise ValueError("blockage_factor must be between 0 and 1")
        if not (0.0 <= self.operational_factor <= 1.0):
            raise ValueError("operational_factor must be between 0 and 1")

    @property
    def effective_capacity_m3_s(self) -> float:
        return self.base_capacity_m3_s * self.blockage_factor * self.operational_factor


@dataclass(frozen=True)
class InletCellMapping:
    inlet_id: str
    cell_id: str

    def __post_init__(self):
        if not self.inlet_id:
            raise ValueError("inlet_id cannot be empty")
        if not self.cell_id:
            raise ValueError("cell_id cannot be empty")


@dataclass(frozen=True)
class InletCaptureResult:
    timestamp_seconds: int
    inlet_id: str
    node_id: str
    available_surface_m3: float
    effective_capacity_m3_s: float
    capacity_volume_m3: float
    captured_volume_m3: float


@dataclass(frozen=True)
class CouplingStepResult:
    timestamp_seconds: int
    total_runoff_input_m3: float
    total_drainage_capture_m3: float
    surface_storage_m3_by_cell: Dict[str, float]
    drainage_inflow_m3_by_node: Dict[str, float]
    drainage_storage_m3_by_node: Dict[str, float]
    drainage_outlet_volume_m3: float
    drainage_surcharge_m3_by_node: Dict[str, float]
    pending_surcharge_m3_by_cell: Dict[str, float]
    surface_boundary_outflow_m3: float
    total_surface_storage_m3: float
    total_drainage_storage_m3: float
    mass_balance_error_m3: float
    inlet_results: Tuple[InletCaptureResult, ...]


def calculate_capture_volume(
    available_surface_m3: float,
    capacity_m3_s: float,
    dt_seconds: float,
) -> float:
    if available_surface_m3 < -EPSILON_M3:
        raise ValueError("available_surface_m3 cannot be negative")
    if capacity_m3_s < 0:
        raise ValueError("capacity_m3_s cannot be negative")
    if dt_seconds <= 0:
        raise ValueError("dt_seconds must be > 0")

    available = max(available_surface_m3, 0.0)
    capacity_volume = capacity_m3_s * dt_seconds
    return min(available, capacity_volume)


def allocate_inlet_capacity(
    available_by_cell: Mapping[str, float],
    capacity_m3_s: float,
    dt_seconds: float,
) -> Dict[str, float]:
    if capacity_m3_s < 0:
        raise ValueError("capacity_m3_s must be >= 0")
    if dt_seconds <= 0:
        raise ValueError("dt_seconds must be > 0")

    total_available = sum(max(v, 0.0) for v in available_by_cell.values())
    if total_available <= EPSILON_M3:
        return {cell_id: 0.0 for cell_id in available_by_cell}

    capacity_volume = capacity_m3_s * dt_seconds
    total_capture = min(total_available, capacity_volume)

    return {
        cell_id: (total_capture * max(available, 0.0) / total_available)
        for cell_id, available in available_by_cell.items()
    }


def allocate_cell_capture(
    available_m3: float,
    inlet_capacities_m3_s: Mapping[str, float],
    dt_seconds: float,
) -> Dict[str, float]:
    if available_m3 < -EPSILON_M3:
        raise ValueError("available_m3 cannot be negative")
    if dt_seconds <= 0:
        raise ValueError("dt_seconds must be > 0")

    available = max(available_m3, 0.0)
    total_capacity = sum(max(c, 0.0) for c in inlet_capacities_m3_s.values())

    if total_capacity <= EPSILON_M3:
        return {inlet_id: 0.0 for inlet_id in inlet_capacities_m3_s}

    total_capture = min(available, total_capacity * dt_seconds)

    return {
        inlet_id: (total_capture * capacity / total_capacity)
        for inlet_id, capacity in inlet_capacities_m3_s.items()
    }


class SurfaceDrainageCouplingEngine:
    def __init__(
        self,
        surface_engine: SurfaceStorageEngine,
        drainage_network: StatefulDrainageNetwork,
        inlets: Sequence[DrainageInlet],
        mappings: Sequence[InletCellMapping],
        dt_seconds: float = 60.0,
        surcharge_cell_by_node: Optional[Mapping[str, str]] = None,
    ):
        if dt_seconds <= 0:
            raise ValueError("dt_seconds must be > 0")

        self.surface_engine = surface_engine
        self.drainage_network = drainage_network
        self.dt_seconds = float(dt_seconds)

        # Validate matching timesteps
        if float(surface_engine.dt_seconds) != self.dt_seconds:
            raise ValueError(
                f"Coupling timestep ({self.dt_seconds}s) and surface timestep ({surface_engine.dt_seconds}s) must match."
            )
        if float(drainage_network.dt_seconds) != self.dt_seconds:
            raise ValueError(
                f"Coupling timestep ({self.dt_seconds}s) and drainage timestep ({drainage_network.dt_seconds}s) must match."
            )

        # Validate unique inlet IDs
        inlet_ids = [x.inlet_id for x in inlets]
        if len(inlet_ids) != len(set(inlet_ids)):
            raise ValueError("Duplicate inlet_id found in inlets list.")

        inlet_by_id = {x.inlet_id: x for x in inlets}
        known_inlets = set(inlet_ids)
        known_cells = set(surface_engine.cell_ids)
        known_nodes = set(drainage_network.node_ids)

        for inlet in inlets:
            if inlet.node_id not in known_nodes:
                raise ValueError(f"Unknown drainage node '{inlet.node_id}' referenced by inlet '{inlet.inlet_id}'.")

        for mapping in mappings:
            if mapping.inlet_id not in known_inlets:
                raise ValueError(f"Unknown inlet '{mapping.inlet_id}' in mapping.")
            if mapping.cell_id not in known_cells:
                raise ValueError(f"Unknown surface cell '{mapping.cell_id}' in mapping.")

        self.inlets = tuple(inlets)
        self.mappings = tuple(mappings)
        self.inlet_by_id = inlet_by_id

        # Construct lookup maps
        self.inlets_by_cell: Dict[str, List[DrainageInlet]] = {}
        self.cells_by_inlet: Dict[str, List[str]] = {}

        for mapping in mappings:
            inlet_obj = inlet_by_id[mapping.inlet_id]
            self.inlets_by_cell.setdefault(mapping.cell_id, []).append(inlet_obj)
            self.cells_by_inlet.setdefault(mapping.inlet_id, []).append(mapping.cell_id)

        # Surcharge node -> surface cell mapping
        self.surcharge_cell_by_node: Dict[str, str] = {}
        if surcharge_cell_by_node:
            for nid, cid in surcharge_cell_by_node.items():
                if nid not in known_nodes:
                    raise ValueError(f"Unknown drainage node '{nid}' in surcharge mapping.")
                if cid not in known_cells:
                    raise ValueError(f"Unknown surface cell '{cid}' in surcharge mapping.")
                self.surcharge_cell_by_node[nid] = cid
        else:
            # Default: map node to cell associated with inlet on that node
            for inlet in inlets:
                cells = self.cells_by_inlet.get(inlet.inlet_id, [])
                if cells:
                    self.surcharge_cell_by_node[inlet.node_id] = cells[0]

        # Dynamic State: Pending surcharge delayed by 1 timestep
        self._pending_surcharge_m3_by_cell: Dict[str, float] = {
            cid: 0.0 for cid in self.surface_engine.cell_ids
        }
        self._cumulative_runoff_m3: float = 0.0
        self._cumulative_surface_boundary_m3: float = 0.0
        self._cumulative_drainage_outlet_m3: float = 0.0
        self._last_timestamp_seconds: Optional[int] = None
        self.history: List[CouplingStepResult] = []

    def reset(self) -> None:
        """Resets all surface, drainage, and coupling pending state."""
        self._pending_surcharge_m3_by_cell = {
            cid: 0.0 for cid in self.surface_engine.cell_ids
        }
        self._cumulative_runoff_m3 = 0.0
        self._cumulative_surface_boundary_m3 = 0.0
        self._cumulative_drainage_outlet_m3 = 0.0
        self._last_timestamp_seconds = None
        self.history.clear()
        self.surface_engine.reset()
        self.drainage_network.reset()

    def validate_timestamp(self, timestamp_seconds: int) -> None:
        if not isinstance(timestamp_seconds, (int, float)) or math.isnan(timestamp_seconds) or math.isinf(timestamp_seconds):
            raise ValueError(f"Invalid timestamp: {timestamp_seconds}")
        t = int(timestamp_seconds)

        if self._last_timestamp_seconds is not None:
            if t <= self._last_timestamp_seconds:
                raise ValueError(
                    f"Timestamp ({t}s) must be strictly greater than previous ({self._last_timestamp_seconds}s)."
                )
            actual_dt = t - self._last_timestamp_seconds
            if actual_dt != int(self.dt_seconds):
                raise ValueError(
                    f"Timestep spacing ({actual_dt}s) does not match expected ({int(self.dt_seconds)}s)."
                )

    def step(
        self,
        timestamp_seconds: int,
        runoff_volume_m3_by_cell: Mapping[str, float],
    ) -> CouplingStepResult:
        """
        Executes one coupled surface-drainage simulation timestep:
        1. Combines surface storage + direct runoff + previous delayed surcharge = available surface water
        2. Resolves inlet captures deterministically
        3. Routes remaining surface water across D8 terrain network (Layer 5)
        4. Transmits captured water into subsurface pipes, updating storage, discharge, and surcharge (Layer 6)
        5. Queues drainage surcharge as pending surface water for timestep t+1
        6. Verifies system-wide mass conservation
        """
        self.validate_timestamp(timestamp_seconds)
        t = int(timestamp_seconds)

        # 1. Validate runoff inputs
        expected_cells = set(self.surface_engine.cell_ids)
        provided_cells = set(runoff_volume_m3_by_cell.keys())
        if expected_cells != provided_cells:
            missing = expected_cells - provided_cells
            extra = provided_cells - expected_cells
            raise ValueError(f"Runoff input cell mismatch. Missing: {len(missing)}, Extra: {len(extra)}")

        for cid, vol in runoff_volume_m3_by_cell.items():
            if not isinstance(vol, (int, float)) or vol < 0.0 or math.isnan(vol) or math.isinf(vol):
                raise ValueError(f"Invalid runoff volume for cell {cid}: {vol}")

        # 2. Build available surface water per cell
        available_surface_m3: Dict[str, float] = {}
        for cid in self.surface_engine.cell_ids:
            s_current = self.surface_engine.storage(cid)
            r_val = float(runoff_volume_m3_by_cell[cid])
            surch_pend = self._pending_surcharge_m3_by_cell[cid]
            available_surface_m3[cid] = s_current + r_val + surch_pend

        # 3. Resolve Inlet Captures
        inlet_results_list: List[InletCaptureResult] = []
        capture_by_cell: Dict[str, float] = {cid: 0.0 for cid in self.surface_engine.cell_ids}
        drainage_inflow_by_node: Dict[str, float] = {nid: 0.0 for nid in self.drainage_network.node_ids}

        # Handle each cell's inlets
        for cid in self.surface_engine.cell_ids:
            cell_inlets = self.inlets_by_cell.get(cid, [])
            avail_cell = available_surface_m3[cid]

            if not cell_inlets or avail_cell <= EPSILON_M3:
                continue

            if len(cell_inlets) == 1:
                inlet = cell_inlets[0]
                cap_m3 = calculate_capture_volume(
                    available_surface_m3=avail_cell,
                    capacity_m3_s=inlet.effective_capacity_m3_s,
                    dt_seconds=self.dt_seconds,
                )
                capture_by_cell[cid] += cap_m3
                drainage_inflow_by_node[inlet.node_id] += cap_m3

                inlet_results_list.append(
                    InletCaptureResult(
                        timestamp_seconds=t,
                        inlet_id=inlet.inlet_id,
                        node_id=inlet.node_id,
                        available_surface_m3=avail_cell,
                        effective_capacity_m3_s=inlet.effective_capacity_m3_s,
                        capacity_volume_m3=inlet.effective_capacity_m3_s * self.dt_seconds,
                        captured_volume_m3=cap_m3,
                    )
                )
            else:
                # Multiple inlets on this cell -> allocate proportionally by inlet capacity
                cap_map = {inlet.inlet_id: inlet.effective_capacity_m3_s for inlet in cell_inlets}
                alloc_map = allocate_cell_capture(
                    available_m3=avail_cell,
                    inlet_capacities_m3_s=cap_map,
                    dt_seconds=self.dt_seconds,
                )
                for inlet in cell_inlets:
                    cap_m3 = alloc_map[inlet.inlet_id]
                    capture_by_cell[cid] += cap_m3
                    drainage_inflow_by_node[inlet.node_id] += cap_m3

                    inlet_results_list.append(
                        InletCaptureResult(
                            timestamp_seconds=t,
                            inlet_id=inlet.inlet_id,
                            node_id=inlet.node_id,
                            available_surface_m3=avail_cell,
                            effective_capacity_m3_s=inlet.effective_capacity_m3_s,
                            capacity_volume_m3=inlet.effective_capacity_m3_s * self.dt_seconds,
                            captured_volume_m3=cap_m3,
                        )
                    )

        # 4. Calculate Remaining Surface Water
        remaining_surface_m3: Dict[str, float] = {}
        for cid in self.surface_engine.cell_ids:
            rem = available_surface_m3[cid] - capture_by_cell[cid]
            remaining_surface_m3[cid] = max(0.0, rem)

        # 5. Route Remaining Surface Water via Layer 5 D8 Engine
        next_surface_storage, surface_boundary_outflow, _ = self.surface_engine.route_available_water(
            available_surface_m3_by_cell=remaining_surface_m3,
            dt_seconds=self.dt_seconds,
        )

        # 6. Advance Layer 6 Subsurface Drainage Network
        drainage_result: DrainageStepResult = self.drainage_network.step(
            timestamp_seconds=t,
            inflow_volume_m3_by_node=drainage_inflow_by_node,
            dt_seconds=int(self.dt_seconds),
        )

        # 7. Map Surcharge to Delayed Next-Timestep Surface Storage
        next_pending_surcharge: Dict[str, float] = {cid: 0.0 for cid in self.surface_engine.cell_ids}
        for nid, surch_vol in drainage_result.surcharge_volume_m3_by_node.items():
            if surch_vol > EPSILON_M3:
                target_cell = self.surcharge_cell_by_node.get(nid)
                if target_cell is not None:
                    next_pending_surcharge[target_cell] += surch_vol

        # Surcharge becomes pending for timestep t + 1 (NO instantaneous loop)
        self._pending_surcharge_m3_by_cell = next_pending_surcharge

        # 8. Cumulative System-Wide Mass Conservation Accounting
        step_runoff_total = sum(runoff_volume_m3_by_cell.values())
        step_capture_total = sum(capture_by_cell.values())
        total_surface_storage = sum(next_surface_storage.values())
        total_drainage_storage = sum(drainage_result.node_storage_m3_by_node.values())
        total_pending_surcharge = sum(self._pending_surcharge_m3_by_cell.values())

        self._cumulative_runoff_m3 += step_runoff_total
        self._cumulative_surface_boundary_m3 += surface_boundary_outflow
        self._cumulative_drainage_outlet_m3 += drainage_result.outlet_volume_m3
        self._last_timestamp_seconds = t

        # Global Invariant: Cumulative Runoff == Surface Storage + Drainage Storage + Pending Surcharge + Boundary Outflow + Outlet Outflow
        mass_balance_error = (
            self._cumulative_runoff_m3
            - total_surface_storage
            - total_drainage_storage
            - total_pending_surcharge
            - self._cumulative_surface_boundary_m3
            - self._cumulative_drainage_outlet_m3
        )

        step_res = CouplingStepResult(
            timestamp_seconds=t,
            total_runoff_input_m3=step_runoff_total,
            total_drainage_capture_m3=step_capture_total,
            surface_storage_m3_by_cell=next_surface_storage,
            drainage_inflow_m3_by_node=drainage_inflow_by_node,
            drainage_storage_m3_by_node=drainage_result.node_storage_m3_by_node,
            drainage_outlet_volume_m3=drainage_result.outlet_volume_m3,
            drainage_surcharge_m3_by_node=drainage_result.surcharge_volume_m3_by_node,
            pending_surcharge_m3_by_cell=dict(self._pending_surcharge_m3_by_cell),
            surface_boundary_outflow_m3=surface_boundary_outflow,
            total_surface_storage_m3=total_surface_storage,
            total_drainage_storage_m3=total_drainage_storage,
            mass_balance_error_m3=mass_balance_error,
            inlet_results=tuple(inlet_results_list),
        )
        self.history.append(step_res)
        return step_res

    def mass_balance(self) -> Dict[str, Any]:
        """Returns cumulative coupled system mass balance audit."""
        total_surface_storage = sum(self.surface_engine.storage_m3.values())
        total_drainage_storage = sum(self.drainage_network.node_storage_m3.values())
        total_pending_surcharge = sum(self._pending_surcharge_m3_by_cell.values())

        error_m3 = (
            self._cumulative_runoff_m3
            - total_surface_storage
            - total_drainage_storage
            - total_pending_surcharge
            - self._cumulative_surface_boundary_m3
            - self._cumulative_drainage_outlet_m3
        )

        return {
            "cumulative_runoff_m3": round(self._cumulative_runoff_m3, 6),
            "current_surface_storage_m3": round(total_surface_storage, 6),
            "current_drainage_storage_m3": round(total_drainage_storage, 6),
            "pending_surcharge_m3": round(total_pending_surcharge, 6),
            "cumulative_surface_boundary_m3": round(self._cumulative_surface_boundary_m3, 6),
            "cumulative_drainage_outlet_m3": round(self._cumulative_drainage_outlet_m3, 6),
            "mass_balance_error_m3": round(error_m3, 8),
            "is_conserved": abs(error_m3) <= 1e-5,
        }
