# SafeSurge (AURA-FLOOD) — Urban Hydrological Command Center

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![Pytest Tests](https://img.shields.io/badge/pytest-196%20passed-brightgreen.svg)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An autonomous, physics-informed hydrological nowcasting, real-time multi-station sensor fusion, mass-conserving drainage simulation, and risk-aware dynamic emergency routing system.

---

## 🚀 Quick Start Commands

### 1. Clone the Repository
```bash
git clone https://github.com/Vasanth-repos/SafeSurge.git
cd SafeSurge
```

### 2. Set Up Virtual Environment (Recommended)

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS (Bash):**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

*(Or install core dependencies directly):*
```bash
pip install fastapi uvicorn pydantic pyyaml numpy scipy networkx pytest httpx shapely pyproj python-docx
```

### 4. Start the Application Server
```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8008 --reload
```

---

## 🌐 Access Points & Endpoints

Once the server is running, access the services in your browser:

| Service | URL | Description |
| :--- | :--- | :--- |
| **Command Center GIS Dashboard** | [http://127.0.0.1:8008/](http://127.0.0.1:8008/) | Interactive 2D GIS visualization, dynamic routing, timeline player |
| **Static Dashboard Mirror** | [http://127.0.0.1:8008/static/index.html](http://127.0.0.1:8008/static/index.html) | Direct static assets mount |
| **Interactive API Documentation (Swagger)** | [http://127.0.0.1:8008/docs](http://127.0.0.1:8008/docs) | Live endpoint testing & OpenAPI schemas |
| **ReDoc API Specifications** | [http://127.0.0.1:8008/redoc](http://127.0.0.1:8008/redoc) | Clean API documentation reference |
| **Automated Diagnostic .docx Export** | [http://127.0.0.1:8008/api/reports/download-docx?scenario_id=storm_01](http://127.0.0.1:8008/api/reports/download-docx?scenario_id=storm_01) | Download nowcasting report (.docx format) |

---

## 🧪 Run Automated Tests

To execute the full automated test suite verifying all 196 unit, integration, mass balance, sensor fusion, and routing scenarios:

```bash
python -m pytest tests/ -v
```

### Key Verification Test Suites:
- `tests/test_all_10_scenarios.py`: Validates all 10 canonical storm and fault scenarios.
- `tests/test_conservation.py`: Mass balance invariant verification ($|\text{error}| \le 0.000001\text{ m}^3$).
- `tests/test_routing.py` & `test_routing_avoidance.py`: Multi-criteria Dijkstra emergency route diversion around flooded segments.
- `tests/test_sensor_validation.py` & `test_fault_injection.py`: Spike anomalies, rate-of-rise filters, and heartbeat loss fallback.
- `tests/test_fusion_convergence.py`: Spatial Kalman filter & IDW bias convergence over time.
- `tests/test_surface_drainage_coupling.py`: 2D Overland hydrodynamics coupled with subsurface culvert/pipe capacities.

---

## 🌟 System Features & Capabilities

1. **Hydrological Nowcasting Engine (`flood_engine/`, `replay/`)**:
   - **Pit-Fill & D8 Flow Direction**: Resolves topographical depressions and generates steepest-descent gravity routing vectors.
   - **SCS-CN Runoff Estimation**: Cumulative and incremental runoff volume modeling calibrated per land-use Curve Number.
   - **High-Contrast D8 Hydrodynamic Vectors**: Dynamic SVG flow arrows that follow the physical slope towards catchment sinks and drainage canals.
   - **Closed-Loop Mass Conservation**: Guarantees zero unphysical water loss/gain ($\Delta V = I - D - B - \Delta S \approx 0.000\text{ m}^3$).

2. **Multi-Station IoT Sensor Fleet (`sensors/`, `fusion/`)**:
   - **6 Ultrasonic Depth Monitoring Stations**: Distributed across high-ground origin, midtown basin, east lowland depression, west bypass, and south canal outfall.
   - **Spike Rejection & Rate-of-Rise Filtering**: Rejects unphysical ultrasonic noise while capturing authentic flash flood surges.
   - **Health State Machine**: Tracks sensor lifecycle transitions (`ONLINE` $\to$ `STALE` $\to$ `OFFLINE` $\to$ `INVALID`).
   - **Spatial Kalman & Gaussian Propagation**: Fuses sparse sensor observations with physical hydrodynamic predictions.

3. **Risk-Aware Dynamic Emergency Routing (`routing/`)**:
   - **Hard Physical Barrier Exclusion**: Roads with flood depths $\ge 25\text{ cm}$ (`UNSAFE`) are strictly excluded as impassable.
   - **Cost-Penalized Avoidance**: Roads with depths $15\text{–}25\text{ cm}$ (`HIGH`) incur a $+500\text{s}$ Dijkstra penalty, automatically diverting ambulances to safe high-ground bypasses.
   - **Live Map Route Corridor Glow**: Animated glowing route corridor polyline with vehicle dispatch marker rendered directly on the GIS map.

4. **Interactive Fault Injection Suite**:
   - One-click fault injection controls (`⚡ S001 Spike`, `🔌 Drop S001`, `🚧 Culvert Clog 70%`, `🔄 Reset`) with real-time UI/API responses.

---

## 🏛 Directory Layout

```
├── backend/
│   ├── api/                       # REST endpoints (dashboard state, sensors, reports, snapshots)
│   ├── models/schemas.py          # Pydantic schemas & data models
│   ├── services/                  # SnapshotService & SimulationManager
│   ├── static/                    # Frontend assets (index.html, app.css, app.js)
│   └── app.py                     # FastAPI application entrypoint
├── flood_engine/
│   ├── dem.py                     # Priority-flood fill & D8 flow directions
│   ├── runoff.py                  # SCS-CN runoff volume estimation
│   ├── routing.py                 # Slope-weighted 2D surface routing
│   ├── drainage.py                # Subsurface pipe network & inlet capacity
│   └── conservation.py            # Water mass balance diagnostic logger
├── sensors/
│   ├── registry.py                # Hardware sensor registry & YAML parser
│   ├── validation.py              # Range, rate-of-rise spike & heartbeat checks
│   ├── health.py                  # Sensor lifecycle state machine
│   └── ultrasonic.py              # Ultrasonic HC-SR04 & float switch simulation
├── fusion/
│   ├── pipeline.py                # Central sensor fusion orchestrator
│   ├── spatial.py                 # Inverse distance weighting (IDW) & Gaussian decay
│   ├── bias.py                    # Exponential bias smoothing
│   └── confidence.py              # Composite confidence scoring
├── routing/
│   ├── safe_route.py              # Multi-criteria Dijkstra safe route engine
│   └── road_graph.py              # Road risk classification (SAFE, WATCH, HIGH, UNSAFE)
├── replay/
│   ├── engine.py                  # Deterministic scenario replay orchestrator
│   └── faults.py                  # Fault injection definitions & schedules
├── data/
│   ├── sensors/registry.yaml      # Multi-station IoT hardware configurations
│   └── replay/                    # Synthetic rainfall & sensor timeseries
├── outputs/reports/               # Generated .docx nowcasting & incident reports
├── tests/                         # Full automated test suite (196 tests)
├── requirements.txt               # Python package dependencies
└── README.md                      # Project documentation & startup guide
```
