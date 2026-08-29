# SafeSurge – AURA-FLOOD
### Physics-Guided Urban Flood Nowcasting & Safe Routing System

---

## 1. Problem Statement

Urban flooding in Indian metros — Mumbai, Delhi, Chennai, Bengaluru — has become an annual crisis. Traditional Numerical Weather Prediction (NWP) models fall short because knowing *how much* rain will fall does not translate into knowing *where* streets will flood.

Flooding is a hyper-local phenomenon governed by:
- Micro-topography and elevation
- Impervious surface fraction (concrete, asphalt)
- Surface runoff and natural flow paths
- Underground drainage capacity — often invisible, aging, and strained
- Real-time ground-truth, which is sparse

Municipal bodies currently lack real-time, street-level predictive systems, so cities are caught off guard by rapid water accumulation, leading to gridlock, economic loss, and loss of life.

**Goal:** a 0–3 hour urban flood nowcasting system that fuses rainfall nowcasts, high-resolution terrain, a graph-based drainage model, and real-time IoT observations to predict street-level inundation depth and route around it — before it happens.

A pure hydrodynamic model is too computationally expensive to update rapidly with sparse live data. A pure sensor network can't observe every street and is vulnerable to noise, drift, and dropout. **The solution couples both.**

---

## 2. Core Design Principle: Three Intelligence Layers

| Layer | Question it answers | Component |
|---|---|---|
| **Prediction** | Given rainfall, terrain, and drainage state, where will water accumulate? | Physics engine (runoff → surface routing → drainage coupling) |
| **Observation** | What is actually happening at this specific point right now? | IoT sensor network |
| **Decision** | Given predicted + observed water levels, which roads should be avoided? | Risk classification + routing engine |

The model does the spatial prediction. Sensors validate and correct it locally — they do not replace it. Keeping this distinction explicit avoids the common design mistake of asking a handful of point sensors to "predict the city."

---

## 3. System Architecture

```
Rainfall Nowcast (Radar/IMD)
        ↓
Rainfall Grid → SCS-CN Runoff ──┐
                                 │
DEM → Pit Fill → D8 Flow Dir ───┤
                                 ↓
                    2D Surface-Water Routing
                                 ↓
                       Surface Storage (per cell)
                                 ↓
                 Drainage Inlet Capture ←→ 1D Drainage Graph
                                 ↓
                    Capacity / Surcharge Check
                                 ↓
                          Flood Depth Grid
                                 ↓
                    ┌────────────┴────────────┐
              Road Risk Mapping         IoT Sensor Observations
                    │                          ↓
                    │                   Validation → Fusion
                    │                          ↓
                    └──────────► Confidence Score
                                 ↓
                    Flood-Aware Routing (cost-penalized graph)
                                 ↓
                          GIS Command Center
```

Eight subsystems implement this pipeline. Grouping at this level (rather than presenting 40+ micro-steps) keeps the architecture legible to judges and reviewers.

---

## 4. Subsystem 1 — Rainfall & Terrain Engine

**Rainfall dataset** (`rainfall.csv`)
```
timestamp, cell_id, latitude, longitude, rainfall_mm, rainfall_rate_mm_hr
```
Prototype: synthetic/replayed storm at 5-minute intervals. Production: radar-derived nowcast (IMD Doppler Weather Radar / GPM-IMERG as fallback).

**DEM dataset** (`dem.tif`, raster)
```
elevation, latitude, longitude
```
Used to compute slope, pits/depressions, and D8 flow direction (which of 8 neighboring cells receives outflow). Note: 30 m SRTM/Cartosat resolution is coarse for true street-level accuracy — state this limitation explicitly rather than implying LiDAR-grade precision without it.

**Land use dataset** (`landuse.geojson`)
```
cell_id, land_use, impervious_fraction, curve_number
```

**Runoff model — SCS Curve Number (corrected, complete form)**

Potential maximum retention:
$$ S = \frac{25400}{CN} - 254 \quad \text{(mm)} $$

