exec(open("part2_setup.py").read())

import rasterio
from rasterio.transform import from_origin

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

# simplified per-cell local depth (no cross-cell routing needed here - just
# enough physical grounding that sensor readings track the storm realistically)
def local_depth_series(cid):
    cn = LAND_USE_CN[landuse_lookup[cid]]
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
        # local drainage capture: fixed small capacity representative of nearby inlet
        capture = min(storage_m3 + runoff_m3, 4.0)
        storage_m3 = max(0.0, storage_m3 + runoff_m3 - capture)
        depths[t] = (storage_m3 / CELL_AREA_M2) * 100.0  # cm
    return depths

sensor_rows = []
for sid, role, (r, c) in station_defs:
    cid = cell_id(r, c)
    lat, lon = cell_latlon(r, c)
    ref_h = reference_heights[sid]
    depths = local_depth_series(cid)

    battery = 100.0
    status = "ONLINE"
    dropout_start, dropout_end = None, None
    if sid == "S003":
        dropout_start, dropout_end = 100, 140   # simulates comms failure mid-storm (Fault Test A)
    spike_time = 95 if sid == "S005" else None   # simulates ultrasonic spike (Fault Test B)

    for t in timesteps:
        true_depth_cm = depths[t]
        noise = np.random.normal(0, 0.3)
        reading_depth_cm = max(0.0, true_depth_cm + noise)
        distance_cm = round(ref_h - reading_depth_cm, 2)

        # dropout window
        if dropout_start is not None and dropout_start <= t <= dropout_end:
            if t < dropout_start + 15:
                status = "STALE"
            else:
                status = "OFFLINE"
            distance_cm = None
            reading_depth_cm = None
        else:
            status = "ONLINE"

        # spike injection (single bad reading, physically implausible jump)
        if spike_time is not None and t == spike_time:
            distance_cm = round(ref_h - 90, 2)  # implausible 90cm depth reading
            reading_depth_cm = 90.0
            status = "ONLINE"  # raw reading still comes in; validation layer should flag it, not the sensor itself

        battery = max(2.0, battery - random.uniform(0.05, 0.15))
        rssi = round(random.uniform(-78, -55), 1)

        sensor_rows.append({
            "sensor_id": sid,
            "role": role,
            "timestamp_min": t,
            "latitude": lat,
            "longitude": lon,
            "distance_cm": distance_cm,
            "water_depth_cm": round(reading_depth_cm, 2) if reading_depth_cm is not None else None,
            "battery_pct": round(battery, 1),
            "rssi_dbm": rssi,
            "status": status,
            "is_injected_spike": (spike_time is not None and t == spike_time),
            "is_injected_dropout": (dropout_start is not None and dropout_start <= t <= dropout_end),
        })

with open("sensors.csv", "w", newline="") as f:
    fieldnames = list(sensor_rows[0].keys())
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(sensor_rows)

print(f"sensors.csv written: {len(sensor_rows)} rows "
      f"({len(station_defs)} sensors x {len(timesteps)} timesteps)")

# =================================================================
# 2. SOIL / HYDROLOGY (soil_hydrology.csv)
# =================================================================
SOIL_GROUP_PROFILES = {
    # (soil_group, typical infiltration rate mm/hr) - standard NRCS/SCS ranges
    "A": (7.6, 11.4),   # sandy, high infiltration
    "B": (3.8, 7.6),
    "C": (1.3, 3.8),
    "D": (0.0, 1.3),    # clay/impervious, low infiltration
}

def assign_soil_group(land_use):
    if land_use == "WATER_BODY":
        return "D"
    if land_use == "PARK":
        return random.choice(["A", "B"])
    if land_use == "RESIDENTIAL":
        return random.choice(["B", "C"])
    # ROAD, COMMERCIAL - heavily compacted/impervious substrate
    return random.choice(["C", "D"])

soil_rows = []
for row in dem_rows:
    cid = row["cell_id"]
    lu = landuse_lookup[cid]
    sg = assign_soil_group(lu)
    lo, hi = SOIL_GROUP_PROFILES[sg]
    infiltration = round(random.uniform(lo, hi), 2)
    soil_rows.append({
        "cell_id": cid,
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "soil_group": sg,
        "infiltration_rate_mm_hr": infiltration,
        "land_use": lu,
    })

with open("soil_hydrology.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["cell_id","latitude","longitude","soil_group","infiltration_rate_mm_hr","land_use"])
    w.writeheader()
    w.writerows(soil_rows)

print(f"soil_hydrology.csv written: {len(soil_rows)} rows")

# =================================================================
# 3. WEATHER CONTEXT (weather_context.csv) - 2 synthetic AWS stations
# =================================================================
aws_stations = [
    ("AWS01", cell_latlon(9, 0)),
    ("AWS02", cell_latlon(0, 9)),
]

weather_rows = []
for station_id, (lat, lon) in aws_stations:
    base_temp = random.uniform(27, 30)
    base_pressure = random.uniform(1006, 1010)
    for t in timesteps:
        rate = storm_intensity(t)
        storm_factor = min(1.0, rate / 28.0)
        temp_c = round(base_temp - storm_factor * random.uniform(1.5, 3.0) + np.random.normal(0, 0.2), 2)
        humidity_pct = round(min(99, 65 + storm_factor * 30 + np.random.normal(0, 2)), 1)
        wind_speed_kmph = round(8 + storm_factor * random.uniform(15, 35) + np.random.normal(0, 2), 1)
        wind_dir_deg = round(random.uniform(0, 360), 1)
        pressure_hpa = round(base_pressure - storm_factor * random.uniform(2, 5), 2)
        weather_rows.append({
            "station_id": station_id,
            "timestamp_min": t,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": temp_c,
            "humidity_pct": humidity_pct,
            "wind_speed_kmph": wind_speed_kmph,
            "wind_dir_deg": wind_dir_deg,
            "pressure_hpa": pressure_hpa,
        })

with open("weather_context.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["station_id","timestamp_min","latitude","longitude",
                                       "temperature_c","humidity_pct","wind_speed_kmph",
                                       "wind_dir_deg","pressure_hpa"])
    w.writeheader()
    w.writerows(weather_rows)

