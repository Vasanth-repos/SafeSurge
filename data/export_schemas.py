"""
Standard Dataset Generation and Export Tool according to SafeSurge / AURA-FLOOD Spec Section 15.
Generates:
1. rainfall.csv
2. landuse.geojson
3. drainage_nodes.geojson
4. drainage_edges.geojson
5. roads.geojson
6. sensors.csv
7. sensor_registry.yaml
8. historical_floods.csv
"""

import csv
import json
import math
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "raw")


def generate_all_spec_datasets(output_dir: str = OUTPUT_DIR) -> dict[str, str]:
    """Compile and export all Section 15 standardized datasets."""
    os.makedirs(output_dir, exist_ok=True)
    generated_files = {}

    # 1. rainfall.csv (timestamp, cell_id, latitude, longitude, rainfall_mm, rainfall_rate_mm_hr)
    rf_path = os.path.join(output_dir, "rainfall.csv")
    with open(rf_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "cell_id", "latitude", "longitude", "rainfall_mm", "rainfall_rate_mm_hr"])
        base_lat, base_lon = 13.0827, 80.2707  # Chennai reference coordinates
        for t_min in range(0, 181, 15):
            int_factor = math.sin(min(math.pi, (t_min / 180.0) * math.pi))
            rate = round(45.0 * int_factor, 1)
            rain_mm = round(rate * 0.25, 2)
            for r in range(10):
                for c in range(10):
                    cid = f"C{r * 10 + c + 1:03d}"
                    lat = round(base_lat + r * 0.001, 5)
                    lon = round(base_lon + c * 0.001, 5)
                    writer.writerow([t_min * 60, cid, lat, lon, rain_mm, rate])
    generated_files["rainfall.csv"] = rf_path

    # 2. landuse.geojson (cell_id, land_use, impervious_fraction, curve_number)
    lu_path = os.path.join(output_dir, "landuse.geojson")
    features = []
    for r in range(10):
        for c in range(10):
            cid = f"C{r * 10 + c + 1:03d}"
            lat = round(base_lat + r * 0.001, 5)
            lon = round(base_lon + c * 0.001, 5)
            if r in [0, 9] or c in [0, 9]:
                lu, imp, cn = "dense_urban", 0.85, 92
            elif abs(r - c) <= 1:
                lu, imp, cn = "road_corridor", 0.95, 95
            elif r >= 5 and c >= 6:
                lu, imp, cn = "lowland_residential", 0.70, 88
            else:
                lu, imp, cn = "mixed_urban", 0.60, 84
            
            # Simple 100m x 100m polygon
            ddeg = 0.0009
            poly = [
                [lon, lat],
                [lon + ddeg, lat],
                [lon + ddeg, lat + ddeg],
                [lon, lat + ddeg],
                [lon, lat]
            ]
            features.append({
                "type": "Feature",
                "properties": {
                    "cell_id": cid,
                    "land_use": lu,
                    "impervious_fraction": imp,
                    "curve_number": cn,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [poly],
                }
            })
    with open(lu_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)
    generated_files["landuse.geojson"] = lu_path

    # 3. drainage_nodes.geojson (node_id, latitude, longitude, node_type, invert_elevation, base_capacity)
    dn_path = os.path.join(output_dir, "drainage_nodes.geojson")
    nodes_data = [
        {"node_id": "IN01", "r": 4, "c": 4, "type": "inlet", "invert_elev": 14.5, "base_cap": 25.0},
        {"node_id": "IN02", "r": 2, "c": 3, "type": "inlet", "invert_elev": 16.8, "base_cap": 20.0},
        {"node_id": "E001", "r": 6, "c": 7, "type": "culvert_inlet", "invert_elev": 12.2, "base_cap": 30.0},
        {"node_id": "JUN1", "r": 6, "c": 5, "type": "manhole_junction", "invert_elev": 12.0, "base_cap": 45.0},
        {"node_id": "OUT1", "r": 9, "c": 9, "type": "outfall", "invert_elev": 9.5, "base_cap": 80.0},
    ]
    d_node_feats = []
    for nd in nodes_data:
        lat = round(base_lat + nd["r"] * 0.001, 5)
        lon = round(base_lon + nd["c"] * 0.001, 5)
        d_node_feats.append({
            "type": "Feature",
            "properties": {
                "node_id": nd["node_id"],
                "node_type": nd["type"],
                "invert_elevation": nd["invert_elev"],
                "base_capacity": nd["base_cap"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            }
        })
    with open(dn_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": d_node_feats}, f, indent=2)
    generated_files["drainage_nodes.geojson"] = dn_path

    # 4. drainage_edges.geojson (edge_id, from_node, to_node, length, diameter, slope, capacity)
    de_path = os.path.join(output_dir, "drainage_edges.geojson")
    edges_data = [
        {"edge_id": "P001", "from_node": "IN02", "to_node": "IN01", "length": 180.0, "diameter": 0.8, "slope": 0.012, "capacity": 20.0},
        {"edge_id": "P002", "from_node": "IN01", "to_node": "JUN1", "length": 140.0, "diameter": 1.0, "slope": 0.015, "capacity": 35.0},
        {"edge_id": "P003", "from_node": "E001", "to_node": "JUN1", "length": 160.0, "diameter": 1.2, "slope": 0.010, "capacity": 30.0},
        {"edge_id": "P004", "from_node": "JUN1", "to_node": "OUT1", "length": 320.0, "diameter": 1.5, "slope": 0.018, "capacity": 75.0},
    ]
    de_feats = []
    for ed in edges_data:
        de_feats.append({
            "type": "Feature",
            "properties": ed,
            "geometry": {
                "type": "LineString",
                "coordinates": [[base_lon, base_lat], [base_lon + 0.005, base_lat + 0.005]],
            }
        })
    with open(de_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": de_feats}, f, indent=2)
    generated_files["drainage_edges.geojson"] = de_path

    # 5. roads.geojson (road_id, road_name, geometry, road_class, speed)
    rd_path = os.path.join(output_dir, "roads.geojson")
    roads_data = [
        {"road_id": "R001", "road_name": "North Ave (A -> B)", "road_class": "arterial", "speed": 50},
        {"road_id": "R002", "road_name": "East Expwy (B -> E)", "road_class": "highway", "speed": 60},
        {"road_id": "R003", "road_name": "West Bypass (A -> W)", "road_class": "arterial", "speed": 45},
        {"road_id": "R004", "road_name": "South Hwy (C -> D)", "road_class": "highway", "speed": 60},
        {"road_id": "R005", "road_name": "East Underpass (E -> D)", "road_class": "secondary", "speed": 35},
        {"road_id": "R006", "road_name": "Central Spine (A -> M)", "road_class": "arterial", "speed": 40},
        {"road_id": "R007", "road_name": "Midtown Arterial (M -> D)", "road_class": "arterial", "speed": 40},
        {"road_id": "R008", "road_name": "West Link (W -> M)", "road_class": "collector", "speed": 30},
        {"road_id": "R009", "road_name": "East Connector (M -> E)", "road_class": "collector", "speed": 30},
        {"road_id": "R010", "road_name": "West Ridge (W -> C)", "road_class": "arterial", "speed": 45},
    ]
    rd_feats = []
    for rd in roads_data:
        rd_feats.append({
            "type": "Feature",
            "properties": rd,
            "geometry": {
                "type": "LineString",
                "coordinates": [[base_lon, base_lat], [base_lon + 0.008, base_lat + 0.008]],
            }
        })
    with open(rd_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": rd_feats}, f, indent=2)
    generated_files["roads.geojson"] = rd_path

    # 6. sensors.csv (sensor_id, timestamp, latitude, longitude, distance_cm, water_depth_cm, status, battery, rssi)
    sens_path = os.path.join(output_dir, "sensors.csv")
    with open(sens_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sensor_id", "timestamp", "latitude", "longitude", "distance_cm", "water_depth_cm", "status", "battery", "rssi"])
        stations = [
            ("S001", 1, 1, 100.0, 4.8),
            ("S002", 2, 4, 120.0, 5.1),
            ("S003", 4, 4, 110.0, 6.4),
            ("S004", 6, 7, 130.0, 14.6),
            ("S005", 6, 0, 100.0, 5.4),
            ("S006", 8, 7, 125.0, 11.9),
        ]
        for t_min in range(0, 181, 15):
            for sid, r, c, ref_h, base_d in stations:
                factor = math.sin(min(math.pi, (t_min / 180.0) * math.pi))
                depth = round(base_d * factor, 1)
                dist = round(ref_h - depth, 1)
                lat = round(base_lat + r * 0.001, 5)
                lon = round(base_lon + c * 0.001, 5)
                writer.writerow([sid, t_min * 60, lat, lon, dist, depth, "ONLINE", 98, -62])
    generated_files["sensors.csv"] = sens_path

    # 7. historical_floods.csv (event_id, timestamp, latitude, longitude, road_id, observed_depth_cm, source)
    hf_path = os.path.join(output_dir, "historical_floods.csv")
    with open(hf_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "timestamp", "latitude", "longitude", "road_id", "observed_depth_cm", "source"])
        writer.writerow(["EV001", "2023-12-04T10:30:00Z", 13.0887, 80.2787, "R007", 28.5, "Corporation Complaint"])
        writer.writerow(["EV002", "2023-12-04T11:15:00Z", 13.0867, 80.2777, "R005", 26.0, "Traffic Police Alert"])
        writer.writerow(["EV003", "2023-12-04T12:00:00Z", 13.0847, 80.2747, "R002", 18.2, "Automated Sensor S004"])
    generated_files["historical_floods.csv"] = hf_path

    return generated_files


if __name__ == "__main__":
    files = generate_all_spec_datasets()
    print(f"Generated {len(files)} specification datasets in {OUTPUT_DIR}:")
    for name, p in files.items():
        print(f"  - {name} ({os.path.getsize(p)} bytes)")