Initial abstraction (standard assumption):
$$ I_a = 0.2S $$

Runoff depth, valid only when cumulative rainfall $P > I_a$:
$$ Q = \frac{(P - I_a)^2}{P - I_a + S}, \quad Q = 0 \text{ if } P \leq I_a $$

*(The earlier draft stated the retention formula but omitted the actual runoff equation — this is the piece that converts rainfall into usable runoff volume, and without it the pipeline has a gap between "cumulative rainfall" and "incremental runoff.")*

Pipeline: Rainfall → Cumulative rainfall → Cumulative runoff (via $Q$ above) → Incremental runoff (difference between consecutive timesteps) → Runoff volume input to the surface model.

---

## 5. Subsystem 2 — 2D Surface Flood Model

Each computational cell tracks: `elevation, area, rainfall, runoff, storage, inflow, outflow, drainage_capture, flood_depth`.

**Storage update, with the non-negativity constraint enforced explicitly (not just asserted):**
$$ S_t = \max\left(0,\ S_{t-1} + I_t - O_t - D_t - B_t\right) $$

where $I_t$ = runoff + upstream inflow, $O_t$ = outflow to downstream cells (via D8 direction, capped by available head/slope), $D_t$ = drainage inlet capture, $B_t$ = boundary/edge-of-domain outflow.

**Role of D8:** it answers *"which direction does water move"*, not *"how much water is present."* D8 direction + the storage balance above are both required; D8 alone only gives a flow-path map, not a depth estimate.

---

## 6. Subsystem 3 — Underground Drainage Network

Modeled as a directed graph $G = (V, E)$: $V$ = manholes/inlets/junctions/outfalls, $E$ = pipes/culverts/canals.

**Nodes** (`drainage_nodes.geojson`): `node_id, latitude, longitude, node_type, invert_elevation, base_capacity`
**Edges** (`drainage_edges.geojson`): `edge_id, from_node, to_node, length, diameter, slope, capacity, roughness (optional)`

**Surface-to-drainage coupling:** flooded surface cell → nearest stormwater inlet → drainage node → pipe → junction → outfall. The model asks *"how much can the network actually accept,"* rather than assuming all surface water instantly disappears into the drain — this is what allows the system to represent surcharge.

**Effective capacity** (consistent unit: m³/min throughout):
$$ C_{eff} = C_0 \cdot F_t $$
where $F_t \in [0,1]$ is a condition/degradation factor (silting, blockage, partial closure).

**Drainage capture term used in Section 5:**
$$ D_t = \min(\text{demand from surface}, C_{eff}) $$

**Overcapacity example:**
```
Incoming water   = 15 m³/min
Effective drain  =  6 m³/min  (base 20 m³/min × factor 0.3)
Remaining on surface = 9 m³/min → adds to surface storage
```
Drainage capacity ↓ → surface storage ↑ → flood depth ↑. This is the surcharge mechanism.

---

## 7. Subsystem 4 — Flood Depth Engine

$$ \text{Depth} = \frac{\text{Storage}}{\text{Effective Area}} $$

Example: 50 m³ storage over 500 m² → 0.1 m = 10 cm. Output is a per-cell flood-depth grid, e.g. `C001: 0cm, C002: 4cm, C003: 12cm, C004: 28cm`.

---

## 8. Subsystem 5 — IoT Sensor System

**Hardware (prototype):** ESP32 + HC-SR04 ultrasonic distance sensor.

$$ \text{WaterDepth} = \text{ReferenceHeight} - \text{SensorDistance} $$
e.g. 100 cm reference − 73 cm measured = 27 cm water depth.

**Deployment:** for a real installation, mount on an elevated fixed structure (roadside pole/streetlight) facing the road surface — a single sensor observes its own point location only, not the surrounding network.

**Placement strategy — six stations at functionally distinct points**, not randomly distributed:
`headwater, arterial road, low-lying basin, depression, elevated reference point, outfall`.

