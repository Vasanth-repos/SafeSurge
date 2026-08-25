# Layer 3 — Rainfall Replay Specification & Contract

## Overview
Layer 3 provides deterministic, reproducible precipitation drivers for the urban flood nowcasting simulation. It decouples raw meteorological/radar input from the hydrological runoff engine.

## Key Contracts
1. **Simulation Timestep Alignment**:
   All rainfall series validate against `config.yaml` (`simulation.timestep_seconds: 60`).
2. **Units & Semantics**:
   - `rainfall_mm`: Depth of precipitation accumulated *during that single timestep* (not mm/hour).
   - `RainfallStep(minute, timestamp_seconds, rainfall_mm, timestep_seconds)`
   - `SpatialRainfallStep(timestamp_seconds, timestep_seconds, cells)`
3. **Reproducibility & Provenance**:
   - Every replay computes a `source_sha256` byte hash and canonical `content_fingerprint`.
4. **Physical Volume Helper**:
   [
   V_{rain} = \frac{P_{mm}}{1000} \times A_{m^2}
   ]
5. **Separation of Concerns**:
   Layer 3 contains **no hydrologic runoff equations (SCS-CN)** and **no D8 routing**; it only supplies $P(t, \text{cell})$.
