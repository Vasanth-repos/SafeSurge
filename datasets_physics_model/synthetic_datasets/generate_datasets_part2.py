"""
SafeSurge - AURA-FLOOD synthetic dataset generator (Part 2)
Generates:
1. sensors.csv
2. soil_hydrology.csv
3. weather_context.csv
4. dem.tif (if rasterio available)
5. fault_injection_scenarios.csv
"""

import os
import csv
import json
import math
import random
import numpy as np

try:
    import rasterio
    from rasterio.transform import from_origin
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

GRID_N = 10
LAT0, LON0 = 13.0500, 80.2000     # bottom-left corner
CELL_SIZE_DEG = 0.0018             # ~200m per cell

def cell_id(r, c):
    return f"C{r:02d}{c:02d}"

def cell_latlon(r, c):
    lat = LAT0 + r * CELL_SIZE_DEG
    lon = LON0 + c * CELL_SIZE_DEG
    return round(lat, 6), round(lon, 6)

station_defs = [
    ("S001", "C0101", 1.8),
    ("S002", "C0108", 2.0),
    ("S003", "C0505", 2.2),
    ("S004", "C0802", 1.9),
    ("S005", "C0808", 2.1),
    ("S006", "C0304", 2.0),
]
reference_heights = {s[0]: s[2] for s in station_defs}

base_dir = os.path.dirname(os.path.abspath(__file__))

