# Technical Assumptions & System Boundaries

## 1. Prototype Assumptions

- **Rainfall Ingestion**: Provided through standard rainfall grid replay scenarios (`replay/rainfall/*.json`), not a live radar feed.
- **Runoff Estimation**: SCS-CN is a lightweight cumulative-P / incremental-Q runoff model parameterized by land-use Curve Number, not an operational calibrated hydrodynamic solver.
- **Antecedent Soil Moisture**: Fixed for the duration of the scenario.
- **Surface Routing**: D8 determines topological flow direction only; a slope-weighted fraction rule ($f_i = \text{clip}(k \sqrt{s_i} \Delta t, 0, f_{max})$) approximates transport between cells.
- **Cell Storage**: Grid-cell storage balance ($S_{t+1} = \max(0, S_t + I_t - O_t - D_t)$) approximates flood accumulation.
- **Drainage Capacity**: Simplified dynamic capacity factor model ($F_t \in [1.0, 0.8, 0.6, 0.3]$). Blockage is modeled as reduced effective intake capacity.
- **Sensor Coverage**: Sparse ultrasonic/float nodes do not provide complete spatial ground truth; unsensed cells rely on spatial inverse distance weighted (IDW) bias propagation.
- **Road Risk**: Road segment flood depth is sampled/interpolated from nearby grid cells.
- **Validation**: Pipeline and mass conservation diagnostics ($|\text{balance\_error}| \le 0.05\text{ m}^3$), sensor fault injection, and routing diversion tests.

---

## 2. Explicitly Out of Scope

| Component | Status | Rationale |
|---|---|---|
| Live IMD Radar / Satellite Feeds | Out of Scope | External dependency; prototype uses standardized rainfall-grid replay interface. |
| City-Wide Deployment | Out of Scope | Prototype focuses on small, bounded, high-resolution demonstration catchment. |
| Full 2D Shallow-Water Hydrodynamics | Out of Scope | 2D Saint-Venant solvers are too computationally heavy for 60s live nowcasting without specialized GPU clusters. |
| Operational Drainage Control | Out of Scope | System provides situational awareness and nowcasting, not active SCADA valve actuation. |
| Field-Validated Predictive Accuracy | Out of Scope | Validation is pipeline, synthetic fault-injection, and mass conservation based. |
| Automatic Blockage Confirmation | Out of Scope | Anomalies are flagged as *"Possible drainage capacity anomaly"*, never claimed as physical blockage detection. |
| Production Emergency Dispatch | Out of Scope | Demonstration pathfinder showcasing flood-aware Dijkstra routing. |
