# Hackathon Live Demo Script (4.5 Minutes)

Rehearsed happy path for demonstrating the Urban Flood Nowcasting & Response System to judges.

---

## ⏱ Demo Sequence

### 0:00 — Baseline & Catchment Overview
- **Action:** Open Dashboard (`http://127.0.0.1:8008/static/index.html`).
- **Narrative:** *"This is our selected urban catchment (200m × 200m). Notice the DEM elevation terrain sloping from the northwest ridge down into the central drainage valley, the underground pipe network with 11 inlets, and our deployed ultrasonic/float sensors."*

### 0:30 — Storm Onset (Replay Trigger)
- **Action:** Select `Cloudburst Flash Flood (60mm/hr)` from Scenario dropdown, click **▶ Play** or **Step Next**.
- **Narrative:** *"A convective cloudburst begins. Rainfall is ingested per timestep. The SCS-CN engine converts cumulative precipitation into incremental runoff without resetting state."*

### 1:00 — Surface Runoff & D8 Transport
- **Action:** Toggle **D8 Flow Vectors** layer.
- **Narrative:** *"Surface routing transfers water downstream based on slope gradients. Water accumulates in the low-lying valley corridor and flows toward the drainage inlets."*

### 1:30 — Drainage Stress & Blockage Injection
- **Action:** Click **🚫 Choke Inlet #3 (Cap to 30%)** in the Fault Injection deck.
- **Narrative:** *"We simulate a partial drainage capacity degradation at Inlet #3. Notice surface accumulation rapidly building in the low basin as effective capacity drops."*

### 2:00 — Real-Time Sensor Telemetry
- **Action:** Point to the Sensor Telemetry card on the right panel.
- **Narrative:** *"Ultrasonic sensor S03 reports rising water levels (44 cm). Float switch activates, providing binary physical redundancy."*

### 2:30 — Sensor-Model Fusion & Spatial Bias Propagation
- **Action:** Point to the cell depth and bias indicators.
- **Narrative:** *"The model was predicting 28 cm, while the sensor observed 44 cm. Exponential smoothing updates local bias, which is propagated across unsensed neighboring cells via inverse distance weighting."*

### 3:00 — Road Network Vulnerability & Risk Classification
- **Action:** Highlight the red/orange road segments on the map.
- **Narrative:** *"Surface flood depths are mapped to the road network. Avenue segments passing through the central basin exceed 30 cm depth and are classified as UNSAFE."*

### 3:30 — Emergency Safe Routing
- **Action:** Select Origin `J1 (NW)`, Destination `J16 (SE)`, Mode `🚑 Emergency Response Vehicle`, click **⚡ Calculate Safe Corridor**.
- **Narrative:** *"The multi-criteria routing engine assigns infinite penalty to UNSAFE roads, automatically routing emergency responders along elevated ridge avenues with guaranteed clearance."*

### 4:00 — Fault Injection: Sensor Disconnect (Degraded Mode)
- **Action:** Click **🔌 Disconnect Sensor #2 (Offline)**.
- **Narrative:** *"Sensor 2 drops heartbeats and transitions to OFFLINE. The system continues seamlessly in degraded mode using the physical model, while the confidence indicator visibly drops to reflect increased uncertainty."*

### 4:30 — Mass Conservation Diagnostic Confirmation
- **Action:** Point to the top-right **MASS BALANCE: PASS (0.0000 m³)** indicator and the conservation breakdown stats.
- **Narrative:** *"Throughout the entire 10-minute storm evolution, Total Inflow strictly matches Surface Storage + Drained Water + Boundary Outflow. Mass balance error is zero."*
