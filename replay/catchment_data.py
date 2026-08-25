"""
Synthetic Catchment Generator for Demo Catchment (20x20 grid, 400 cells, 10m resolution).
Generates terrain DEM, D8 flow, drainage network, road network, and sensor placements.
"""

from typing import Dict, List, Tuple, Any
import numpy as np

from flood_engine.dem import priority_flood_fill, compute_d8_flow_directions, cell_to_id
from flood_engine.drainage import DrainageNetwork, DrainageNode, DrainageEdge
from routing.road_graph import RoadNetwork, RoadSegment
from sensor.health import SensorNode


def generate_demo_catchment(
    rows: int = 20,
    cols: int = 20,
    cell_size_m: float = 10.0,
) -> Dict[str, Any]:
    """
    Builds the complete catchment model for the demonstration.
    """
    # 1. Generate realistic terrain with a ridge and a central drainage valley
    # Elevation slopes from ~32m in NW down to ~12m in SE, with a trough in the middle
    elevation_grid = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            # Regional slope
            base_elev = 30.0 - 0.7 * r - 0.5 * c
            # Natural swale/valley along diagonal r ~ c
            valley_dist = abs(r - c)
            valley_dip = max(0.0, 3.5 - 0.5 * valley_dist)
            elevation_grid[r, c] = max(10.0, base_elev - valley_dip)

    # Apply pit fill
    filled_dem = priority_flood_fill(elevation_grid)
    flow_dirs = compute_d8_flow_directions(filled_dem, cell_size_m=cell_size_m)

    # 2. Curve Numbers (CN)
    # Urban asphalt/commercial ~ 88-92, residential ~ 75-80, green park ~ 60-65
    cn_grid = np.full((rows, cols), 80.0, dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            if r < 6 and c < 6:
                cn_grid[r, c] = 90.0  # Dense downtown
            elif r > 12 and c > 12:
                cn_grid[r, c] = 85.0  # Industrial zone
            elif abs(r - c) <= 1:
                cn_grid[r, c] = 68.0  # Vegetated riparian buffer

    # 3. Drainage Network
    drainage = DrainageNetwork()
    # 8 inlet nodes along the central valley and low points
    inlet_locations = [
        (2, 2), (5, 5), (8, 8), (11, 11), (14, 14), (17, 17), (19, 19),
        (5, 2), (2, 5), (14, 11), (11, 14)
    ]
    node_objects: List[DrainageNode] = []
    for idx, (r, c) in enumerate(inlet_locations):
        cid = cell_to_id(r, c, cols)
        ntype = "outfall" if (r, c) == (19, 19) else "inlet"
        cap = 1.2 if ntype == "outfall" else 0.6
        node = DrainageNode(
            node_id=idx + 1,
            cell_id=cid,
            node_type=ntype,
            base_capacity_m3_s=cap,
            capacity_factor=1.0,
            name=f"Inlet-{idx + 1}" if ntype == "inlet" else "Main-Outfall",
        )
        drainage.add_node(node)
        node_objects.append(node)

    # Underground pipe edges connecting consecutive inlets downstream
    pipe_connections = [
        (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),
        (8, 2), (9, 2), (10, 5), (11, 5)
    ]
    for edge_id, (from_n, to_n) in enumerate(pipe_connections, start=1):
        edge = DrainageEdge(
            edge_id=edge_id,
            from_node=from_n,
            to_node=to_n,
            length_m=35.0,
            diameter_m=0.8,
            slope=0.015,
            base_capacity_m3_s=1.0,
        )
        drainage.add_edge(edge)

    # 4. Road Network (Urban grid with 16 junction nodes and arterial roads)
    roads = RoadNetwork()
    # 4x4 junction grid (coordinates mapped to grid positions)
    junction_coords = {}
    for jr in range(4):
        for jc in range(4):
            jid = f"J{jr * 4 + jc + 1}"
            grid_r = int(jr * 6 + 1)
            grid_c = int(jc * 6 + 1)
            junction_coords[jid] = (grid_r, grid_c)
            roads.add_node(jid, (grid_r, grid_c))

    # Horizontal and vertical road segments
    road_id_seq = 1
    # Horizontal roads
    for jr in range(4):
        for jc in range(3):
            u = f"J{jr * 4 + jc + 1}"
            v = f"J{jr * 4 + jc + 2}"
            r1, c1 = junction_coords[u]
            r2, c2 = junction_coords[v]
            # Associate intermediate cells along the segment
            assoc_cells = [cell_to_id(r1, c, cols) for c in range(c1 + 1, c2)]
            if not assoc_cells:
                assoc_cells = [cell_to_id(r1, c1, cols)]
            road_seg = RoadSegment(
                road_id=f"RD-{road_id_seq:02d}",
                u_node=u,
                v_node=v,
                length_m=60.0,
                speed_limit_kmh=45.0,
                associated_cell_ids=assoc_cells,
                name=f"Cross St {road_id_seq}",
            )
            roads.add_road(road_seg)
            road_id_seq += 1

    # Vertical roads
    for jc in range(4):
        for jr in range(3):
            u = f"J{jr * 4 + jc + 1}"
            v = f"J{(jr + 1) * 4 + jc + 1}"
            r1, c1 = junction_coords[u]
            r2, c2 = junction_coords[v]
            assoc_cells = [cell_to_id(r, c1, cols) for r in range(r1 + 1, r2)]
            if not assoc_cells:
                assoc_cells = [cell_to_id(r1, c1, cols)]
            road_seg = RoadSegment(
                road_id=f"RD-{road_id_seq:02d}",
                u_node=u,
                v_node=v,
                length_m=60.0,
                speed_limit_kmh=50.0,
                associated_cell_ids=assoc_cells,
                name=f"Avenue {road_id_seq}",
            )
            roads.add_road(road_seg)
            road_id_seq += 1

    # 5. Sensor Nodes (Ultrasonic + Float in low points and key manholes)
    sensor_nodes: List[SensorNode] = [
        SensorNode(sensor_id=1, name="Sensor-CentralSwale-1", cell_id=cell_to_id(5, 5, cols), sensor_type="ultrasonic", installation_height_cm=180.0, latitude=5.0, longitude=5.0),
        SensorNode(sensor_id=2, name="Sensor-MidValley-2", cell_id=cell_to_id(8, 8, cols), sensor_type="ultrasonic", installation_height_cm=180.0, latitude=8.0, longitude=8.0),
        SensorNode(sensor_id=3, name="Sensor-LowBasin-3", cell_id=cell_to_id(14, 14, cols), sensor_type="ultrasonic", installation_height_cm=200.0, latitude=14.0, longitude=14.0),
        SensorNode(sensor_id=4, name="Sensor-NorthInlet-4", cell_id=cell_to_id(2, 5, cols), sensor_type="float", installation_height_cm=100.0, latitude=2.0, longitude=5.0),
        SensorNode(sensor_id=5, name="Sensor-SouthDrain-5", cell_id=cell_to_id(17, 17, cols), sensor_type="ultrasonic", installation_height_cm=220.0, latitude=17.0, longitude=17.0),
        SensorNode(sensor_id=6, name="Sensor-Outfall-6", cell_id=cell_to_id(19, 19, cols), sensor_type="float", installation_height_cm=150.0, latitude=19.0, longitude=19.0),
    ]

    return {
        "rows": rows,
        "cols": cols,
        "cell_size_m": cell_size_m,
        "elevation_grid": filled_dem,
        "raw_elevation_grid": elevation_grid,
        "flow_dirs": flow_dirs,
        "cn_grid": cn_grid,
        "drainage": drainage,
        "roads": roads,
        "sensors": sensor_nodes,
    }
