# Urban Flood Nowcasting & Response System — Implementation Plan

**Status:** Architecture locked. This is the build specification.
**Scope:** 36-hour hackathon MVP, small demo catchment, replay-first, hardware optional.

---

## 0. Prototype Assumptions (state these up front, always)

- Rainfall is provided through replay, not a live radar feed.
- SCS-CN is a coarse per-timestep runoff approximation (cumulative-P/cumulative-Q method), not a calibrated hydrological model.
- Antecedent moisture condition is fixed for the scenario.
- D8 gives flow direction only; a slope-weighted fraction rule approximates transport.
- Grid-cell storage approximates flood accumulation, not a hydraulic solver.
- Drainage capacity is a simplified capacity-factor model; blockage = reduced effective capacity.
- CN values are prototype assumptions from land-use classification, not locally calibrated.
- Sparse sensors do not provide complete spatial ground truth; unsensed areas rely on spatial bias propagation.
- Predicted road depth is interpolated from nearby grid cells, not a road-specific hydraulic model.
- Validation is pipeline/consistency-based (mass conservation, fault injection), not field accuracy — field accuracy is future work.

---

## 1. Default Parameters (pin these at hour 0 — do not leave symbolic)

| Parameter | Symbol | Default | Notes |
|---|---|---|---|
| Timestep | Δt | 60 s | Reduce if instability observed |
| Max routing fraction | f_max | 0.5 | Cap on fraction of storage leaving per timestep |
| Routing coefficient | k | 0.1 | Tune empirically against demo catchment |
| Bias correction smoothing | α | 0.3 | Exponential weight on new error |
| Confidence weight — coverage | w_c | 0.4 | |
| Confidence weight — freshness | w_f | 0.3 | |
| Confidence weight — agreement | w_a | 0.3 | |
| Agreement window | N | 10 timesteps | ~10 min at Δt=60s |
| Sensor rate-of-rise limit | r_critical | 5 cm/min | Reject/flag above this |
| Sensor stale threshold | — | 3 missed heartbeats | → STALE state |
| Sensor offline threshold | — | 6 missed heartbeats | → OFFLINE state |
| Capacity factor levels | F_t | 1.00 / 0.80 / 0.60 / 0.30 | Normal / minor / partial / severe |
| Grid cell size | — | 10 m × 10 m | Adjust to DEM/venue availability |

Change these in one shared config file (`config/defaults.yaml`) — every module reads from it, nobody hardcodes.

---

## 2. Repository Structure

```
urban-flood-nowcast/
├── config/
│   └── defaults.yaml
├── backend/
│   ├── api/                  # FastAPI routers
│   ├── models/                # Pydantic schemas
│   ├── services/
│   └── database/               # SQLAlchemy models, migrations
├── flood_engine/
│   ├── rainfall.py
│   ├── runoff.py
│   ├── dem.py                 # pit-fill + D8
│   ├── routing.py             # slope-weighted fraction routing
│   ├── drainage.py            # graph + dynamic capacity
│   ├── storage.py             # cell water balance
│   └── conservation.py        # mass balance diagnostic
├── sensor/
│   ├── validation.py          # range/rate/heartbeat checks
│   ├── fusion.py               # bias correction + spatial propagation
│   ├── anomaly.py
│   └── health.py
├── routing/
│   ├── road_graph.py
│   └── safe_route.py
├── replay/
│   ├── rainfall/               # scripted storm CSV/JSON
│   └── sensors/                # scripted sensor sequences
├── frontend/
│   ├── map/
│   ├── dashboard/
│   └── routing/
├── tests/
│   ├── test_conservation.py
│   ├── test_sensor_validation.py
│   ├── test_fusion_convergence.py
│   ├── test_degraded_mode.py
│   ├── test_routing_avoidance.py
│   └── test_end_to_end_replay.py
├── firmware/                   # ESP32
└── docs/
    ├── architecture.md
    ├── assumptions.md
    └── api_contracts.md
```

---

## 3. Database Schema (PostgreSQL/PostGIS)