**Sensor reading schema** (`sensors.csv`):
```
sensor_id, timestamp, latitude, longitude, distance_cm, water_depth_cm, battery, rssi, status
```

---

## 9. Subsystem 6 — Sensor Validation & Fusion

**Validation pipeline:** Raw reading → range check → rate-of-rise check → burst/median filtering → heartbeat/freshness check → quality state (`ONLINE / STALE / OFFLINE / INVALID`).

**Spike rejection example:** readings `10, 11, 12, 90, 13` cm — the 12→90 cm jump exceeds a physically plausible rate-of-rise, so it's rejected and the previous valid state is retained.

**Dropout handling:** `ONLINE → STALE → OFFLINE` as heartbeats are missed. The model keeps running on physics alone; confidence decreases because observational coverage has dropped — it should never silently keep using a stale reading as if it were current.

**Fusion (bias correction):**
$$ e_t = H_{sensor} - H_{model} $$
$$ B_t = \alpha e_t + (1-\alpha) B_{t-1} $$
$$ H_{corrected} = H_{model} + B_t $$

**Spatial propagation** (inverse-distance weighting):
$$ w_i = \frac{1}{d_i^{\,p} + \epsilon} $$
applied with a defined cutoff radius so a single sensor doesn't over-influence distant cells.

**Anti-circularity requirement:** confidence must be evaluated against the *original* physics-only prediction, not the sensor-corrected one. Feeding the corrected estimate back into its own confidence calculation would make the system look more accurate than it is — this must be structurally prevented, not just avoided by convention.

**Confidence score** (prototype weighting — state explicitly this is a design choice, not a calibrated statistical probability):
$$ C = 0.30\,C_{coverage} + 0.30\,C_{freshness} + 0.40\,C_{agreement} $$

**Anomaly rules:**
| Type | Condition |
|---|---|
| Rapid rise | $\Delta h / \Delta t >$ threshold |
| Model disagreement | $\lvert H_{sensor} - H_{model} \rvert >$ threshold |
| Sensor inconsistency | e.g. ultrasonic reads dry, float switch reads wet |
| Possible capacity anomaly | Observed behavior inconsistent with expected drainage response |

---

## 10. Subsystem 7 — Road Flood Intelligence

Spatial intersection of flood-depth grid with road geometry → depth aggregation per road segment → road-level depth (e.g. `R017: 26 cm`).

**Risk classification (state clearly: prototype thresholds, not a vehicle-safety standard):**
| Depth | Risk |
|---|---|
| < 5 cm | SAFE |
| 5–15 cm | WATCH |
| 15–25 cm | HIGH |
| ≥ 25 cm | UNSAFE |

---

## 11. Subsystem 8 — Flood-Aware Routing

Road graph edges carry: `road_id, travel_time, flood_depth, risk, confidence`.

**Cost function — normalize terms before combining, since travel time (seconds) and risk/uncertainty (categorical or 0–1 scores) are not naturally the same unit:**
$$ Cost = TravelTime + \lambda \cdot Risk_{norm} + \mu \cdot Uncertainty_{norm} $$

- $Risk_{norm}, Uncertainty_{norm} \in [0,1]$
- $\lambda, \mu$ are tunable penalty weights, chosen empirically for the demo
- Hard barrier: if depth ≥ 25 cm (UNSAFE), set $Cost = \infty$ — the edge is effectively removed from the routable graph
- Soft penalty: for 15–25 cm (HIGH), apply a strong but finite penalty rather than removing the edge outright, so the router can still use it if there is genuinely no alternative

**Example:** shortest path A→B→D (70s) crosses road B at 26 cm (UNSAFE) → edge cost becomes ∞ → router selects A→C→D instead, even though it's slower. This demonstrates the full prediction→decision chain, not just a visualization.

---

## 12. GIS Command Center (Dashboard)

