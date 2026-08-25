"""
Drainage network representation with graph topology, dynamic capacity factors,
and surface-to-drain inlet capture.
"""

from typing import Dict, List, Optional
import networkx as nx


class DrainageNode:
    def __init__(
        self,
        node_id: int,
        cell_id: int,
        node_type: str = "inlet",  # 'inlet', 'manhole', 'junction', 'outfall'
        base_capacity_m3_s: float = 0.5,
        capacity_factor: float = 1.0,
        name: Optional[str] = None,
    ):
        self.node_id = node_id
        self.cell_id = cell_id
        self.node_type = node_type
        self.base_capacity_m3_s = base_capacity_m3_s
        self.capacity_factor = float(capacity_factor)
        self.name = name or f"Node-{node_id}"
        self.captured_this_step_m3: float = 0.0

    @property
    def effective_capacity_m3_s(self) -> float:
        return max(0.0, self.base_capacity_m3_s * self.capacity_factor)

    def set_capacity_factor(self, factor: float):
        self.capacity_factor = float(max(0.0, min(1.0, factor)))


class DrainageEdge:
    def __init__(
        self,
        edge_id: int,
        from_node: int,
        to_node: int,
        length_m: float = 20.0,
        diameter_m: float = 0.6,
        slope: float = 0.01,
        base_capacity_m3_s: float = 0.8,
    ):
        self.edge_id = edge_id
        self.from_node = from_node
        self.to_node = to_node
        self.length_m = length_m
        self.diameter_m = diameter_m
        self.slope = slope
        self.base_capacity_m3_s = base_capacity_m3_s
        self.current_flow_m3_s: float = 0.0


class DrainageNetwork:
    def __init__(self):
        self.nodes: Dict[int, DrainageNode] = {}
        self.edges: Dict[int, DrainageEdge] = {}
        self.cell_to_node: Dict[int, int] = {}
        self.graph = nx.DiGraph()

    def add_node(self, node: DrainageNode):
        self.nodes[node.node_id] = node
        self.cell_to_node[node.cell_id] = node.node_id
        self.graph.add_node(node.node_id, data=node)

    def add_edge(self, edge: DrainageEdge):
        self.edges[edge.edge_id] = edge
        self.graph.add_edge(edge.from_node, edge.to_node, data=edge)

    def get_inlet_for_cell(self, cell_id: int) -> Optional[DrainageNode]:
        node_id = self.cell_to_node.get(cell_id)
        if node_id is not None:
            return self.nodes[node_id]
        return None

    def compute_capture(self, cell_id: int, available_storage_m3: float, dt: float) -> float:
        """
        Computes water volume captured from surface grid cell into drainage network at time t.
        """
        node = self.get_inlet_for_cell(cell_id)
        if node is None:
            return 0.0

        max_capture_volume = node.effective_capacity_m3_s * dt
        captured = min(max_capture_volume, max(0.0, available_storage_m3))
        node.captured_this_step_m3 = captured
        return captured