```sql
CREATE TABLE sensor (
    id SERIAL PRIMARY KEY,
    name TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    node_id INTEGER REFERENCES drainage_node(id),
    sensor_type TEXT,              -- 'ultrasonic' | 'float'
    installation_height_cm DOUBLE PRECISION,
    status TEXT DEFAULT 'ONLINE',  -- ONLINE|STALE|OFFLINE|INVALID|CALIBRATION
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE sensor_reading (
    id SERIAL PRIMARY KEY,
    sensor_id INTEGER REFERENCES sensor(id),
    ts TIMESTAMP,
    water_level_cm DOUBLE PRECISION,
    float_state BOOLEAN,
    battery INTEGER,
    signal_quality DOUBLE PRECISION,
    quality_flag TEXT,             -- VALID|INVALID_SPIKE|STALE|MISSING
    heartbeat BOOLEAN
);

CREATE TABLE rainfall_grid (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP,
    cell_id INTEGER,
    rainfall_mm DOUBLE PRECISION,
    forecast_horizon_min INTEGER,
    source TEXT                    -- 'replay' | 'live'
);

CREATE TABLE drainage_node (
    id SERIAL PRIMARY KEY,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    node_type TEXT,                 -- manhole|inlet|junction|outfall
    base_capacity DOUBLE PRECISION,
    capacity_factor DOUBLE PRECISION DEFAULT 1.0
);

CREATE TABLE drainage_edge (
    id SERIAL PRIMARY KEY,
    from_node INTEGER REFERENCES drainage_node(id),
    to_node INTEGER REFERENCES drainage_node(id),
    length_m DOUBLE PRECISION,
    diameter_m DOUBLE PRECISION,
    slope DOUBLE PRECISION,
    base_capacity DOUBLE PRECISION,
    current_capacity DOUBLE PRECISION
);

CREATE TABLE cell_state (
    cell_id INTEGER,
    ts TIMESTAMP,
    elevation DOUBLE PRECISION,
    storage_m3 DOUBLE PRECISION,
    depth_cm DOUBLE PRECISION,
    inflow_m3 DOUBLE PRECISION,
    outflow_m3 DOUBLE PRECISION,
    drained_m3 DOUBLE PRECISION,
    PRIMARY KEY (cell_id, ts)
);

CREATE TABLE flood_prediction (
    id SERIAL PRIMARY KEY,
    cell_id INTEGER,
    ts TIMESTAMP,
    forecast_time TIMESTAMP,
    predicted_depth_cm DOUBLE PRECISION,
    lower_bound_cm DOUBLE PRECISION,
    upper_bound_cm DOUBLE PRECISION,
    confidence DOUBLE PRECISION
);

CREATE TABLE road_risk (
    road_id TEXT,
    forecast_time TIMESTAMP,
    predicted_depth_cm DOUBLE PRECISION,
    risk_level TEXT,               -- SAFE|WATCH|HIGH|UNSAFE
    data_quality TEXT,             -- HIGH_CONF|MEDIUM_CONF|LOW_CONF|MODEL_ONLY
    confidence DOUBLE PRECISION
);

CREATE TABLE route_request (
    id SERIAL PRIMARY KEY,
    origin TEXT,
    destination TEXT,
    mode TEXT,                     -- vehicle|emergency|pedestrian
    ts TIMESTAMP
);

CREATE TABLE mass_balance_log (
    ts TIMESTAMP PRIMARY KEY,
    input_total_m3 DOUBLE PRECISION,
    storage_total_m3 DOUBLE PRECISION,
    drained_total_m3 DOUBLE PRECISION,
    boundary_outflow_m3 DOUBLE PRECISION,
    balance_error_m3 DOUBLE PRECISION,
    status TEXT                    -- PASS|FAIL
);

CREATE TABLE event_log (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP,
    component TEXT,
    event_type TEXT,
    payload JSONB
);
```

---

## 4. API Contracts

