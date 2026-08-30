"""
SafeSurge - AURA-FLOOD synthetic dataset generator
Produces the 4 datasets flagged as genuinely missing/unavailable publicly:
  1. drainage_nodes.geojson / drainage_edges.geojson   (drainage graph)
  2. drainage capacity is embedded in the nodes/edges above (base_capacity, condition_factor)
  3. historical_floods.csv
  4. dem.csv (DEM proxy grid - real raster DEM still needs Cartosat-1/SRTM;
     this generates a plausible elevation surface for the same synthetic
     10x10 catchment used in landuse/roads/sensors)

Also regenerates the supporting datasets (landuse, roads, sensors, rainfall)
so the whole MVP set is internally consistent (same grid, same coordinate
frame, same cell IDs) - useful even though roads/rainfall have real sources,
because a hackathon demo needs everything to line up spatially.

All values are SYNTHETIC. Do not present as real municipal data.
"""

import csv
import json
import math
import random

random.seed(42)

# ---------------------------------------------------------------
# 1. Grid definition: 10x10 cells over a small bounding box
#    (placeholder coords near Chennai; shift these to your real
#    pilot area's bounding box before using)
# ---------------------------------------------------------------
GRID_N = 10
LAT0, LON0 = 13.0500, 80.2000     # bottom-left corner
CELL_SIZE_DEG = 0.0018             # ~200m per cell

def cell_id(r, c):
    return f"C{r:02d}{c:02d}"

def cell_latlon(r, c):
    lat = LAT0 + r * CELL_SIZE_DEG
    lon = LON0 + c * CELL_SIZE_DEG
    return round(lat, 6), round(lon, 6)

# ---------------------------------------------------------------
# 2. DEM: elevation surface with 1 ridge (top-right), 1 valley
#    (diagonal), 1 low-lying basin (bottom-left), matching the
#    narrative already used in the spec document.
# ---------------------------------------------------------------
def elevation(r, c):
    base = 20.0
    # general slope: high top-right -> low bottom-left
    slope_component = -(r + c) * 0.45
    # basin depression near bottom-left
    basin_dist = math.hypot(r - 1, c - 1)
    basin_dip = -3.5 * math.exp(-(basin_dist**2) / 4)
    # ridge bump near top-right
    ridge_dist = math.hypot(r - 8, c - 8)
    ridge_bump = 2.5 * math.exp(-(ridge_dist**2) / 6)
    # small random micro-topography noise
    noise = random.uniform(-0.3, 0.3)
    return round(base + slope_component + basin_dip + ridge_bump + noise, 2)

dem_rows = []
for r in range(GRID_N):
    for c in range(GRID_N):
        lat, lon = cell_latlon(r, c)
        dem_rows.append({
            "cell_id": cell_id(r, c),
            "row": r, "col": c,
            "latitude": lat, "longitude": lon,
            "elevation_m": elevation(r, c)
        })

with open("dem.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["cell_id","row","col","latitude","longitude","elevation_m"])
    w.writeheader()
    w.writerows(dem_rows)

elev_lookup = {row["cell_id"]: row["elevation_m"] for row in dem_rows}

# ---------------------------------------------------------------
# 3. Land use / curve number per cell
# ---------------------------------------------------------------
LAND_USE_PROFILES = [
    ("ROAD", 0.95, 96),
    ("RESIDENTIAL", 0.65, 88),
    ("COMMERCIAL", 0.85, 92),
    ("PARK", 0.15, 68),
    ("WATER_BODY", 0.02, 100),  # CN=100 as a modeling convenience, not literal
]

def assign_landuse(r, c):
    # deterministic-ish but varied assignment
    if (r, c) in [(1,1),(2,1),(1,2)]:
        return "WATER_BODY"
    if r % 4 == 0 and c % 3 == 0:
        return "PARK"
    if r >= 7 and c >= 7:
        return "COMMERCIAL"
    if (r + c) % 5 == 0:
        return "ROAD"
    return "RESIDENTIAL"

landuse_features = []
for r in range(GRID_N):
    for c in range(GRID_N):
        lat, lon = cell_latlon(r, c)
        lu = assign_landuse(r, c)
        profile = next(p for p in LAND_USE_PROFILES if p[0] == lu)
        landuse_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "cell_id": cell_id(r, c),
                "land_use": lu,
                "impervious_fraction": profile[1],
                "curve_number": profile[2]
            }
        })

with open("landuse.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": landuse_features}, f, indent=2)

# ---------------------------------------------------------------
# 4. Drainage network graph
#    Strategy: pick 15 nodes at locally low-elevation cells,
#    connect them following the downhill direction toward one
#    outfall at the lowest point, forming a converging tree -
#    this is what a real stormwater network looks like topologically.
# ---------------------------------------------------------------
sorted_cells = sorted(dem_rows, key=lambda x: x["elevation_m"])
NUM_NODES = 15
node_cells = sorted_cells[:NUM_NODES]          # lowest 15 cells get drainage nodes
outfall_cell = sorted_cells[0]                  # lowest point = outfall