- **Map layers:** rainfall, flood depth, road risk, drainage network, sensor locations, flow directions
- **Timeline scrubber:** NOW, +30, +60, +90, +120, +150, +180 minutes
- **Sensor panel:** live status per station (🟢 ONLINE / 🟡 STALE / ⚪ OFFLINE)
- **Forecast panel:** predicted depth + forecast range + confidence %, e.g. `24 cm (range 19–31 cm), confidence 82%`

---

## 13. Mass Conservation Check

$$ E = I - \Delta S - D - B $$
where $I$ = rainfall input, $\Delta S$ = change in surface storage, $D$ = drainage outflow, $B$ = boundary outflow, all in consistent volume units (m³) over the same timestep.

Report `PASS` when $|E| <$ configured tolerance — **do not** claim exact zero-error; floating-point and discretization effects make that an unrealistic and scientifically indefensible claim for any numerical model.

---

## 14. Fault Injection Test Plan

| Test | Injected condition | Expected system behavior |
|---|---|---|
| A — Sensor failure | S001 → OFFLINE | Model continues; confidence decreases |
| B — Sensor spike | 12 cm → 90 cm | Spike detected and rejected |
| C — Drainage degradation | Capacity factor 1.0 → 0.3 | Drainage↓, storage↑, flood depth↑ |
| D — Extreme rainfall | Intensity spike | Runoff↑, flood depth↑, road risk↑ |
| E — No rainfall | Zero input | System reports "forecast unavailable," not a fabricated prediction |
| F — No sensor coverage | All sensors down | Model continues; confidence drops sharply |
| G — Flooded shortest route | Force UNSAFE on shortest path | Router selects valid alternative |

---

## 15. Datasets Required — with Real Access Links

Status key: 🟢 directly downloadable today · 🟡 accessible but needs registration/processing/is coarse · 🔴 not publicly available — must be requested, digitized, or synthesized

