"""
Road network graph representation and risk assessment based on flood depth.
"""

from typing import Dict, List, Tuple, Optional
import networkx as nx


class RoadSegment:
    def __init__(
        self,
        road_id: str,
        u_node: str,
        v_node: str,
        length_m: float,
        speed_limit_kmh: float = 40.0,
        associated_cell_ids: Optional[List[int]] = None,
        name: str = "",
    ):
        self.road_id = road_id
        self.u_node = u_node
        self.v_node = v_node
        self.length_m = length_m
        self.speed_limit_kmh = speed_limit_kmh
        self.associated_cell_ids = associated_cell_ids or []
        self.name = name or road_id

        # Travel time in minutes
        speed_m_min = (speed_limit_kmh * 1000.0) / 60.0
        self.base_travel_time_min = length_m / max(speed_m_min, 1.0)

        # Dynamic flood state
        self.predicted_depth_cm: float = 0.0
        self.risk_level: str = "SAFE"  # 'SAFE', 'WATCH', 'HIGH', 'UNSAFE'
        self.risk_score: float = 0.0
        self.confidence: float = 1.0
        self.data_quality: str = "HIGH_CONF"

    def update_flood_risk(
        self,
        cell_depths: Dict[int, float],
        cell_confidences: Dict[int, float],
    ):
        if not self.associated_cell_ids:
            self.predicted_depth_cm = 0.0
            self.risk_level = "SAFE"
            self.risk_score = 0.0
            self.confidence = 1.0
            self.data_quality = "MODEL_ONLY"
            return

        depths = [cell_depths.get(cid, 0.0) for cid in self.associated_cell_ids]
        confs = [cell_confidences.get(cid, 0.5) for cid in self.associated_cell_ids]

        self.predicted_depth_cm = float(max(depths))
        self.confidence = float(min(confs))

        # Risk level determination
        if self.predicted_depth_cm < 5.0:
            self.risk_level = "SAFE"
            self.risk_score = 0.0
        elif self.predicted_depth_cm < 15.0:
            self.risk_level = "WATCH"
            self.risk_score = 1.0 + (self.predicted_depth_cm - 5.0) / 10.0
        elif self.predicted_depth_cm < 30.0:
            self.risk_level = "HIGH"
            self.risk_score = 3.0 + (self.predicted_depth_cm - 15.0) / 5.0
        else:
            self.risk_level = "UNSAFE"
            self.risk_score = 10.0 + (self.predicted_depth_cm - 30.0)

        # Data quality determination
        if self.confidence >= 0.75:
            self.data_quality = "HIGH_CONF"
        elif self.confidence >= 0.50:
            self.data_quality = "MEDIUM_CONF"
        elif self.confidence >= 0.25:
            self.data_quality = "LOW_CONF"
        else:
            self.data_quality = "MODEL_ONLY"


class RoadNetwork:
    def __init__(self):
        self.roads: Dict[str, RoadSegment] = {}
        self.nodes: Dict[str, Tuple[float, float]] = {}  # node_id -> (lat, lon) or (x, y)
        self.graph = nx.Graph()

    def add_node(self, node_id: str, position: Tuple[float, float]):
        self.nodes[node_id] = position
        self.graph.add_node(node_id, pos=position)

    def add_road(self, road: RoadSegment):
        self.roads[road.road_id] = road
        self.graph.add_edge(
            road.u_node,
            road.v_node,
            road_id=road.road_id,
            road=road,
        )

    def update_all_risks(
        self,
        cell_depths: Dict[int, float],
        cell_confidences: Dict[int, float],
    ):
        for road in self.roads.values():
            road.update_flood_risk(cell_depths, cell_confidences)