NODE_TYPES = ["INLET", "JUNCTION", "JUNCTION", "INLET", "OUTFALL"]

drainage_nodes = []
node_id_map = {}
for i, cell in enumerate(node_cells):
    nid = f"N{i+1:02d}"
    node_id_map[cell["cell_id"]] = nid
    is_outfall = (cell["cell_id"] == outfall_cell["cell_id"])
    ntype = "OUTFALL" if is_outfall else random.choice(["INLET", "INLET", "JUNCTION"])
    base_capacity = round(random.uniform(8, 25), 1) if ntype != "OUTFALL" else round(random.uniform(30, 45), 1)
    drainage_nodes.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [cell["longitude"], cell["latitude"]]},
        "properties": {
            "node_id": nid,
            "source_cell": cell["cell_id"],
            "node_type": ntype,
            "invert_elevation_m": round(cell["elevation_m"] - random.uniform(1.0, 2.5), 2),
            "base_capacity_m3_per_min": base_capacity
        }
    })

with open("drainage_nodes.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": drainage_nodes}, f, indent=2)

# Build edges: each non-outfall node connects to its nearest lower-elevation node (downhill)
def dist(a, b):
    return math.hypot(a["latitude"] - b["latitude"], a["longitude"] - b["longitude"])

edges = []
edge_counter = 1
for i, cell in enumerate(node_cells):
    if cell["cell_id"] == outfall_cell["cell_id"]:
        continue
    candidates = [nc for nc in node_cells if nc["elevation_m"] < cell["elevation_m"]]
    if not candidates:
        target = outfall_cell
    else:
        target = min(candidates, key=lambda nc: dist(cell, nc))
    from_id = node_id_map[cell["cell_id"]]
    to_id = node_id_map[target["cell_id"]]
    length_m = round(dist(cell, target) * 111000, 1)  # rough deg->m
    diameter_mm = random.choice([300, 450, 600, 900])
    slope = round(max(0.001, (cell["elevation_m"] - target["elevation_m"]) / max(length_m, 1)), 4)
    capacity = round(random.uniform(5, 20), 1)
    condition_factor = round(random.choice([1.0, 1.0, 0.9, 0.7, 0.5, 0.3]), 2)  # some degraded
    edges.append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [cell["longitude"], cell["latitude"]],
                [target["longitude"], target["latitude"]]
            ]
        },
        "properties": {
            "edge_id": f"E{edge_counter:02d}",
            "from_node": from_id,
            "to_node": to_id,
            "length_m": length_m,
            "diameter_mm": diameter_mm,
            "slope": slope,
            "base_capacity_m3_per_min": capacity,
            "condition_factor": condition_factor,
            "effective_capacity_m3_per_min": round(capacity * condition_factor, 2)
        }
    })
    edge_counter += 1

# add a few extra cross-links so it's a graph, not a strict tree (loops happen in real networks)
extra_links = 6
attempts = 0
while extra_links > 0 and attempts < 50:
    attempts += 1
    a, b = random.sample(node_cells, 2)
    if a["elevation_m"] <= b["elevation_m"]:
        continue
    from_id, to_id = node_id_map[a["cell_id"]], node_id_map[b["cell_id"]]
    if any(e["properties"]["from_node"] == from_id and e["properties"]["to_node"] == to_id for e in edges):
        continue
    length_m = round(dist(a, b) * 111000, 1)
    diameter_mm = random.choice([300, 450, 600])
    slope = round(max(0.001, (a["elevation_m"] - b["elevation_m"]) / max(length_m, 1)), 4)
    capacity = round(random.uniform(5, 15), 1)
    condition_factor = round(random.choice([1.0, 0.9, 0.8, 0.6]), 2)
    edges.append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[a["longitude"], a["latitude"]], [b["longitude"], b["latitude"]]]
        },
        "properties": {
            "edge_id": f"E{edge_counter:02d}",
            "from_node": from_id,
            "to_node": to_id,
            "length_m": length_m,
            "diameter_mm": diameter_mm,
            "slope": slope,
            "base_capacity_m3_per_min": capacity,
            "condition_factor": condition_factor,
            "effective_capacity_m3_per_min": round(capacity * condition_factor, 2)
        }
    })
    edge_counter += 1
    extra_links -= 1

with open("drainage_edges.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": edges}, f, indent=2)

# ---------------------------------------------------------------
# 5. Roads: 10 segments crossing the grid, some passing near
#    drainage-poor (low condition_factor) nodes so flooding demo
#    has a clear "this road floods" storyline
# ---------------------------------------------------------------
road_paths = [
    [(0,0),(2,2),(4,4)],
    [(4,4),(6,6),(8,8)],
    [(1,8),(3,6),(5,4)],
    [(9,0),(7,1),(5,2)],
    [(0,5),(2,5),(4,5)],
    [(5,0),(5,3),(5,6)],
    [(2,9),(4,7),(6,5)],
    [(8,1),(8,4),(8,7)],
    [(0,9),(2,7),(4,5)],
    [(9,9),(7,7),(5,5)],
]

