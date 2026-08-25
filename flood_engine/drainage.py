"""
Layer 6 (Hardened & Stateful) — Subsurface Drainage Network Engine:
Simulates stateful node storage, capacity-constrained pipe transport, proportional branching,
explicit surcharge generation, outlet discharge, and strict mass conservation.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path
import math
import networkx as nx
import numpy as np

from flood_engine.config import load_config


class DrainageNode:
    def __init__(
        self,
        node_id: Any,
        latitude: float = 0.0,
        longitude: float = 0.0,
        node_type: str = "manhole",
        base_capacity_m3_s: float = 0.05,
        storage_capacity_m3: float = 10.0,
        invert_elevation_m: float = 0.0,
        ground_elevation_m: float = 1.0,
        associated_cell_id: Optional[Any] = None,
        cell_id: Optional[Any] = None,
        capacity_factor: float = 1.0,
        name: str = "",
        **kwargs,
    ):
        self.node_id = str(node_id)
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.node_type = str(node_type)
        self.base_capacity_m3_s = float(base_capacity_m3_s)
        self.storage_capacity_m3 = float(storage_capacity_m3)
        self.invert_elevation_m = float(invert_elevation_m)
        self.ground_elevation_m = float(ground_elevation_m)
        self.cell_id = cell_id if cell_id is not None else associated_cell_id
        self.associated_cell_id = str(self.cell_id) if self.cell_id is not None else None
        self.capacity_factor = float(capacity_factor)
        self.name = name or f"Node-{self.node_id}"

    def set_capacity_factor(self, factor: float) -> None:
        """Sets the capacity degradation factor (0 <= factor <= 1)."""
        self.capacity_factor = float(factor)


class DrainageEdge:
    def __init__(
        self,
        edge_id: Any,
        from_node: Any,
        to_node: Any,
        length_m: float = 50.0,
        capacity_m3_s: Optional[float] = None,
        base_capacity_m3_s: Optional[float] = None,
        diameter_m: float = 0.8,
        slope: float = 0.01,
        upstream_invert_elevation_m: float = 0.0,
        downstream_invert_elevation_m: float = -0.2,
        travel_time_seconds: float = 0.0,
        **kwargs,
    ):
        self.edge_id = str(edge_id)
        self.from_node = str(from_node)
        self.to_node = str(to_node)
        self.length_m = float(length_m)
        cap = capacity_m3_s if capacity_m3_s is not None else (base_capacity_m3_s if base_capacity_m3_s is not None else 0.05)
        self.capacity_m3_s = float(cap)
        self.base_capacity_m3_s = float(cap)
        self.diameter_m = float(diameter_m)
        self.slope = float(slope)
        self.upstream_invert_elevation_m = float(upstream_invert_elevation_m)
        self.downstream_invert_elevation_m = float(downstream_invert_elevation_m)
        self.travel_time_seconds = float(travel_time_seconds)


@dataclass
class EdgeFlowResult:
    edge_id: str
    from_node: str
    to_node: str
    requested_volume_m3: float
    capacity_volume_m3: float
    transmitted_volume_m3: float
    excess_volume_m3: float
    capacity_factor: float


@dataclass
class DrainageStepResult:
    timestamp_seconds: int
    timestep_seconds: int
    node_storage_m3_by_node: Dict[str, float]
    edge_flows: Dict[str, EdgeFlowResult]
    outlet_discharge_m3_by_node: Dict[str, float]
    surcharge_volume_m3_by_node: Dict[str, float]
    external_inflow_m3: float
    transmitted_volume_m3: float
    outlet_volume_m3: float
    stored_volume_m3: float
    surcharge_volume_m3: float
    mass_balance_error_m3: float


class StatefulDrainageNetwork:
    def __init__(
        self,
        nodes: Optional[List[DrainageNode]] = None,
        edges: Optional[List[DrainageEdge]] = None,
        expected_timestep_seconds: int = 60,
        config_path: Optional[Union[str, Path]] = "config.yaml",
    ):
        self.nodes: Dict[str, DrainageNode] = {}
        self.edges: Dict[str, DrainageEdge] = {}
        self.graph = nx.DiGraph()
        self.expected_timestep_seconds = int(expected_timestep_seconds)

        if config_path and Path(config_path).exists():
            cfg = load_config(Path(config_path))
            self.expected_timestep_seconds = int(cfg.get("simulation", {}).get("timestep_seconds", self.expected_timestep_seconds))

        # Dynamic State (m³)
        self.node_storage_m3: Dict[str, float] = {}
        self.cumulative_inflow_m3: float = 0.0
        self.cumulative_outlet_discharge_m3: float = 0.0
        self.cumulative_surcharge_m3: float = 0.0
        self.last_timestamp_seconds: Optional[int] = None
        self.history: List[DrainageStepResult] = []

        if nodes:
            for n in nodes:
                self.add_node(n)
        if edges:
            for e in edges:
                self.add_edge(e)

    @property
    def node_ids(self) -> List[str]:
        return [str(k) for k in self.nodes.keys() if isinstance(k, str)]

    @property
    def dt_seconds(self) -> float:
        return float(self.expected_timestep_seconds)

    def add_node(self, node: DrainageNode) -> None:
        self.nodes[str(node.node_id)] = node
        try:
            int_id = int(node.node_id)
            self.nodes[int_id] = node
        except (ValueError, TypeError):
            pass

        self.graph.add_node(str(node.node_id), data=node)
        if str(node.node_id) not in self.node_storage_m3:
            self.node_storage_m3[str(node.node_id)] = 0.0

    def add_edge(self, edge: DrainageEdge) -> None:
        from_str = str(edge.from_node)
        to_str = str(edge.to_node)
        if from_str not in self.nodes and edge.from_node not in self.nodes:
            raise ValueError(f"from_node '{edge.from_node}' not registered in drainage network.")
        if to_str not in self.nodes and edge.to_node not in self.nodes:
            raise ValueError(f"to_node '{edge.to_node}' not registered in drainage network.")
        if edge.capacity_m3_s < 0.0:
            raise ValueError(f"Edge capacity cannot be negative: {edge.capacity_m3_s}")

        self.edges[str(edge.edge_id)] = edge
        try:
            int_eid = int(edge.edge_id)
            self.edges[int_eid] = edge
        except (ValueError, TypeError):
            pass

        self.graph.add_edge(
            from_str,
            to_str,
            edge_id=str(edge.edge_id),
            capacity=edge.capacity_m3_s,
            data=edge,
        )

    def reset(self) -> None:
        """Resets all node storage levels, cumulative accounting, and timestamp history."""
        for nid in self.nodes.keys():
            self.node_storage_m3[str(nid)] = 0.0
        self.cumulative_inflow_m3 = 0.0
        self.cumulative_outlet_discharge_m3 = 0.0
        self.cumulative_surcharge_m3 = 0.0
        self.last_timestamp_seconds = None
        self.history.clear()

    def outgoing_edges(self, node_id: Any) -> List[DrainageEdge]:
        edges = []
        nid_str = str(node_id)
        if nid_str in self.graph:
            for _, to_node, data in self.graph.out_edges(nid_str, data=True):
                edges.append(data["data"])
        return edges

    def incoming_edges(self, node_id: Any) -> List[DrainageEdge]:
        edges = []
        nid_str = str(node_id)
        if nid_str in self.graph:
            for from_node, _, data in self.graph.in_edges(nid_str, data=True):
                edges.append(data["data"])
        return edges

    @property
    def cell_to_node(self) -> Dict[Any, Any]:
        """Mapping from computational cell_id to node_id."""
        mapping = {}
        for n in self.nodes.values():
            if n.cell_id is not None:
                mapping[n.cell_id] = n.node_id
                try:
                    mapping[int(n.cell_id)] = n.node_id
                except (ValueError, TypeError):
                    pass
            if n.associated_cell_id is not None:
                mapping[n.associated_cell_id] = n.node_id
        return mapping

    def get_inlet_for_cell(self, cell_id: Any) -> Optional[DrainageNode]:
        """Retrieves drainage node associated with a specific computational cell ID."""
        cid_str = str(cell_id)
        for n in self.nodes.values():
            if str(n.cell_id) == cid_str or str(n.associated_cell_id) == cid_str:
                return n
        return None

    def set_capacity_factor(self, target_id: Any, factor: float) -> None:
        """Sets capacity factor for a node or edge."""
        tid_str = str(target_id)
        f_val = float(factor)
        if tid_str in self.nodes:
            self.nodes[tid_str].capacity_factor = f_val
        if target_id in self.nodes:
            self.nodes[target_id].capacity_factor = f_val
        for n in self.nodes.values():
            if str(n.cell_id) == tid_str or str(n.associated_cell_id) == tid_str or n.cell_id == target_id:
                n.capacity_factor = f_val

    def compute_capture(self, cell_or_node_id: Any, available_m3: float, dt_seconds: float = 60.0) -> float:
        """Helper for surface coupling capture computation."""
        cid_str = str(cell_or_node_id)
        target_node = self.nodes.get(cid_str)
        if target_node is None:
            for n in self.nodes.values():
                if str(n.cell_id) == cid_str or str(n.associated_cell_id) == cid_str:
                    target_node = n
                    break
        if target_node is None:
            return 0.0
        cap_vol = target_node.base_capacity_m3_s * getattr(target_node, "capacity_factor", 1.0) * float(dt_seconds)
        return min(max(0.0, float(available_m3)), cap_vol)

    def validate_timestamp(self, timestamp_seconds: int, dt_seconds: Optional[int] = None) -> None:
        """Enforces strictly advancing timestamps matching configured spacing."""
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
        inflow_volume_m3_by_node: Optional[Dict[str, float]] = None,
        capacity_factor_by_edge: Optional[Dict[str, float]] = None,
        dt_seconds: Optional[int] = None,
    ) -> DrainageStepResult:
        """
        Executes one stateful drainage network simulation timestep:
        1. Ingests external surface runoff/inlet capture inflows I_t
        2. Routes pipe flows based on capacity, degradation factors, and branching
        3. Delivers routed pipe volumes to downstream nodes (synchronous next-step storage)
        4. Handles boundary outlet discharge
        5. Computes persistent storage and surcharge Q_t when node capacity is exceeded
        6. Verifies mass conservation
        """
        dt = int(dt_seconds or self.expected_timestep_seconds)
        self.validate_timestamp(timestamp_seconds, dt_seconds=dt)
        t = int(timestamp_seconds)

        # 1. Parse inflows
        inflow_map: Dict[str, float] = {nid: 0.0 for nid in self.nodes.keys()}
        if inflow_volume_m3_by_node:
            for nid, val in inflow_volume_m3_by_node.items():
                nid_str = str(nid)
                if nid_str not in self.nodes:
                    raise ValueError(f"Unknown drainage node '{nid_str}' in inflow input.")
                if not isinstance(val, (int, float)) or val < 0.0 or math.isnan(val) or math.isinf(val):
                    raise ValueError(f"Invalid inflow volume for node {nid_str}: {val}")
                inflow_map[nid_str] = float(val)

        # 2. Parse capacity degradation factors (0 <= factor <= 1)
        cap_factors: Dict[str, float] = {eid: 1.0 for eid in self.edges.keys()}
        if capacity_factor_by_edge:
            for eid, f_val in capacity_factor_by_edge.items():
                eid_str = str(eid)
                if eid_str not in self.edges:
                    raise ValueError(f"Unknown edge '{eid_str}' in capacity factor input.")
                if not (0.0 <= f_val <= 1.0):
                    raise ValueError(f"Capacity factor for edge {eid_str} must be in [0, 1], got {f_val}")
                cap_factors[eid_str] = float(f_val)

        # 3. Synchronous Pipe Outflow Evaluation
        available_at_node: Dict[str, float] = {}
        for nid in self.nodes.keys():
            available_at_node[nid] = self.node_storage_m3[nid] + inflow_map[nid]

        edge_flow_results: Dict[str, EdgeFlowResult] = {}
        downstream_arrivals_m3: Dict[str, float] = {nid: 0.0 for nid in self.nodes.keys()}
        total_pipe_transmitted_m3 = 0.0

        for nid, node in self.nodes.items():
            avail = available_at_node[nid]
            out_edges = self.outgoing_edges(nid)

            if not out_edges or avail <= 0.0:
                continue

            eff_caps = [e.capacity_m3_s * cap_factors[e.edge_id] * dt for e in out_edges]
            sum_caps = sum(eff_caps)

            if sum_caps <= 0.0:
                for e in out_edges:
                    edge_flow_results[e.edge_id] = EdgeFlowResult(
                        edge_id=e.edge_id,
                        from_node=e.from_node,
                        to_node=e.to_node,
                        requested_volume_m3=0.0,
                        capacity_volume_m3=0.0,
                        transmitted_volume_m3=0.0,
                        excess_volume_m3=0.0,
                        capacity_factor=cap_factors[e.edge_id],
                    )
                continue

            transferred_from_node = 0.0
            if avail <= sum_caps:
                for e, c_vol in zip(out_edges, eff_caps):
                    frac = c_vol / sum_caps
                    flow_vol = avail * frac
                    edge_flow_results[e.edge_id] = EdgeFlowResult(
                        edge_id=e.edge_id,
                        from_node=e.from_node,
                        to_node=e.to_node,
                        requested_volume_m3=flow_vol,
                        capacity_volume_m3=c_vol,
                        transmitted_volume_m3=flow_vol,
                        excess_volume_m3=0.0,
                        capacity_factor=cap_factors[e.edge_id],
                    )
                    downstream_arrivals_m3[e.to_node] += flow_vol
                    transferred_from_node += flow_vol
                    total_pipe_transmitted_m3 += flow_vol
            else:
                for e, c_vol in zip(out_edges, eff_caps):
                    req_vol = avail * (c_vol / sum_caps)
                    flow_vol = c_vol
                    excess_vol = max(0.0, req_vol - flow_vol)
                    edge_flow_results[e.edge_id] = EdgeFlowResult(
                        edge_id=e.edge_id,
                        from_node=e.from_node,
                        to_node=e.to_node,
                        requested_volume_m3=req_vol,
                        capacity_volume_m3=c_vol,
                        transmitted_volume_m3=flow_vol,
                        excess_volume_m3=excess_vol,
                        capacity_factor=cap_factors[e.edge_id],
                    )
                    downstream_arrivals_m3[e.to_node] += flow_vol
                    transferred_from_node += flow_vol
                    total_pipe_transmitted_m3 += flow_vol

            available_at_node[nid] -= transferred_from_node

        # 4. Outlets, Node Storage Retention, and Surcharge
        outlet_discharge_m3: Dict[str, float] = {nid: 0.0 for nid in self.nodes.keys()}
        surcharge_m3: Dict[str, float] = {nid: 0.0 for nid in self.nodes.keys()}
        new_storage_m3: Dict[str, float] = {}

        step_outlet_total = 0.0
        step_surcharge_total = 0.0
        step_storage_total = 0.0

        for nid, node in self.nodes.items():
            rem_water = available_at_node[nid] + downstream_arrivals_m3[nid]

            if node.node_type in ("outlet", "outfall"):
                outlet_cap_vol = node.base_capacity_m3_s * dt
                discharge_vol = min(rem_water, outlet_cap_vol)
                outlet_discharge_m3[nid] = discharge_vol
                rem_water -= discharge_vol
                step_outlet_total += discharge_vol

            max_store = node.storage_capacity_m3
            if rem_water <= max_store:
                stored = rem_water
                surch = 0.0
            else:
                stored = max_store
                surch = rem_water - max_store

            new_storage_m3[nid] = stored
            surcharge_m3[nid] = surch
            self.node_storage_m3[nid] = stored

            step_storage_total += stored
            step_surcharge_total += surch

        # 5. Cumulative Mass Conservation Accounting
        step_inflow_total = sum(inflow_map.values())
        self.cumulative_inflow_m3 += step_inflow_total
        self.cumulative_outlet_discharge_m3 += step_outlet_total
        self.cumulative_surcharge_m3 += step_surcharge_total
        self.last_timestamp_seconds = t

        error_m3 = (
            self.cumulative_inflow_m3
            - step_storage_total
            - self.cumulative_outlet_discharge_m3
            - self.cumulative_surcharge_m3
        )

        step_res = DrainageStepResult(
            timestamp_seconds=t,
            timestep_seconds=dt,
            node_storage_m3_by_node=new_storage_m3,
            edge_flows=edge_flow_results,
            outlet_discharge_m3_by_node=outlet_discharge_m3,
            surcharge_volume_m3_by_node=surcharge_m3,
            external_inflow_m3=step_inflow_total,
            transmitted_volume_m3=total_pipe_transmitted_m3,
            outlet_volume_m3=step_outlet_total,
            stored_volume_m3=step_storage_total,
            surcharge_volume_m3=step_surcharge_total,
            mass_balance_error_m3=error_m3,
        )
        self.history.append(step_res)
        return step_res

    def mass_balance(self) -> Dict[str, Any]:
        """Returns cumulative mass balance accounting across the drainage network."""
        current_stored = sum(self.node_storage_m3.values())
        error_m3 = (
            self.cumulative_inflow_m3
            - current_stored
            - self.cumulative_outlet_discharge_m3
            - self.cumulative_surcharge_m3
        )
        return {
            "cumulative_inflow_m3": round(self.cumulative_inflow_m3, 6),
            "current_node_storage_m3": round(current_stored, 6),
            "cumulative_outlet_discharge_m3": round(self.cumulative_outlet_discharge_m3, 6),
            "cumulative_surcharge_m3": round(self.cumulative_surcharge_m3, 6),
            "mass_balance_error_m3": round(error_m3, 8),
            "is_conserved": abs(error_m3) <= 1e-5,
        }

    def traverse_volume(
        self,
        source_node: Any,
        target_node: Any,
        volume_m3: float,
        dt_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        """Diagnostic path traversal helper."""
        src_str = str(source_node)
        tgt_str = str(target_node)
        if not nx.has_path(self.graph, src_str, tgt_str):
            return {"reachable": False, "delivered_volume_m3": 0.0, "blocked_volume_m3": float(volume_m3)}

        path = nx.shortest_path(self.graph, src_str, tgt_str)
        path_edges = []
        min_cap_vol = float("inf")
        limiting_edge = None

        for u, v in zip(path[:-1], path[1:]):
            edge_data = self.graph[u][v]["data"]
            path_edges.append(edge_data.edge_id)
            cap_vol = edge_data.capacity_m3_s * dt_seconds
            if cap_vol < min_cap_vol:
                min_cap_vol = cap_vol
                limiting_edge = edge_data.edge_id

        delivered = min(float(volume_m3), min_cap_vol)
        blocked = max(0.0, float(volume_m3) - delivered)

        return {
            "reachable": True,
            "path": path,
            "path_edges": path_edges,
            "requested_volume_m3": float(volume_m3),
            "delivered_volume_m3": round(delivered, 6),
            "blocked_volume_m3": round(blocked, 6),
            "limiting_edge": limiting_edge,
            "bottleneck_capacity_m3_s": self.edges[limiting_edge].capacity_m3_s if limiting_edge else 0.0,
        }

    @classmethod
    def create_synthetic_demo_network(cls) -> "StatefulDrainageNetwork":
        """Creates canonical 5-node branching test drainage network."""
        nodes = [
            DrainageNode(node_id="N001", latitude=13.010, longitude=80.200, node_type="inlet", storage_capacity_m3=5.0, associated_cell_id="C00001"),
            DrainageNode(node_id="N002", latitude=13.008, longitude=80.202, node_type="manhole", storage_capacity_m3=10.0, associated_cell_id="C00022"),
            DrainageNode(node_id="N003", latitude=13.005, longitude=80.205, node_type="manhole", storage_capacity_m3=10.0, associated_cell_id="C00064"),
            DrainageNode(node_id="N004", latitude=13.000, longitude=80.210, node_type="outlet", base_capacity_m3_s=0.10, storage_capacity_m3=20.0, associated_cell_id="C00295"),
            DrainageNode(node_id="N005", latitude=13.002, longitude=80.208, node_type="outlet", base_capacity_m3_s=0.08, storage_capacity_m3=15.0, associated_cell_id="C00274"),
        ]
        edges = [
            DrainageEdge(edge_id="E001", from_node="N001", to_node="N002", length_m=100.0, capacity_m3_s=0.05),
            DrainageEdge(edge_id="E002", from_node="N002", to_node="N003", length_m=150.0, capacity_m3_s=0.04),
            DrainageEdge(edge_id="E003", from_node="N003", to_node="N004", length_m=200.0, capacity_m3_s=0.06),
            DrainageEdge(edge_id="E004", from_node="N002", to_node="N005", length_m=120.0, capacity_m3_s=0.03),
        ]
        return cls(nodes=nodes, edges=edges, expected_timestep_seconds=60)


# Backward compatibility alias
DrainageNetwork = StatefulDrainageNetwork