print(f"weather_context.csv written: {len(weather_rows)} rows")

# =================================================================
# 4. REAL DEM RASTER (dem.tif) - GeoTIFF, not just a CSV proxy
# =================================================================
elev_grid = np.zeros((GRID_N, GRID_N), dtype=np.float32)
for row in dem_rows:
    # raster row 0 = north (top); our r=0 is south, so flip
    raster_row = GRID_N - 1 - row["row"]
    elev_grid[raster_row, row["col"]] = row["elevation_m"]

# pixel size in degrees, origin = top-left corner (north-west)
top_left_lon = LON0 - CELL_SIZE_DEG / 2
top_left_lat = LAT0 + (GRID_N - 0.5) * CELL_SIZE_DEG
transform = from_origin(top_left_lon, top_left_lat, CELL_SIZE_DEG, CELL_SIZE_DEG)

with rasterio.open(
    "dem.tif", "w",
    driver="GTiff",
    height=GRID_N, width=GRID_N,
    count=1, dtype=elev_grid.dtype,
    crs="EPSG:4326",
    transform=transform,
    nodata=-9999,
) as dst:
    dst.write(elev_grid, 1)

print("dem.tif written (GeoTIFF, EPSG:4326,", f"{GRID_N}x{GRID_N} px)")

# =================================================================
# 5. FAULT INJECTION SCENARIOS (fault_injection_scenarios.csv)
#    Structured version of spec Section 35, cross-referenced to the
#    actual injected events in sensors.csv where applicable.
# =================================================================
fault_scenarios = [
    {
        "test_id": "A", "name": "Sensor failure",
        "trigger_condition": "S003 communication lost from t=100min to t=140min",
        "injected_in": "sensors.csv (status=STALE then OFFLINE, sensor_id=S003)",
        "expected_behavior": "Physics model continues running; confidence score decreases due to reduced observational coverage",
    },
    {
        "test_id": "B", "name": "Sensor spike",
        "trigger_condition": "S005 reports an implausible 90cm depth jump at t=95min",
        "injected_in": "sensors.csv (is_injected_spike=True, sensor_id=S005, t=95)",
        "expected_behavior": "Rate-of-rise validation rejects the reading; previous valid state is retained",
    },
    {
        "test_id": "C", "name": "Drainage capacity reduction",
        "trigger_condition": "Drainage condition_factor reduced from 1.0 to 0.3 on affected edges",
        "injected_in": "drainage_edges.geojson (condition_factor field, some edges already set as low as 0.3)",
        "expected_behavior": "Effective drainage capacity drops; surface storage increases; flood depth increases",
    },
    {
        "test_id": "D", "name": "Extreme rainfall",
        "trigger_condition": "Storm peak intensity set to 60mm/hr (vs. 28mm/hr baseline)",
        "injected_in": "Not pre-generated - run the Colab physics engine with peak_mm_hr=60",
        "expected_behavior": "Runoff increases; flood depth increases; road risk escalates to HIGH/UNSAFE",
    },
    {
        "test_id": "E", "name": "No rainfall",
        "trigger_condition": "Storm peak intensity set to 0mm/hr",
        "injected_in": "Not pre-generated - run the Colab physics engine with peak_mm_hr=0",
        "expected_behavior": "System reports 'forecast unavailable' rather than a fabricated non-zero prediction",
    },
    {
        "test_id": "F", "name": "No sensor coverage",
        "trigger_condition": "All 6 sensors set to OFFLINE simultaneously",
        "injected_in": "Not pre-generated - filter sensors.csv to status=OFFLINE for all sensor_ids",
        "expected_behavior": "Physics model continues; confidence score drops sharply (coverage term -> 0)",
    },
    {
        "test_id": "G", "name": "Flooded shortest route",
        "trigger_condition": "Road R006 forced to UNSAFE (depth >= 25cm) at t=100min",
        "injected_in": "historical_floods.csv includes an R006 event at 18.5cm as a reference point; force to 25+cm for the live demo",
        "expected_behavior": "Router assigns cost=infinity to R006's edge; shortest-path alternative is selected instead",
    },
]

with open("fault_injection_scenarios.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["test_id","name","trigger_condition","injected_in","expected_behavior"])
    w.writeheader()
    w.writerows(fault_scenarios)

print(f"fault_injection_scenarios.csv written: {len(fault_scenarios)} rows")

print("\nAll Part 2 datasets generated successfully.")