roads = []
for i, path in enumerate(road_paths):
    coords = []
    for (r, c) in path:
        lat, lon = cell_latlon(r, c)
        coords.append([lon, lat])
    roads.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "road_id": f"R{i+1:03d}",
            "road_name": f"Synthetic Road {i+1}",
            "road_class": random.choice(["arterial", "collector", "local"]),
            "speed_kmph": random.choice([30, 40, 50])
        }
    })

with open("roads.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": roads}, f, indent=2)

# ---------------------------------------------------------------
# 6. Sensor registry: 6 stations at functionally distinct points
# ---------------------------------------------------------------
station_defs = [
    ("S001", "HEADWATER", (9, 9)),
    ("S002", "ARTERIAL",  (5, 5)),
    ("S003", "BASIN",     (1, 1)),
    ("S004", "DEPRESSION",(2, 2)),
    ("S005", "ELEVATED",  (8, 2)),
    ("S006", "OUTFALL",   (outfall_cell["row"], outfall_cell["col"])),
]

sensor_registry = []
for sid, role, (r, c) in station_defs:
    lat, lon = cell_latlon(r, c)
    sensor_registry.append({
        "sensor_id": sid,
        "role": role,
        "latitude": lat,
        "longitude": lon,
        "reference_height_cm": random.choice([80, 100, 120]),
        "min_range_cm": 2,
        "max_range_cm": 400,
        "max_rate_cm_per_min": 15,
        "sampling_interval_sec": 30
    })

with open("sensor_registry.json", "w") as f:
    json.dump(sensor_registry, f, indent=2)

# also emit as YAML-ish text (no external yaml dependency needed)
with open("sensor_registry.yaml", "w") as f:
    for s in sensor_registry:
        f.write(f"- sensor_id: {s['sensor_id']}\n")
        f.write(f"  role: {s['role']}\n")
        f.write(f"  latitude: {s['latitude']}\n")
        f.write(f"  longitude: {s['longitude']}\n")
        f.write(f"  reference_height_cm: {s['reference_height_cm']}\n")
        f.write(f"  min_range_cm: {s['min_range_cm']}\n")
        f.write(f"  max_range_cm: {s['max_range_cm']}\n")
        f.write(f"  max_rate_cm_per_min: {s['max_rate_cm_per_min']}\n")
        f.write(f"  sampling_interval_sec: {s['sampling_interval_sec']}\n")

# ---------------------------------------------------------------
# 7. Rainfall storm profile: 3-hour synthetic storm, 5-min steps,
#    uniform across grid with a mild spatial gradient
# ---------------------------------------------------------------
def storm_intensity(t_min):
    # rises, peaks around 90 min, tapers - classic single-peak design storm
    peak = 90
    spread = 45
    return max(0, 28 * math.exp(-((t_min - peak) ** 2) / (2 * spread ** 2)))

rainfall_rows = []
timesteps = list(range(0, 185, 5))
for t in timesteps:
    rate = round(storm_intensity(t) + random.uniform(-1, 1), 2)
    rate = max(0, rate)
    for row in dem_rows[::7]:  # subsample cells for a manageable file size
        spatial_factor = 1.0 + (row["elevation_m"] - 15) * 0.01  # slightly more rain on higher ground (orographic-ish)
        rainfall_rows.append({
            "timestamp_min": t,
            "cell_id": row["cell_id"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "rainfall_rate_mm_hr": round(rate * spatial_factor, 2)
        })

with open("rainfall_storm.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["timestamp_min","cell_id","latitude","longitude","rainfall_rate_mm_hr"])
    w.writeheader()
    w.writerows(rainfall_rows)

# ---------------------------------------------------------------
# 8. Historical flood events (synthetic, styled like real complaint logs)
# ---------------------------------------------------------------
sources = ["Corporation complaint log", "News report (synthetic)", "Citizen report (synthetic)"]
years = [2019, 2020, 2021, 2022, 2023, 2024]
events = []
for i in range(18):
    road = random.choice(roads)
    yr = random.choice(years)
    month = random.choice([6, 7, 8, 9, 10, 11])  # monsoon months
    day = random.randint(1, 28)
    depth = round(random.uniform(8, 45), 1)
    coord = road["geometry"]["coordinates"][len(road["geometry"]["coordinates"])//2]
    events.append({
        "event_id": f"EVT{i+1:03d}",
        "timestamp": f"{yr}-{month:02d}-{day:02d}T{random.randint(6,22):02d}:00:00",
        "latitude": round(coord[1], 6),
        "longitude": round(coord[0], 6),
        "road_id": road["properties"]["road_id"],
        "observed_depth_cm": depth,
        "source": random.choice(sources)
    })

events.sort(key=lambda e: e["timestamp"])
with open("historical_floods.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["event_id","timestamp","latitude","longitude","road_id","observed_depth_cm","source"])
    w.writeheader()
    w.writerows(events)

print("Generated files:")
import os

for fn in sorted(os.listdir(".")):
    if fn != "generate_datasets.py":
        print(" -", fn)
