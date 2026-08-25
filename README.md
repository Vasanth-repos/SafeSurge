# Urban Flood Nowcasting & Response System (AURA-FLOOD)

An autonomous, physics-informed hydrological nowcasting, real-time sensor fusion, mass-conserving drainage simulation, and risk-aware emergency routing system.

---

## 🌟 Key Features

1. **Hydrological Nowcasting Engine (`flood_engine/`)**:
   - **Pit-Fill & D8 Flow Direction (`dem.py`)**: Resolves depressions and generates topological steepest-descent surface routing vectors.
   - **SCS-CN Runoff Estimation (`runoff.py`)**: Incremental/cumulative runoff estimation calibrated per land-use Curve Number.
   - **Slope-Weighted 2D Routing (`routing.py`)**: Synchronous numerical cell transfers with CFL-bounded fractions.
   - **Drainage Network Coupling (`drainage.py`)**: Dynamic inlet capture and blockage degradation factors ($F_t \in [1.0, 0.8, 0.6, 0.3]$).
   - **Closed-Loop Mass Balance Diagnostic (`conservation.py`)**: Real-time water balance verification ($\Delta V \approx 0.0000\text{ m}^3$).

2. **Sensor Processing & Spatial Fusion (`sensor/`)**:
   - **Plausibility & Spike Filtering (`validation.py`)**: Validates physical depth limits ($0 \le h \le 300\text{ cm}$) and critical rate-of-rise ($|\Delta h/\Delta t| \le 5\text{ cm/min}$).
   - **Health State Machine (`health.py`)**: Tracks heartbeats and triggers automatic transitions: `ONLINE` $\to$ `STALE` $\to$ `OFFLINE` $\to$ `INVALID`.
   - **Exponential Bias Smoothing & IDW Propagation (`fusion.py`)**: Calibrates local sensor biases and propagates corrections across unsensed cells.
   - **Hydrological Anomaly Detection (`anomaly.py`)**: Flags rapid rise, sensor-model disagreements, and possible drainage capacity anomalies.

3. **Risk-Aware Emergency Routing (`routing/`)**:
   - **Road Flood Depth Interpolation (`road_graph.py`)**: Maps surface water depth onto arterial road segments and classifies risk (`SAFE`, `WATCH`, `HIGH`, `UNSAFE`).
   - **Multi-Criteria Dijkstra Pathfinding (`safe_route.py`)**: Optimizes travel time, flood risk penalty ($\lambda$), and model uncertainty ($\mu$), while enforcing hard blocks on `UNSAFE` corridors for emergency vehicles.

4. **Interactive GIS Command Center (`frontend/`)**:
   - High-performance 2D GIS visualization showing terrain contours, flood water heatmap, D8 flow vectors, drainage network nodes/pipes, road risk states, and live emergency routes.
   - Simulation playback controller (Play/Pause, Step, Reset, Timeline scrubber).
   - Real-time Mass Conservation diagnostic gauge (Live PASS/FAIL status).
   - One-click fault injection deck for live judge demonstrations (Sensor Spike, Heartbeat Drop, Drain Blockage).

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Dependencies: `pip install fastapi uvicorn pydantic pyyaml numpy scipy networkx pytest httpx`

### 2. Run the Server
```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8008 --reload
```

### 3. Open the Dashboard & API Docs
- **Interactive UI Dashboard**: [http://127.0.0.1:8008/static/index.html](http://127.0.0.1:8008/static/index.html)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8008/docs](http://127.0.0.1:8008/docs)

---

## 🧪 Automated Test Suite

Run the full automated test suite verifying all 6 core non-circular validation scenarios:
```powershell
python -m pytest tests/ -v
```

### Test Coverage:
1. `tests/test_conservation.py`: Mass balance $|\text{error}| \le 0.05\text{ m}^3$ across severe storms.
2. `tests/test_sensor_validation.py`: Physical range check and spike rejection.
3. `tests/test_fusion_convergence.py`: Bias correction convergence over $N$ timesteps.
4. `tests/test_degraded_mode.py`: Graceful fallback to model-only on sensor dropout.
5. `tests/test_routing_avoidance.py`: Emergency route diversion around flooded road segments.
6. `tests/test_end_to_end_replay.py`: Full end-to-end simulation from rain ingest to route dispatch.

---

## 🏛 Architecture Directory Layout

```
├── config/
│   └── defaults.yaml              # Centralized hyperparameters & tolerances
├── backend/
│   ├── api/                       # REST endpoints (rainfall, sensors, flood, routes, diagnostics)
│   ├── models/schemas.py          # Pydantic schemas
│   ├── services/                  # SimulationService orchestrator
│   └── app.py                     # FastAPI application
├── flood_engine/
│   ├── dem.py                     # Priority-flood fill & D8 flow directions
│   ├── runoff.py                  # SCS-CN cumulative/incremental runoff
│   ├── routing.py                 # Slope-weighted 2D surface routing
│   ├── drainage.py                # Graph topology & dynamic capacity factor
│   ├── storage.py                 # Synchronous mass-balanced cell state updates
│   └── conservation.py            # Water balance diagnostic logger
├── sensor/
│   ├── validation.py              # Range, rate-of-rise spike & heartbeat checks
│   ├── health.py                  # Sensor lifecycle state machine
│   ├── fusion.py                  # Exponential bias smoothing & IDW propagation
│   ├── anomaly.py                 # Rapid rise & drainage anomaly detection
│   └── confidence.py              # Composite confidence score
├── routing/
│   ├── road_graph.py              # Road segment graph & flood risk classifier
│   └── safe_route.py              # Multi-objective safe route Dijkstra planner
├── replay/
│   ├── rainfall/                  # Scripted rainfall storm profiles
│   ├── sensors/                   # Scripted ultrasonic/float sensor series
│   └── catchment_data.py          # Synthetic 20x20 DEM demonstration catchment
├── frontend/
│   ├── index.html                 # Command Center dashboard markup
│   ├── style.css                  # Dark-mode GIS styling
│   └── app.js                     # Canvas renderer & interactive controllers
└── tests/                         # Automated pytest validation suite
```