```http
POST /api/rainfall/ingest
Body: { ts, cell_id, rainfall_mm, forecast_horizon_min, source }

POST /api/sensors/reading
Body: { sensor_id, ts, water_level_cm, float_state, battery, signal_quality, heartbeat }

GET  /api/sensors/{id}/status
Resp: { sensor_id, status, last_seen, last_reading }

POST /api/flood/simulate
Body: { catchment_id, start_ts, duration_min }
Resp: { run_id, status }

GET  /api/flood/forecast?cell_id=&forecast_time=
Resp: { predicted_depth_cm, lower_bound_cm, upper_bound_cm, confidence }

GET  /api/flood/grid?ts=
Resp: [{ cell_id, depth_cm, risk_level }]

GET  /api/flood/roads?ts=
Resp: [{ road_id, depth_cm, risk_level, data_quality, confidence }]

POST /api/routes/safe
Body: { origin, destination, mode, forecast_minutes }
Resp: { route: [...], eta_minutes, flood_exposure, confidence }

GET  /api/diagnostics/mass_balance?ts=
Resp: { input_total_m3, storage_total_m3, drained_total_m3, boundary_outflow_m3, balance_error_m3, status }
```

---

## 5. Flood Engine Pseudocode

### 5.1 `dem.py` — Pit-fill + D8

```
function preprocess_dem(elevation_grid):
    filled = priority_flood_fill(elevation_grid)   # remove local depressions
    flow_dir = {}
    for cell in filled.cells:
        neighbors = get_8_neighbors(cell)
        lowest = min(neighbors, key=lambda n: n.elevation)
        if lowest.elevation < cell.elevation:
            flow_dir[cell.id] = lowest.id
        else:
            flow_dir[cell.id] = None   # sink/outlet, route to boundary or nearest drain inlet
    return filled, flow_dir
```

### 5.2 `runoff.py` — SCS-CN, cumulative/incremental

```
function compute_incremental_runoff(cell, cumulative_P_prev, cumulative_rainfall_mm):
    CN = cell.cn_value
    S = (25400 / CN) - 254          # mm
    Ia = 0.2 * S
    P = cumulative_rainfall_mm

    if P <= Ia:
        Q_cum = 0
    else:
        Q_cum = ((P - Ia) ** 2) / (P - Ia + S)

    delta_Q = max(0, Q_cum - cumulative_P_prev.Q)
    cumulative_P_prev.Q = Q_cum
    cumulative_P_prev.P = P
    return delta_Q   # mm, this timestep's incremental runoff
```

### 5.3 `routing.py` — Slope-weighted fraction routing (synchronous update)

```
function compute_outflows(cells, flow_dir, dt, k, f_max):
    # PASS 1: compute using storage snapshot at t — read-only
    outflow = {}
    for cell in cells:
        j = flow_dir[cell.id]
        if j is None:
            outflow[cell.id] = 0
            continue
        slope = max(0, (cell.elevation - j.elevation) / distance(cell, j))
        f = clip(k * sqrt(slope) * dt, 0, f_max)
        outflow[cell.id] = f * cell.storage_t   # uses storage at t only

    return outflow   # do not mutate storage here
```

### 5.4 `drainage.py` — Capture + dynamic capacity

```
function compute_drain_capture(cell, outflow_i, dt):
    if not cell.has_inlet:
        return 0
    node = cell.drainage_node
    dynamic_capacity = node.base_capacity * node.capacity_factor(t)   # F_t: 1.0/0.8/0.6/0.3
    available = cell.storage_t - outflow_i
    capture = min(dynamic_capacity * dt, max(0, available))
    return capture
```

### 5.5 `storage.py` — Synchronous state update (apply after all cells computed)

```
function update_storage(cells, inflow, outflow, drain_capture):
    for cell in cells:
        S_next = cell.storage_t + inflow[cell.id] - outflow[cell.id] - drain_capture[cell.id]
        S_next = max(0, S_next)                       # never negative
        assert outflow[cell.id] + drain_capture[cell.id] <= cell.storage_t + inflow[cell.id] + EPSILON
        cell.storage_t1 = S_next
        cell.depth_cm = (S_next / cell.effective_area_m2) * 100

    for cell in cells:
        cell.storage_t = cell.storage_t1   # commit, once every cell is done
```

### 5.6 `conservation.py` — Mass balance diagnostic (run every timestep)

