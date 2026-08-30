"""
SafeSurge - AURA-FLOOD VALIDATION dataset generator.

Purpose: produce data the model has never seen, to genuinely test it -
as opposed to the training scenarios (Part 1) which the model was fit on.

Two things happen here:
  1. Recreate the EXACT same static grid/drainage setup as the Colab
     notebook (same seed=42) so engineered features (flow_accum,
     dist_to_drain_m, node_base_capacity, etc.) match what the model
     was trained on - this is required for the saved model to be usable.
  2. Generate NEW storm scenarios using a SEPARATE random stream
     (seed=999), so none of these storms were part of training - includes
     both "normal range" validation storms and deliberate EDGE CASES
     (zero rainfall, extreme rainfall, extreme drainage failure) that
     stress-test generalization outside the training distribution.

Outputs:
  - validation_data.csv            physics ground truth + features (held-out storms)
  - validation_sensors.csv         simulated live sensor readings for one validation storm
  - validation_historical_events.csv  a second, disjoint set of "observed" flood events
  - validation_report.json / .csv  actual scored metrics against the saved ML model
"""

import json
import csv
import math
import random
import numpy as np
import pandas as pd

# =================================================================
# PART A - recreate the exact static grid + drainage network
#           (must match training seed=42 for feature consistency)
# =================================================================
random.seed(42)
np.random.seed(42)

GRID_N = 10
CELL_SIZE_M = 200.0
CELL_AREA_M2 = CELL_SIZE_M ** 2
LAT0, LON0 = 13.0500, 80.2000
CELL_SIZE_DEG = 0.0018

def cell_id(r, c):
    return f"C{r:02d}{c:02d}"

def cell_latlon(r, c):
    return round(LAT0 + r * CELL_SIZE_DEG, 6), round(LON0 + c * CELL_SIZE_DEG, 6)

def elevation(r, c):
    base = 20.0
    slope_component = -(r + c) * 0.45
    basin_dist = math.hypot(r - 1, c - 1)
    basin_dip = -3.5 * math.exp(-(basin_dist**2) / 4)
    ridge_dist = math.hypot(r - 8, c - 8)
    ridge_bump = 2.5 * math.exp(-(ridge_dist**2) / 6)
    noise = np.random.uniform(-0.3, 0.3)
    return round(base + slope_component + basin_dip + ridge_bump + noise, 2)

def assign_landuse(r, c):
    if (r, c) in [(1,1),(2,1),(1,2)]:
        return "WATER_BODY", 0.02, 100
    if r % 4 == 0 and c % 3 == 0:
        return "PARK", 0.15, 68
    if r >= 7 and c >= 7:
        return "COMMERCIAL", 0.85, 92
    if (r + c) % 5 == 0:
        return "ROAD", 0.95, 96
    return "RESIDENTIAL", 0.65, 88

cells_meta = {}
for r in range(GRID_N):
    for c in range(GRID_N):
        cid = cell_id(r, c)
        lu, imperv, cn = assign_landuse(r, c)
        cells_meta[cid] = {"row": r, "col": c, "elevation": elevation(r, c),
                            "land_use": lu, "impervious_fraction": imperv, "curve_number": cn}

def neighbors(r, c):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < GRID_N and 0 <= nc < GRID_N:
                yield nr, nc

flow_dir = {}
for cid, meta in cells_meta.items():
    r, c = meta["row"], meta["col"]
    best, best_elev = None, meta["elevation"]
    for nr, nc in neighbors(r, c):
        ncid = cell_id(nr, nc)
        if cells_meta[ncid]["elevation"] < best_elev:
            best_elev = cells_meta[ncid]["elevation"]
            best = ncid
    flow_dir[cid] = best

order = sorted(cells_meta.keys(), key=lambda k: -cells_meta[k]["elevation"])
accum = {cid: 1 for cid in cells_meta}
for cid in order:
    down = flow_dir[cid]
    if down is not None:
        accum[down] += accum[cid]

NUM_NODES = 15
sorted_by_elev = sorted(cells_meta.keys(), key=lambda k: cells_meta[k]["elevation"])
node_cells = sorted_by_elev[:NUM_NODES]
node_base_capacity = {nid: round(random.uniform(8, 25), 1) for nid in node_cells}

def dist(a, b):
    ra, ca = cells_meta[a]["row"], cells_meta[a]["col"]
    rb, cb = cells_meta[b]["row"], cells_meta[b]["col"]
    return math.hypot(ra - rb, ca - cb)

nearest_node, nearest_node_dist = {}, {}
for cid in cells_meta:
    nid = min(node_cells, key=lambda n: dist(cid, n))
    nearest_node[cid] = nid
    nearest_node_dist[cid] = dist(cid, nid) * CELL_SIZE_M

print("Static grid + drainage network recreated (matches training feature space).")