landuse_lookup = {}
lu_path = os.path.join(base_dir, "landuse.geojson")
if os.path.exists(lu_path):
    with open(lu_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for feat in data.get("features", []):
            cid = feat.get("properties", {}).get("cell_id")
            lu = feat.get("properties", {}).get("land_use")
            if cid and lu:
                landuse_lookup[cid] = lu
else:
    for r in range(GRID_N):
        for c in range(GRID_N):
            landuse_lookup[cell_id(r, c)] = "RESIDENTIAL"

dem_rows = []
dem_path = os.path.join(base_dir, "dem.csv")
if os.path.exists(dem_path):
    with open(dem_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dem_rows.append({
                "cell_id": row["cell_id"],
                "row": int(row["row"]),
                "col": int(row["col"]),
                "elevation_m": float(row["elevation_m"]),
            })
else:
    for r in range(GRID_N):
        for c in range(GRID_N):
            dem_rows.append({
                "cell_id": cell_id(r, c),
                "row": r,
                "col": c,
                "elevation_m": round(20.0 - (r + c) * 0.45, 2),
            })


# =================================================================
# 1. SENSOR TELEMETRY (sensors.csv) - live readings over the storm
#    timeline, derived from a simplified physics run at each sensor
#    cell, with injected spike + dropout for fault-injection testing.
# =================================================================

def storm_intensity(t_min, peak_mm_hr=28, peak_time_min=90, spread_min=45):
    return max(0.0, peak_mm_hr * math.exp(-((t_min - peak_time_min) ** 2) / (2 * spread_min ** 2)))

def scs_cn_runoff_mm(cumulative_rain_mm, curve_number):
    S = (25400.0 / curve_number) - 254.0
    Ia = 0.2 * S
    if cumulative_rain_mm <= Ia:
        return 0.0
    return ((cumulative_rain_mm - Ia) ** 2) / (cumulative_rain_mm - Ia + S)

LAND_USE_CN = {"ROAD": 96, "RESIDENTIAL": 88, "COMMERCIAL": 92, "PARK": 68, "WATER_BODY": 100}
CELL_AREA_M2 = 200.0 * 200.0

timesteps = list(range(0, 185, 5))

def local_depth_series(cid):
    cn = LAND_USE_CN.get(landuse_lookup.get(cid, "RESIDENTIAL"), 88)
    cum_rain = 0.0
    cum_runoff_prev = 0.0
    storage_m3 = 0.0
    depths = {}
    for t in timesteps:
        rate = storm_intensity(t)
        cum_rain += rate * (5 / 60.0)
        cum_runoff = scs_cn_runoff_mm(cum_rain, cn)
        incremental_mm = max(0.0, cum_runoff - cum_runoff_prev)
        cum_runoff_prev = cum_runoff
        runoff_m3 = (incremental_mm / 1000.0) * CELL_AREA_M2
        capture = min(storage_m3 + runoff_m3, 4.0)
        storage_m3 = max(0.0, storage_m3 + runoff_m3 - capture)
        depths[t] = (storage_m3 / CELL_AREA_M2) * 100.0  # cm
    return depths

sensor_depth_series = {}
for sid, cid, ref_h in station_defs:
    r, c = int(cid[1:3]), int(cid[3:5])
    lat, lon = cell_latlon(r, c)
    sensor_depth_series[sid] = {
        "cell_id": cid, "lat": lat, "lon": lon,
        "ref_h_m": ref_h,
        "depths": local_depth_series(cid)
    }

sensor_rows = []
for sid, info in sensor_depth_series.items():
    ref_h_cm = info["ref_h_m"] * 100.0
    for t in timesteps:
        true_depth_cm = info["depths"][t]
        noise = np.random.normal(0, 0.4)
        noisy_depth = max(0.0, true_depth_cm + noise)

        distance_cm = max(5.0, ref_h_cm - noisy_depth)
        status = "OK"

        if sid == "S001" and 75 <= t <= 85:
            distance_cm = max(5.0, distance_cm - 45.0)
            noisy_depth = ref_h_cm - distance_cm
            status = "SPIKE"

        if sid == "S005" and 100 <= t <= 125:
            distance_cm = None
            noisy_depth = None
            status = "OFFLINE"

        battery = round(max(3.0, 4.15 - (t / 180.0) * 0.12 + random.uniform(-0.02, 0.02)), 2)
        rssi = random.randint(-85, -62) if status != "OFFLINE" else -110

        sensor_rows.append({
            "sensor_id": sid,
            "timestamp_min": t,
            "latitude": info["lat"],
            "longitude": info["lon"],
            "distance_cm": round(distance_cm, 1) if distance_cm is not None else "",
            "water_depth_cm": round(noisy_depth, 1) if noisy_depth is not None else "",
            "status": status,
            "battery_v": battery,
            "rssi_dbm": rssi
        })

sensors_csv_path = os.path.join(base_dir, "sensors.csv")
with open(sensors_csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "sensor_id", "timestamp_min", "latitude", "longitude",
        "distance_cm", "water_depth_cm", "status", "battery_v", "rssi_dbm"
    ])
    w.writeheader()
    w.writerows(sensor_rows)

print(f"sensors.csv written: {len(sensor_rows)} rows ({len(station_defs)} sensors x {len(timesteps)} steps)")


# =================================================================
# 2. SOIL & HYDROLOGY PARAMETERS (soil_hydrology.csv)
# =================================================================

HSG_DEFAULTS = {
    "WATER_BODY":  ("A", 100, 25.0, 0.45, 0.10),
    "PARK":        ("B",  68, 12.0, 0.38, 0.15),
    "RESIDENTIAL": ("C",  88,  4.5, 0.32, 0.20),
    "COMMERCIAL":  ("D",  92,  1.5, 0.28, 0.25),
    "ROAD":        ("D",  96,  0.5, 0.25, 0.25),
}

soil_rows = []
for r in range(GRID_N):
    for c in range(GRID_N):
        cid = cell_id(r, c)
        lat, lon = cell_latlon(r, c)
        elev_record = next(row for row in dem_rows if row["cell_id"] == cid)
        elev = elev_record["elevation_m"]
        lu = landuse_lookup[cid]
        hsg, cn, ksat_base, porosity, theta_r = HSG_DEFAULTS[lu]

        ksat = round(max(0.1, ksat_base + random.uniform(-0.5, 0.5)), 2)
        slope_pct = round(abs(random.gauss(1.2, 0.4)), 2)
        depth_to_bedrock_m = round(random.uniform(1.2, 3.5), 2)
        initial_moisture_fraction = 0.28

        soil_rows.append({
            "cell_id": cid, "latitude": lat, "longitude": lon,
            "elevation_m": elev, "land_use": lu,
            "hydrologic_soil_group": hsg,
            "curve_number": cn,
            "saturated_conductivity_mm_hr": ksat,
            "porosity_fraction": porosity,
            "residual_moisture_fraction": theta_r,
            "initial_moisture_fraction": initial_moisture_fraction,
            "depth_to_bedrock_m": depth_to_bedrock_m,
            "slope_percent": slope_pct
        })

soil_csv_path = os.path.join(base_dir, "soil_hydrology.csv")
with open(soil_csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "cell_id", "latitude", "longitude", "elevation_m", "land_use",
        "hydrologic_soil_group", "curve_number",
        "saturated_conductivity_mm_hr", "porosity_fraction",
        "residual_moisture_fraction", "initial_moisture_fraction",
        "depth_to_bedrock_m", "slope_percent"
    ])
    w.writeheader()
    w.writerows(soil_rows)