```
function check_mass_balance(input_total, storage_total, drained_total, boundary_outflow, tolerance):
    balance_error = input_total - (storage_total + drained_total + boundary_outflow)
    status = "PASS" if abs(balance_error) <= tolerance else "FAIL"
    log_mass_balance(input_total, storage_total, drained_total, boundary_outflow, balance_error, status)
    return status
```

---

## 6. Sensor Pipeline Pseudocode

### 6.1 `validation.py`

```
function validate_reading(reading, prev_reading, dt):
    if not (0 <= reading.water_level_cm <= MAX_PHYSICAL_DEPTH):
        return "INVALID_RANGE"

    if prev_reading is not None:
        rate = abs(reading.water_level_cm - prev_reading.water_level_cm) / dt
        if rate > r_critical:
            return "INVALID_SPIKE"

    if not reading.heartbeat:
        return "MISSING_HEARTBEAT"

    return "VALID"
```

### 6.2 `health.py`

```
function update_sensor_state(sensor, missed_heartbeats):
    if missed_heartbeats == 0:
        sensor.status = "ONLINE"
    elif missed_heartbeats < STALE_THRESHOLD:
        sensor.status = "ONLINE"
    elif missed_heartbeats < OFFLINE_THRESHOLD:
        sensor.status = "STALE"
    else:
        sensor.status = "OFFLINE"
```

### 6.3 `fusion.py` — Bias correction + spatial propagation

```
function update_bias(sensor_id, predicted, observed, prev_bias, alpha):
    error = observed - predicted
    new_bias = alpha * error + (1 - alpha) * prev_bias
    return new_bias

function propagate_bias(unsensed_cell, sensor_biases, sensor_locations):
    weights_sum = 0
    weighted_bias = 0
    for sensor_id, bias in sensor_biases.items():
        d = distance(unsensed_cell, sensor_locations[sensor_id])
        w = 1 / (1 + d)              # decays with distance
        weighted_bias += w * bias
        weights_sum += w
    return weighted_bias / weights_sum if weights_sum > 0 else 0

function apply_correction(predicted_depth, bias):
    return predicted_depth + bias
```

### 6.4 `anomaly.py`

```
function detect_anomalies(cell, sensor, model_pred, dt):
    flags = []
    rate = (sensor.level_t - sensor.level_t_minus_1) / dt
    if rate > r_critical:
        flags.append("RAPID_RISE")

    if abs(sensor.level_t - model_pred) > tau_disagreement:
        flags.append("MODEL_DISAGREEMENT")

    if "RAPID_RISE" in flags and cell.drainage_node.capacity_factor < 0.7:
        flags.append("POSSIBLE_DRAINAGE_CAPACITY_ANOMALY")  # never say "detected blockage"

    return flags
```

### 6.5 Confidence (windowed agreement)

```
function compute_confidence(sensor_coverage, freshness, recent_errors_window):
    mean_error = average(recent_errors_window)
    agreement = 1 / (1 + mean_error)     # simple monotonic mapping, tune later
    C = w_c * sensor_coverage + w_f * freshness + w_a * agreement
    return clip(C, 0, 1)
```

---

## 7. Routing Pseudocode

```
function edge_cost(road, mode, lambda_risk, mu_uncertainty):
    base = road.travel_time
    risk_penalty = lambda_risk * road.risk_score
    uncertainty_penalty = mu_uncertainty * (1 - road.confidence)
    if mode == "emergency" and road.risk_level == "UNSAFE":
        return INFINITY   # hard block
    return base + risk_penalty + uncertainty_penalty

function safe_route(graph, origin, dest, mode, forecast_minutes):
    for edge in graph.edges:
        edge.cost = edge_cost(edge, mode, LAMBDA, MU)
    path = dijkstra(graph, origin, dest, weight="cost")
    return {
        "route": path,
        "eta_minutes": sum_travel_time(path),
        "flood_exposure": max_risk_on_path(path),
        "confidence": min_confidence_on_path(path)
    }
```

---

## 8. Replay Format

**Rainfall replay (`replay/rainfall/storm_01.json`):**
```json
[
  {"t_min": 0,  "cell_id": 12, "rainfall_mm_hr": 10},
  {"t_min": 15, "cell_id": 12, "rainfall_mm_hr": 25},
  {"t_min": 30, "cell_id": 12, "rainfall_mm_hr": 50}
]
```

