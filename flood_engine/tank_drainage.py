"""
Virtual Tank Underground Drainage Network Simulation Engine:
Represents the subsurface drainage network as a system of connected storage tanks.
Each node models:
- Maximum storage capacity (liters)
- Current water volume (liters)
- Water inflow (L/s)
- Water outflow (L/s)
- Percentage filled (%)
- Drainage capacity (L/s) with degradation factor
- Surcharge / overflow returned back to connected surface grid cells
- Stage conversion and comparison with live ultrasonic sensor telemetry
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TankThresholds:
    """Configurable thresholds for drainage node status classification."""
    watch_percent: float = 60.0
    near_capacity_percent: float = 80.0
    surcharging_percent: float = 100.0


@dataclass
class DrainageTankNode:
    """
    Virtual Tank abstraction for a single underground drainage node.
    Governing continuity equation:
        current_storage(t+1) = max(0, current_storage(t) + inflow - outflow)
    If current_storage > capacity:
        stored = capacity
        overflow = current_storage - capacity
    """
    node_id: str
    latitude: float
    longitude: float
    connected_cell_id: str
    capacity_liters: float
    base_capacity_lps: float = 30.0  # Base drainage discharge capacity (L/s)
    current_storage_liters: float = 0.0
    drainage_degradation_factor: float = 1.0  # 1.0 = 100%, 0.5 = 50%, 0.3 = 30%
    downstream_node_id: str | None = None
    node_depth_cm: float = 150.0  # Physical manhole / tank depth for sensor stage mapping
    head_dependent_outflow: bool = False  # Hydraulic orifice discharge: Q proportional to fill ratio
    thresholds: TankThresholds = field(default_factory=TankThresholds)

    # Step telemetry metrics
    inflow_lps: float = 0.0
    outflow_lps: float = 0.0
    overflow_lps: float = 0.0
    overflow_liters: float = 0.0
    fill_percentage: float = 0.0
    status: str = "NORMAL"

    def __post_init__(self):
        if self.capacity_liters <= 0:
            raise ValueError(f"capacity_liters must be > 0, got {self.capacity_liters}")
        if self.base_capacity_lps < 0:
            raise ValueError(f"base_capacity_lps must be >= 0, got {self.base_capacity_lps}")
        self.update_status()

    @property
    def effective_capacity_lps(self) -> float:
        """Effective drainage outflow capacity after degradation factor."""
        factor = max(0.0, min(1.0, float(self.drainage_degradation_factor)))
        return self.base_capacity_lps * factor

    def set_degradation_factor(self, factor: float) -> None:
        """Sets the drainage degradation factor (0.0 to 1.0)."""
        self.drainage_degradation_factor = max(0.0, min(1.0, float(factor)))

    def update_status(self) -> None:
        """Updates fill percentage and operational status based on configured thresholds."""
        self.fill_percentage = round((self.current_storage_liters / self.capacity_liters) * 100.0, 2)
        if self.overflow_liters > 0.0 or self.fill_percentage >= self.thresholds.surcharging_percent:
            self.status = "SURCHARGING"
        elif self.fill_percentage >= self.thresholds.near_capacity_percent:
            self.status = "NEAR_CAPACITY"
        elif self.fill_percentage >= self.thresholds.watch_percent:
            self.status = "WATCH"
        else:
            self.status = "NORMAL"

    def step(self, dt_seconds: float, external_inflow_liters: float = 0.0) -> tuple[float, float]:
        """
        Executes one timestep of the virtual tank:
        1. Ingests external surface inflow.
        2. Calculates maximum permissible outflow based on effective drainage capacity.
        3. Computes water balance, new storage, and surcharge overflow.
        Returns:
            (outflow_liters_transmitted, overflow_liters_to_surface)
        """
        dt = float(dt_seconds)
        if dt <= 0:
            raise ValueError(f"dt_seconds must be > 0, got {dt}")

        ext_inflow = max(0.0, float(external_inflow_liters))
        self.inflow_lps = round(ext_inflow / dt, 2)

        # Available water before discharge
        water_available = self.current_storage_liters + ext_inflow

        # Outflow capacity over dt (with optional orifice discharge retention)
        if self.head_dependent_outflow and water_available > 0:
            fill_ratio = min(1.0, max(0.05, water_available / self.capacity_liters))
            discharge_rate = self.effective_capacity_lps * math.sqrt(fill_ratio)
            max_possible_outflow = discharge_rate * dt
        else:
            max_possible_outflow = self.effective_capacity_lps * dt

        actual_outflow = min(water_available, max_possible_outflow)
        self.outflow_lps = round(actual_outflow / dt, 2)

        # Tentative storage
        tentative_storage = water_available - actual_outflow


        # Capacity limitation and overflow calculation
        if tentative_storage > self.capacity_liters:
            self.current_storage_liters = self.capacity_liters
            self.overflow_liters = tentative_storage - self.capacity_liters
        else:
            self.current_storage_liters = max(0.0, tentative_storage)
            self.overflow_liters = 0.0

        self.overflow_lps = round(self.overflow_liters / dt, 2)
        self.update_status()

        return actual_outflow, self.overflow_liters

    @property
    def simulated_water_level_cm(self) -> float:
        """Converts storage volume to simulated water depth inside tank (cm)."""
        ratio = min(1.0, max(0.0, self.current_storage_liters / self.capacity_liters))
        return round(ratio * self.node_depth_cm, 1)

    def to_dict(self) -> dict[str, Any]:
        """Serializes tank state for REST API and dashboard visualization."""
        return {
            "node_id": self.node_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "connected_cell_id": self.connected_cell_id,
            "capacity_liters": round(self.capacity_liters, 1),
            "current_storage_liters": round(self.current_storage_liters, 1),
            "base_capacity_lps": round(self.base_capacity_lps, 1),
            "effective_capacity_lps": round(self.effective_capacity_lps, 1),
            "drainage_degradation_factor": round(self.drainage_degradation_factor, 2),
            "downstream_node_id": self.downstream_node_id,
            "inflow_lps": self.inflow_lps,
            "outflow_lps": self.outflow_lps,
            "overflow_lps": self.overflow_lps,
            "overflow_liters": round(self.overflow_liters, 1),
            "fill_percentage": self.fill_percentage,
            "status": self.status,
            "simulated_water_level_cm": self.simulated_water_level_cm,
        }


class VirtualTankDrainageNetwork:
    """
    Connected underground drainage network modeled as directed virtual tanks.
    Topology:
        Surface Cell -> D01 (Inlet) -> D02 -> D03 -> D04 -> D05 -> Outlet
    Supports:
    - Bidirectional surface runoff capture and surcharge ejection
    - Degradation factor simulation
    - Exact continuous mass balance invariant
    - Ultrasonic telemetry comparison
    """

    def __init__(self, nodes: list[DrainageTankNode] | None = None):
        self.nodes: dict[str, DrainageTankNode] = {}
        self.node_order: list[str] = []

        # Mass balance accounting (in Liters)
        self.cumulative_surface_inflow_liters: float = 0.0
        self.cumulative_outfall_discharge_liters: float = 0.0
        self.cumulative_surface_surcharge_liters: float = 0.0

        if nodes:
            for n in nodes:
                self.add_node(n)
        else:
            self._build_default_network()

    def _build_default_network(self) -> None:
        """Constructs the canonical 5-node urban drainage network aligned with Chennai catchment."""
        default_nodes = [
            DrainageTankNode(
                node_id="D01",
                latitude=13.0867,
                longitude=80.2747,
                connected_cell_id="C022",
                capacity_liters=1000.0,
                base_capacity_lps=25.0,
                downstream_node_id="D02",
                node_depth_cm=120.0,
            ),
            DrainageTankNode(
                node_id="D02",
                latitude=13.0847,
                longitude=80.2737,
                connected_cell_id="C045",
                capacity_liters=1500.0,
                base_capacity_lps=30.0,
                downstream_node_id="D03",
                node_depth_cm=140.0,
            ),
            DrainageTankNode(
                node_id="D03",
                latitude=13.0887,
                longitude=80.2777,
                connected_cell_id="C058",  # East Underpass depression hotspot
                capacity_liters=2000.0,
                base_capacity_lps=30.0,
                downstream_node_id="D04",
                node_depth_cm=160.0,
            ),
            DrainageTankNode(
                node_id="D04",
                latitude=13.0887,
                longitude=80.2757,
                connected_cell_id="C065",
                capacity_liters=2500.0,
                base_capacity_lps=45.0,
                downstream_node_id="D05",
                node_depth_cm=180.0,
            ),
            DrainageTankNode(
                node_id="D05",
                latitude=13.0917,
                longitude=80.2797,
                connected_cell_id="C089",  # Outlet to canal
                capacity_liters=3000.0,
                base_capacity_lps=60.0,
                downstream_node_id=None,    # Outfall node
                node_depth_cm=200.0,
            ),
        ]
        for n in default_nodes:
            self.add_node(n)

    def add_node(self, node: DrainageTankNode) -> None:
        self.nodes[node.node_id] = node
        if node.node_id not in self.node_order:
            self.node_order.append(node.node_id)

    def reset(self) -> None:
        """Resets all node storages and cumulative flow counters."""
        for n in self.nodes.values():
            n.current_storage_liters = 0.0
            n.inflow_lps = 0.0
            n.outflow_lps = 0.0
            n.overflow_lps = 0.0
            n.overflow_liters = 0.0
            n.drainage_degradation_factor = 1.0
            n.update_status()
        self.cumulative_surface_inflow_liters = 0.0
        self.cumulative_outfall_discharge_liters = 0.0
        self.cumulative_surface_surcharge_liters = 0.0

    def step(
        self,
        dt_seconds: float,
        surface_inflows_liters_by_cell: dict[str, float] | None = None,
        degradation_factors: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Executes one timestep across the connected drainage network.
        Water flows:
            Surface Cell Runoff -> Tank Node -> Downstream Tank Node -> Outlet
        If any tank surcharges, overflow returns to connected surface cell.
        """
        dt = float(dt_seconds)
        if dt <= 0:
            raise ValueError(f"dt_seconds must be > 0, got {dt}")

        # 1. Apply degradation factors
        if degradation_factors:
            for nid, factor in degradation_factors.items():
                if nid in self.nodes:
                    self.nodes[nid].set_degradation_factor(factor)

        # 2. Map surface inflows to inlet tank nodes
        cell_to_inflow = surface_inflows_liters_by_cell or {}
        inflow_to_node: dict[str, float] = {nid: 0.0 for nid in self.nodes}
        for n in self.nodes.values():
            if n.connected_cell_id in cell_to_inflow:
                inflow_to_node[n.node_id] += max(0.0, float(cell_to_inflow[n.connected_cell_id]))

        # Track total surface water ingested into drainage
        step_surface_input = sum(inflow_to_node.values())
        self.cumulative_surface_inflow_liters += step_surface_input

        # 3. Route water through connected tanks from upstream to downstream
        step_transmitted: dict[str, float] = {nid: 0.0 for nid in self.nodes}
        step_surcharges_by_cell: dict[str, float] = {}
        step_outfall_discharge = 0.0

        for nid in self.node_order:
            node = self.nodes[nid]
            total_inflow_to_tank = inflow_to_node[nid]

            # Execute tank step
            outflow_liters, overflow_liters = node.step(dt_seconds=dt, external_inflow_liters=total_inflow_to_tank)

            # Route outflow downstream or discharge at outfall
            if node.downstream_node_id and node.downstream_node_id in self.nodes:
                inflow_to_node[node.downstream_node_id] += outflow_liters
                step_transmitted[nid] = outflow_liters
            else:
                # Outfall terminal discharge
                step_outfall_discharge += outflow_liters

            # If tank surcharged, return overflow to connected surface cell
            if overflow_liters > 0.0:
                step_surcharges_by_cell[node.connected_cell_id] = (
                    step_surcharges_by_cell.get(node.connected_cell_id, 0.0) + overflow_liters
                )

        # Update cumulative totals
        self.cumulative_outfall_discharge_liters += step_outfall_discharge
        step_surcharge_total = sum(step_surcharges_by_cell.values())
        self.cumulative_surface_surcharge_liters += step_surcharge_total

        # 4. Strict Mass Balance Verification
        total_current_storage = sum(n.current_storage_liters for n in self.nodes.values())
        mass_balance_error_liters = (
            self.cumulative_surface_inflow_liters
            - total_current_storage
            - self.cumulative_outfall_discharge_liters
            - self.cumulative_surface_surcharge_liters
        )

        return {
            "dt_seconds": dt,
            "total_surface_inflow_liters": step_surface_input,
            "total_current_storage_liters": total_current_storage,
            "step_outfall_discharge_liters": step_outfall_discharge,
            "step_surcharges_by_cell_liters": step_surcharges_by_cell,
            "step_surcharges_by_cell_m3": {cid: round(vol / 1000.0, 6) for cid, vol in step_surcharges_by_cell.items()},
            "cumulative_surface_inflow_liters": self.cumulative_surface_inflow_liters,
            "cumulative_outfall_discharge_liters": self.cumulative_outfall_discharge_liters,
            "cumulative_surface_surcharge_liters": self.cumulative_surface_surcharge_liters,
            "mass_balance_error_liters": round(mass_balance_error_liters, 6),
            "mass_balance_error_m3": round(mass_balance_error_liters / 1000.0, 8),
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
        }

    def compare_with_sensor(
        self,
        node_id: str,
        live_sensor_depth_cm: float | None,
        sensor_status: str = "ONLINE",
    ) -> dict[str, Any]:
        """
        Compares simulated tank water level against physical ultrasonic sensor readings.
        Filters out invalid or disconnected sensors to prevent corruption.
        """
        node = self.nodes.get(node_id)
        if not node:
            return {"status": "ERROR", "message": f"Node {node_id} not found"}

        sim_level = node.simulated_water_level_cm

        if live_sensor_depth_cm is None or sensor_status != "ONLINE":
            return {
                "node_id": node_id,
                "simulated_level_cm": sim_level,
                "sensor_reading_cm": None,
                "sensor_status": sensor_status,
                "residual_cm": None,
                "agreement": "UNAVAILABLE",
            }

        residual = round(float(live_sensor_depth_cm) - sim_level, 2)
        agreement = "EXCELLENT" if abs(residual) <= 5.0 else ("MODERATE" if abs(residual) <= 15.0 else "POOR")

        return {
            "node_id": node_id,
            "simulated_level_cm": sim_level,
            "sensor_reading_cm": round(float(live_sensor_depth_cm), 1),
            "sensor_status": sensor_status,
            "residual_cm": residual,
            "agreement": agreement,
        }

    def get_network_summary(self) -> dict[str, Any]:
        """Returns executive summary of the entire virtual tank drainage network."""
        total_cap = sum(n.capacity_liters for n in self.nodes.values())
        total_stored = sum(n.current_storage_liters for n in self.nodes.values())
        net_fill = round((total_stored / total_cap) * 100.0, 2) if total_cap > 0 else 0.0

        active_surcharging = [nid for nid, n in self.nodes.items() if n.status == "SURCHARGING"]
        near_capacity = [nid for nid, n in self.nodes.items() if n.status == "NEAR_CAPACITY"]

        overall_status = "NORMAL"
        if active_surcharging:
            overall_status = "SURCHARGING"
        elif near_capacity:
            overall_status = "NEAR_CAPACITY"
        elif net_fill >= 60.0:
            overall_status = "WATCH"

        return {
            "network_status": overall_status,
            "total_nodes": len(self.nodes),
            "total_capacity_liters": round(total_cap, 1),
            "total_storage_liters": round(total_stored, 1),
            "network_fill_percentage": net_fill,
            "active_surcharging_nodes": active_surcharging,
            "near_capacity_nodes": near_capacity,
            "cumulative_outfall_discharge_liters": round(self.cumulative_outfall_discharge_liters, 1),
            "cumulative_surcharge_liters": round(self.cumulative_surface_surcharge_liters, 1),
        }