print(f"soil_hydrology.csv written: {len(soil_rows)} rows (1 per cell)")


# =================================================================
# 3. WEATHER CONTEXT (weather_context.csv)
# =================================================================

weather_stations = [
    ("WX_NORTH", round(LAT0 + 8.5 * CELL_SIZE_DEG, 6), round(LON0 + 5.0 * CELL_SIZE_DEG, 6)),
    ("WX_SOUTH", round(LAT0 + 1.5 * CELL_SIZE_DEG, 6), round(LON0 + 5.0 * CELL_SIZE_DEG, 6)),
]

weather_rows = []
for wx_id, lat, lon in weather_stations:
    for t in timesteps:
        storm_frac = storm_intensity(t) / 28.0
        temp_c = round(29.5 - 3.5 * storm_frac + random.uniform(-0.3, 0.3), 1)
        humidity_pct = round(min(100.0, 78.0 + 20.0 * storm_frac + random.uniform(-1, 1)), 1)
        wind_speed_kmph = round(12.0 + 22.0 * storm_frac + np.random.normal(0, 2), 1)
        wind_speed_kmph = max(2.0, wind_speed_kmph)
        wind_dir_deg = int((210 + 25 * storm_frac + np.random.normal(0, 8)) % 360)
        pressure_hpa = round(1008.0 - 4.5 * storm_frac + np.random.normal(0, 0.4), 1)

        weather_rows.append({
            "station_id": wx_id,
            "timestamp_min": t,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": temp_c,
            "humidity_pct": humidity_pct,
            "wind_speed_kmph": wind_speed_kmph,
            "wind_dir_deg": wind_dir_deg,
            "pressure_hpa": pressure_hpa,
        })

weather_csv_path = os.path.join(base_dir, "weather_context.csv")
with open(weather_csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "station_id", "timestamp_min", "latitude", "longitude",
        "temperature_c", "humidity_pct", "wind_speed_kmph",
        "wind_dir_deg", "pressure_hpa"
    ])
    w.writeheader()
    w.writerows(weather_rows)

print(f"weather_context.csv written: {len(weather_rows)} rows")


# =================================================================
# 4. REAL DEM RASTER (dem.tif) - GeoTIFF
# =================================================================