**Sensor replay (`replay/sensors/s03.json`):**
```json
[
  {"t_min": 0,  "water_level_cm": 4,  "float_state": false, "heartbeat": true},
  {"t_min": 15, "water_level_cm": 9,  "float_state": false, "heartbeat": true},
  {"t_min": 30, "water_level_cm": 16, "float_state": true,  "heartbeat": true}
]
```

Replay scheduler pushes these into the same `/api/rainfall/ingest` and `/api/sensors/reading` endpoints real hardware/live feeds would use — the rest of the pipeline never knows the difference.

---

## 9. Team Tickets (4-person parallel board)

| Block | Team A — Flood Model | Team B — Backend/Data | Team C — GIS/Product | Team D — Hardware/Routing |
|---|---|---|---|---|
| 0–4h | DEM load + pit-fill + D8 | DB schema + replay ingestion API | Dashboard shell + map base layer | Ultrasonic reading on tabletop rig |
| 4–8h | Cell storage + slope routing + safeguards | Drainage graph API | Flood layer rendering | Float switch + heartbeat |
| 8–12h | Drain coupling + dynamic capacity + mass conservation | Logging/versioning, event_log | Time slider + sensor health panel | Sensor → API transmission |
| 12–16h | Scenario tuning (k, f_max, Δt) | Fusion engine (bias + propagation) | Route visualization + confidence UI | Road graph construction |
| 16–20h | — Integration — | — Integration — | — Integration — | — Integration — |
| 20–24h | Run full synthetic scenarios end-to-end | | | |
| 24–28h | Wire sensor corrections into live dashboard | | | |
| 28–32h | Fault injection: bad sensor, offline sensor, capacity drop, low confidence | | | |
| 32–36h | Demo stabilization, no new features | | | |

5th member (if available) — **Validation/QA**: owns the 6 test scenarios below, mass-balance dashboard, fault-injection scripts, judge Q&A prep, and the "claims vs. not established" doc.

---

## 10. Test Scenarios (non-circular validation)

1. **Mass conservation** — run a replay storm, assert `|balance_error| < tolerance` at every timestep.
2. **Sensor pipeline** — inject an out-of-range and a rate-spike reading, assert both are flagged and excluded from fusion.
3. **Fusion convergence** — inject a fixed synthetic bias, assert corrected prediction converges toward observed value over N timesteps.
4. **Degraded mode** — disconnect a sensor mid-run, assert system falls back to model-only, confidence drops, dashboard shows OFFLINE not a stale value.
5. **Routing avoidance** — artificially set one road to UNSAFE, assert the emergency route avoids it and a valid alternative is returned.
6. **End-to-end replay** — full storm replay from rainfall ingestion through to a routed emergency-vehicle path; assert no exceptions, no negative storage, mass balance PASS throughout.

---

## 11. Claims Table (keep this exact table in the pitch deck)

| Claim | Status |
|---|---|
| Real-time sensor ingestion | Demonstrated |
| Sensor plausibility filtering | Demonstrated |
| Degraded-state handling | Demonstrated |
| Rainfall replay pipeline | Demonstrated |
| Coarse runoff estimation (SCS-CN approx.) | Demonstrated |
| Dynamic surface storage + routing | Demonstrated |
| Drainage graph + dynamic capacity | Demonstrated |
| Sensor-based bias correction | Demonstrated |
| Flood-aware, mode-specific routing | Demonstrated |
| Mass conservation diagnostic | Demonstrated |
| Live radar integration | Not demonstrated |
| City-wide deployment | Future work |
| Field-validated flood accuracy | Not established |
| Confirmed drainage blockage detection | Not established (flagged as "possible anomaly" only) |

---

## 12. Immediate Next Actions

1. Fill `config/defaults.yaml` with Section 1 values before anyone writes code.
2. Pick and freeze the demo catchment (small, bounded, DEM available).
3. Team A starts DEM pit-fill first — everything downstream depends on valid flow directions.
4. Team D builds the tabletop rig in parallel, independent of Team A/B.
5. Write the 6 test scenarios as actual test stubs before hour 12, even if empty — they define what "done" means for integration.
