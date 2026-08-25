# Layers 16–19 — Anomaly Engine, Road Exposure & Dynamic Emergency Routing Subsystem

## Overview
Layers 16–19 finalize the end-to-end operational intelligence stack:
- **Layer 16 (Anomaly Detection)**: Evaluates multi-source diagnostic anomalies (rate-of-rise surges, anti-circular model disagreements, sensor contact inconsistencies, and unexpected drainage capacity failures).
- **Layer 17 (Road Exposure & Risk)**: Uses spatial STRtree indexing to project cell-average depths onto road GIS centerlines using intersection exposure weighting.
- **Layer 18 (Dynamic Safe Routing)**: Evaluates directed Dijkstra shortest paths using dynamic flood risk penalties and uncertainty weighting, with automated unsafe corridor blocking and route explanation.
- **Layer 19 (FastAPI Orchestrator & Snapshot Store)**: Exposes clean REST API contracts with time-indexed immutable snapshots and concurrency protections.

## Pipeline Architecture
```text
FLOOD ENGINE / FUSION
         │
         ▼
┌──────────────────┐
│  Layer 16        │ Multi-source anomaly assessment (Rapid Rise, Disagreement, Capacity Anomaly)
│  Anomaly Engine  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Layer 17        │ STRtree road-cell exposure & weighted depth
│  Road Risk       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Layer 18        │ Dynamic policy impedance: Cost = TravelTime + RiskPenalty + mu*(1-Confidence)
│  Safe Routing    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Layer 19        │ REST API endpoints & Immutable Simulation Snapshots
│  FastAPI Backend │
└──────────────────┘
```

## Master Routing Adaptation Benchmark
```text
Initial (Dry / Low Water):
A ──[R001]──> B ──[R002]──> D  (Optimal travel time: 120s)

Peak Flood (R002 Inundated >= 25 cm -> UNSAFE):
R002 blocked -> Dynamically switches to safe corridor:
A ──[R003]──> C ──[R004]──> D  (Travel time: 120s, R002 recorded in avoided_roads)
```