if HAS_RASTERIO:
    elev_grid = np.zeros((GRID_N, GRID_N), dtype=np.float32)
    for row in dem_rows:
        raster_row = GRID_N - 1 - row["row"]
        elev_grid[raster_row, row["col"]] = row["elevation_m"]

    top_left_lon = LON0 - CELL_SIZE_DEG / 2
    top_left_lat = LAT0 + (GRID_N - 0.5) * CELL_SIZE_DEG
    transform = from_origin(top_left_lon, top_left_lat, CELL_SIZE_DEG, CELL_SIZE_DEG)

    dem_tif_path = os.path.join(base_dir, "dem.tif")
    with rasterio.open(
        dem_tif_path, "w",
        driver="GTiff",
        height=GRID_N, width=GRID_N,
        count=1, dtype=elev_grid.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999,
    ) as dst:
        dst.write(elev_grid, 1)

    print("dem.tif written (GeoTIFF, EPSG:4326,", f"{GRID_N}x{GRID_N} px)")
else:
    print("rasterio not installed; skipping dem.tif generation")


# =================================================================
# 5. FAULT INJECTION SCENARIOS (fault_injection_scenarios.csv)
# =================================================================

faults = [
    {
        "fault_id": "FLT01",
        "target_type": "sensor",
        "target_id": "S001",
        "fault_type": "spike_anomaly",
        "start_time_min": 75,
        "end_time_min": 85,
        "severity": "critical",
        "injected_effect": "distance_cm dropped by 45cm -> false 45cm water depth surge",
        "ground_truth_status": "NORMAL_WATER_LEVEL_MISREPORTED",
        "expected_system_response": "Rate-of-rise filter rejects spike; flags S001 as DEGRADED; preserves prior flood estimate"
    },
    {
        "fault_id": "FLT02",
        "target_type": "sensor",
        "target_id": "S005",
        "fault_type": "signal_dropout",
        "start_time_min": 100,
        "end_time_min": 125,
        "severity": "high",
        "injected_effect": "telemetry completely lost -> null reading, status OFFLINE",
        "ground_truth_status": "ACTUALLY_FLOODING_18CM",
        "expected_system_response": "Sensor health engine marks S005 OFFLINE; falls back to spatial interpolation from S003 and physics model"
    },
    {
        "fault_id": "FLT03",
        "target_type": "drainage_edge",
        "target_id": "E04",
        "fault_type": "debris_blockage",
        "start_time_min": 60,
        "end_time_min": 180,
        "severity": "critical",
        "injected_effect": "culvert capacity degraded by 85% (condition_factor drops 1.0 -> 0.15)",
        "ground_truth_status": "BLOCKAGE_ACTIVE",
        "expected_system_response": "Physics engine detects surcharge at N04; flags localized ponding on C0304; dynamic routing diverts traffic"
    },
    {
        "fault_id": "FLT04",
        "target_type": "rainfall_feed",
        "target_id": "RADAR_PRIMARY",
        "fault_type": "radar_blackout",
        "start_time_min": 45,
        "end_time_min": 70,
        "severity": "high",
        "injected_effect": "rainfall_rate_mm_hr set to 0 across all cells during peak build-up",
        "ground_truth_status": "STORM_ACTIVE_22MM_HR",
        "expected_system_response": "Ground sensor discrepancy engine catches water rise with zero reported rain; switches to rain-gauge fallback"
    },
    {
        "fault_id": "FLT05",
        "target_type": "sensor",
        "target_id": "S003",
        "fault_type": "calibration_drift",
        "start_time_min": 30,
        "end_time_min": 180,
        "severity": "medium",
        "injected_effect": "+0.15 cm/min gradual drift (uncalibrated sensor creep)",
        "ground_truth_status": "DRIFTING",
        "expected_system_response": "Kalman-filter innovation test flags persistent positive bias; schedules maintenance alert"
    }
]

faults_csv_path = os.path.join(base_dir, "fault_injection_scenarios.csv")
with open(faults_csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "fault_id", "target_type", "target_id", "fault_type",
        "start_time_min", "end_time_min", "severity",
        "injected_effect", "ground_truth_status", "expected_system_response"
    ])
    w.writeheader()
    w.writerows(faults)

print(f"fault_injection_scenarios.csv written: {len(faults)} scenarios")
print("\nSynthetic Part 2 generation complete.")