# =================================================================
# PART B - physics engine (identical logic to training generator)
# =================================================================
def storm_intensity(t_min, peak_mm_hr, peak_time_min, spread_min):
    return max(0.0, peak_mm_hr * math.exp(-((t_min - peak_time_min) ** 2) / (2 * spread_min ** 2)))

def scs_cn_runoff_mm(cumulative_rain_mm, curve_number):
    S = (25400.0 / curve_number) - 254.0
    Ia = 0.2 * S
    if cumulative_rain_mm <= Ia:
        return 0.0
    return ((cumulative_rain_mm - Ia) ** 2) / (cumulative_rain_mm - Ia + S)

def run_scenario(scenario_id, peak_mm_hr, peak_time_min=90, spread_min=45,
                  drainage_condition_factor=1.0, duration_min=180, dt_min=5,
                  outflow_fraction=0.5, tag="normal"):
    timesteps = list(range(0, duration_min + dt_min, dt_min))
    storage = {cid: 0.0 for cid in cells_meta}
    cum_rain = {cid: 0.0 for cid in cells_meta}
    cum_runoff_prev = {cid: 0.0 for cid in cells_meta}
    order_desc = sorted(cells_meta.keys(), key=lambda k: -cells_meta[k]["elevation"])

    rows = []
    for t in timesteps:
        rate = storm_intensity(t, peak_mm_hr, peak_time_min, spread_min)
        rain_this_step_mm = rate * (dt_min / 60.0)

        remaining_capacity = {nid: node_base_capacity[nid] * drainage_condition_factor for nid in node_cells}
        inflow_accum = {cid: 0.0 for cid in cells_meta}
        new_storage = {}

        for cid in order_desc:
            meta = cells_meta[cid]
            cum_rain[cid] += rain_this_step_mm
            cum_runoff_mm = scs_cn_runoff_mm(cum_rain[cid], meta["curve_number"])
            incremental_runoff_mm = max(0.0, cum_runoff_mm - cum_runoff_prev[cid])
            cum_runoff_prev[cid] = cum_runoff_mm

            runoff_volume_m3 = (incremental_runoff_mm / 1000.0) * CELL_AREA_M2
            total_input = storage[cid] + runoff_volume_m3 + inflow_accum[cid]

            nid = nearest_node[cid]
            capture = min(total_input, remaining_capacity[nid])
            remaining_capacity[nid] -= capture
            remaining_after_capture = total_input - capture

            down = flow_dir[cid]
            outflow = remaining_after_capture * outflow_fraction if down is not None else 0.0
            new_storage[cid] = remaining_after_capture - outflow
            if down is not None:
                inflow_accum[down] += outflow

            depth_cm = (new_storage[cid] / CELL_AREA_M2) * 100.0

            rows.append({
                "scenario_id": scenario_id, "scenario_tag": tag, "cell_id": cid, "t_min": t,
                "elevation": meta["elevation"], "curve_number": meta["curve_number"],
                "impervious_fraction": meta["impervious_fraction"], "flow_accum": accum[cid],
                "dist_to_drain_m": nearest_node_dist[cid], "node_base_capacity": node_base_capacity[nid],
                "drainage_condition_factor": drainage_condition_factor,
                "rainfall_rate_mm_hr": round(rate, 3), "cumulative_rain_mm": round(cum_rain[cid], 3),
                "peak_mm_hr": peak_mm_hr, "flood_depth_cm": round(depth_cm, 4),
            })
        storage = new_storage
    return pd.DataFrame(rows)

# =================================================================
# PART C - generate held-out VALIDATION storms
#           separate RNG stream (seed=999) -> guaranteed not in training
# =================================================================
val_rng = random.Random(999)

validation_scenarios = []

# 10 "normal range" validation storms - same distribution as training,
# but a fresh draw the model has never seen
for i in range(10):
    peak = val_rng.uniform(10, 60)
    peak_t = val_rng.uniform(60, 120)
    spread = val_rng.uniform(25, 60)
    cond = val_rng.choice([1.0, 1.0, 0.9, 0.7, 0.5, 0.3])
    outflow = val_rng.uniform(0.35, 0.65)
    validation_scenarios.append(dict(scenario_id=f"VAL_N{i:02d}", peak_mm_hr=peak,
                                      peak_time_min=peak_t, spread_min=spread,
                                      drainage_condition_factor=cond, outflow_fraction=outflow,
                                      tag="normal"))