| # | Dataset | Required? | Status | Real source & link |
|---|---|---|---|---|
| 1 | Rainfall nowcast | Yes | 🟡 | **IMD API** (nowcast, AWS/ARG, radar image, rainfall) — https://mausam.imd.gov.in/responsive/apis.php · https://api.imd.gov.in/public/api_reference.html · Radar imagery (not raw reflectivity volumes): https://mausam.imd.gov.in/responsive/radar.php |
| 1b | Rainfall (satellite fallback) | Alt. | 🟢 | **NASA GPM-IMERG** half-hourly 0.1° global rainfall: https://gpm.nasa.gov/data/imerg · GES DISC direct download: https://disc.gsfc.nasa.gov (search "GPM_3IMERGHH") · Also on Google Earth Engine: `NASA/GPM_L3/IMERG_V07` |
| 2 | DEM | Yes | 🟡 | **Cartosat-1 DEM (Bhuvan/NRSC)**, free after registration: https://bhuvan.nrsc.gov.in/ → https://bhuvan-app3.nrsc.gov.in/data/download/ (wiki guide: https://bhuvan.nrsc.gov.in/wiki/index.php/Free_Satellite_Data_Download) |
| 2b | DEM (global fallback) | Alt. | 🟢 | **SRTM 30m**, no login: https://earthexplorer.usgs.gov or via Google Earth Engine `USGS/SRTMGL1_003`. Coarser than Cartosat-1 — note this limitation if used |
| 3 | Land use / LULC | Yes | 🟡 | **Bhuvan LULC thematic layers**: https://bhuvan.nrsc.gov.in/ (registration required) |
| 3b | Land use (fallback) | Alt. | 🟢 | **OpenStreetMap landuse tags** via Overpass Turbo: https://overpass-turbo.eu or https://www.quickmaptools.com/download-osm (browser-based, no login) |
| 4 | Drainage network (nodes/pipes graph) | Yes | 🔴 (mostly) | No pan-India public graph exists. Partial exceptions: **Bengaluru (BBMP) stormwater drain maps**, CKAN dataset: https://data.opencity.in/dataset/bengaluru-stormwater-drains-maps · **India Geodata** aggregation of AMRUT/Swachh Bharat stormwater drain lines (multiple cities, GeoJSON/shapefile): https://yashveeeeeeer.github.io/india-geodata/ — check coverage for your target city before relying on it |
| 5 | Drainage capacity/condition | Yes | 🔴 | Not published by any metro corporation. Must be estimated (pipe diameter/slope → Manning's equation) or synthesized for the demo |
| 6 | Road network | Yes | 🟢 | **OpenStreetMap** — full India extract: https://download.geofabrik.de/asia/india.html · Pre-packaged HOTOSM roads export: https://data.humdata.org/dataset/hotosm_ind_roads · Custom bounding-box export (no install): https://overpass-turbo.eu |
| 7 | Historical flood events | Recommended | 🔴 | No structured public dataset. Must be compiled manually from Corporation complaint portals, geotagged news/social posts, or NDMA reports — no working link to hand over |
| 8 | Sensor telemetry | Yes (IoT) | — | Generated by your own ESP32 + HC-SR04 hardware; not an external dataset |
| 9 | Sensor registry/config | Yes | — | Self-defined during calibration; not an external dataset |
| 10 | Soil/hydrology | Useful | 🟡 | **ICAR-NBSS&LUP Bhoomi Geoportal** (soil texture, depth, national soil maps): https://bhoomigeoportal-nbsslup.in/ · Legacy district maps via EU archive: https://esdac.jrc.ec.europa.eu/node/39065 |
| 11 | Weather context | Optional | 🟡 | IMD AWS/ARG station data via the same IMD API above |
| 12 | River gauge / catchment boundaries (new — supports drainage/outfall modeling) | Optional | 🟢 | **India WRIS**: https://indiawris.gov.in/wris · Quality-controlled GHI dataset (gauges + catchments): https://essd.copernicus.org/articles/15/4389/2023/ |

### What's genuinely missing (no usable public link)
These are the datasets the original spec assumes exist but that **do not have a direct download link** for most Indian cities — they need to be requested, digitized from PDFs, or synthesized:

1. **Underground drainage network as a routable graph** (nodes + pipe capacities) — this is the single biggest gap. Only Bengaluru has a public dataset; Chennai/Mumbai/Delhi drainage GIS is either unpublished or exists only as static PDF master-plan maps that would need manual digitizing (e.g., tracing pipe centerlines in QGIS from a scanned SWD master plan obtained via RTI).
2. **Drainage pipe/inlet capacity and condition** (base_capacity, degradation factor) — no corporation publishes this; it's normally internal maintenance data.
3. **Historical street-level flood depth records** — exists informally (news reports, citizen complaints, social media) but not as a clean structured dataset; you'd need to build this yourself by geocoding past flood reports for your demo area.
4. **High-resolution (≤5m) LiDAR DEM** — Cartosat-1/SRTM top out around 30m, too coarse for true street-level micro-topography; municipal LiDAR surveys exist for some smart-city areas but aren't publicly downloadable.

For the hackathon MVP, items 1–3 are the ones worth explicitly synthesizing (as already scoped in Section 18) rather than chasing further — say so directly to judges rather than presenting a synthetic graph as if it were real municipal data.

### Exact schemas

```
rainfall.csv:        timestamp, cell_id, latitude, longitude, rainfall_mm, rainfall_rate_mm_hr
dem.tif:              raster elevation
landuse.geojson:      cell_id, land_use, impervious_fraction, curve_number
drainage_nodes.geojson: node_id, latitude, longitude, node_type, invert_elevation, base_capacity
drainage_edges.geojson: edge_id, from_node, to_node, length, diameter, slope, capacity
roads.geojson:        road_id, road_name, geometry, road_class, speed
sensors.csv:          sensor_id, timestamp, latitude, longitude, distance_cm, water_depth_cm, status, battery, rssi
sensor_registry.yaml: sensor_id, reference_height_cm, min_range_cm, max_range_cm, max_rate_cm_per_min, sampling_interval
historical_floods.csv: event_id, timestamp, latitude, longitude, road_id, observed_depth_cm, source
```

---

## 16. What's Real vs. Simulated (state this explicitly to judges)

| Physically real | Replayed/synthetic |
|---|---|
| ESP32 + HC-SR04 hardware | Radar rainfall |
| Water-level measurement | DEM (unless real LiDAR obtained) |
| Wi-Fi/HTTP telemetry | Drainage network graph |
| Backend ingestion + validation | Historical flood events |
| — | City-scale flood simulation, storm progression |

This is an acceptable prototype scope **only if labeled clearly** — do not present synthetic drainage/DEM data as if it were live municipal data.

---

## 17. Repository Structure

```
aura-flood/
├── data/
│   ├── rainfall/       terrain/       landuse/
│   ├── drainage/       roads/         sensors/
│   └── replay/sensors/
├── backend/
│   ├── api/  services/  schemas/
├── engines/
│   ├── runoff/  surface/  drainage/
│   ├── sensors/  fusion/  risk/  routing/
├── frontend/
│   ├── map/  sensors/  forecast/  routing/  diagnostics/
└── tests/
    ├── hydrology/  drainage/  sensors/  routing/  end_to_end/
```

**Stack:** FastAPI (backend) · NumPy/Pandas (hydrology) · GeoPandas/Rasterio/Shapely (GIS) · NetworkX (drainage graph) · PostgreSQL+PostGIS (storage) · React + MapLibre/Leaflet (frontend) · ESP32+HC-SR04 (hardware) · Docker (deployment)

---

## 18. MVP Scope for the Hackathon

- 10×10 synthetic computational grid with a realistic elevation gradient (1 valley, 1 basin, 1 ridge, 1 canal)
- Synthetic/replayed rainfall storm
- SCS-CN runoff + D8 routing + surface storage
- Small drainage graph: 10–20 nodes, 20–30 edges
- 10 road segments
- 1–2 physical ESP32/HC-SR04 sensors (real hardware) + 4 simulated sensor feeds
- Full validation, fusion, confidence, road risk, Dijkstra-based routing
- GIS dashboard with a single **"Start Storm Replay"** button driving the 0→180 minute timeline

### Demo script
1. Normal rainfall → depth 0–3cm, all roads SAFE
2. Rainfall intensifies → runoff↑ → storage↑ → depth↑
3. Reduce drainage capacity 100%→30% → visible flooding increase
4. Physically pour water into the sensor rig → live depth updates on dashboard
5. Inject a spike (12→90cm) → system flags and rejects it
6. Disconnect a sensor → ONLINE→STALE→OFFLINE, confidence visibly drops
7. Flood the shortest route → router reroutes A→C→D around the UNSAFE road

This single run demonstrates the full prediction → observation → decision chain end to end.

---

## 19. Judge Q&A Prep

**"What does your system actually predict?"**
Water depth at individual urban grid cells for future time steps, then mapped onto roads for street-level risk.

**"What does the ultrasonic sensor predict?"**
Nothing — it observes actual local water level at its installation point. Prediction is the model's job; observation is the sensor's job.

**"Why do you need the sensor if you have a model?"**
The model predicts spatially but can drift from reality; sensors give ground-truth to correct it and to raise or lower confidence.

**"Why do you need drainage data specifically?"**
Because rainfall becomes dangerous flooding precisely when runoff exceeds what the surface *and* the drainage network can carry away — modeling surface flow alone misses the surcharge mechanism.

**"What happens if a sensor fails?"**
The physics model keeps running; confidence drops because observational coverage decreased.

**"What happens when a road floods?"**
Its risk classification rises; past the configured hard threshold, the routing engine removes it from the usable graph.

**"How do you validate the model is correct?"**
Mass conservation checks, controlled fault-injection tests, sensor cross-validation, and historical flood records where available — explicitly not claimed as production-grade validation.