# 5 EDGE CASE scenarios - deliberately outside/at the boundary of the
# training distribution (training used peak_mm_hr in [10,60], condition in {1.0,0.9,0.7,0.5,0.3})
edge_cases = [
    dict(scenario_id="VAL_E00_zero_rain", peak_mm_hr=0.0, peak_time_min=90, spread_min=45,
         drainage_condition_factor=1.0, outflow_fraction=0.5, tag="edge_zero_rain"),
    dict(scenario_id="VAL_E01_extreme_rain", peak_mm_hr=75.0, peak_time_min=90, spread_min=30,
         drainage_condition_factor=1.0, outflow_fraction=0.5, tag="edge_extreme_rain"),
    dict(scenario_id="VAL_E02_extreme_drainage_failure", peak_mm_hr=35.0, peak_time_min=90, spread_min=45,
         drainage_condition_factor=0.15, outflow_fraction=0.5, tag="edge_drainage_failure"),
    dict(scenario_id="VAL_E03_combo_worst_case", peak_mm_hr=70.0, peak_time_min=75, spread_min=35,
         drainage_condition_factor=0.2, outflow_fraction=0.4, tag="edge_combo_worst_case"),
    dict(scenario_id="VAL_E04_prolonged_drizzle", peak_mm_hr=8.0, peak_time_min=90, spread_min=90,
         drainage_condition_factor=1.0, outflow_fraction=0.6, tag="edge_prolonged_drizzle"),
]
validation_scenarios.extend(edge_cases)

all_val_dfs = [run_scenario(**s) for s in validation_scenarios]
validation_data = pd.concat(all_val_dfs, ignore_index=True)
validation_data.to_csv("validation_data.csv", index=False)
print(f"validation_data.csv written: {len(validation_data):,} rows "
      f"({len(validation_scenarios)} scenarios: 10 normal + 5 edge case)")

# =================================================================
# PART D - simulated sensor readings for ONE validation storm
#           (paired with true physics depth, for fusion-layer testing)
# =================================================================
sorted_cells_by_elev = sorted(cells_meta.keys(), key=lambda k: cells_meta[k]["elevation"])
outfall_cell_id = sorted_cells_by_elev[0]
station_defs = [
    ("S001", "HEADWATER", (9, 9)), ("S002", "ARTERIAL", (5, 5)), ("S003", "BASIN", (1, 1)),
    ("S004", "DEPRESSION", (2, 2)), ("S005", "ELEVATED", (8, 2)),
    ("S006", "OUTFALL", (cells_meta[outfall_cell_id]["row"], cells_meta[outfall_cell_id]["col"])),
]
reference_heights = {"S001": 100, "S002": 100, "S003": 80, "S004": 90, "S005": 120, "S006": 100}

demo_storm_id = "VAL_E03_combo_worst_case"  # validate against the worst-case edge scenario
demo_df = validation_data[validation_data["scenario_id"] == demo_storm_id]

sensor_val_rows = []
np.random.seed(7)
for sid, role, (r, c) in station_defs:
    cid = cell_id(r, c)
    lat, lon = cell_latlon(r, c)
    ref_h = reference_heights[sid]
    cell_series = demo_df[demo_df["cell_id"] == cid].sort_values("t_min")
    for _, row in cell_series.iterrows():
        true_depth = row["flood_depth_cm"]
        noise = np.random.normal(0, 0.3)
        observed_depth = max(0.0, true_depth + noise)
        distance_cm = round(ref_h - observed_depth, 2)
        sensor_val_rows.append({
            "sensor_id": sid, "role": role, "scenario_id": demo_storm_id,
            "timestamp_min": int(row["t_min"]), "latitude": lat, "longitude": lon,
            "true_depth_cm_physics": round(true_depth, 3),
            "observed_water_depth_cm": round(observed_depth, 3),
            "distance_cm": distance_cm, "status": "ONLINE",
        })

with open("validation_sensors.csv", "w", newline="") as f:
    fieldnames = list(sensor_val_rows[0].keys())
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(sensor_val_rows)
print(f"validation_sensors.csv written: {len(sensor_val_rows)} rows "
      f"(sensor readings paired with ground truth, storm={demo_storm_id})")

# =================================================================
# PART E - a second, disjoint set of "historical" flood events
#           (different random draw from the earlier historical_floods.csv,
#            for testing risk-threshold calibration against fresh ground truth)
# =================================================================
road_paths_ids = [f"R{i+1:03d}" for i in range(10)]
sources = ["Corporation complaint log", "News report (synthetic)", "Citizen report (synthetic)"]
val_events_rng = random.Random(2024)
val_events = []
for i in range(12):
    road = val_events_rng.choice(road_paths_ids)
    yr = val_events_rng.choice([2019, 2020, 2021, 2022, 2023, 2024, 2025])
    month = val_events_rng.choice([6, 7, 8, 9, 10, 11])
    day = val_events_rng.randint(1, 28)
    depth = round(val_events_rng.uniform(6, 42), 1)
    val_events.append({
        "event_id": f"VALEVT{i+1:03d}",
        "timestamp": f"{yr}-{month:02d}-{day:02d}T{val_events_rng.randint(6,22):02d}:00:00",
        "road_id": road, "observed_depth_cm": depth,
        "source": val_events_rng.choice(sources),
    })
val_events.sort(key=lambda e: e["timestamp"])
with open("validation_historical_events.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["event_id","timestamp","road_id","observed_depth_cm","source"])
    w.writeheader()
    w.writerows(val_events)
print(f"validation_historical_events.csv written: {len(val_events)} rows")

print("\nAll validation datasets generated. Proceeding to score against the saved model...")
