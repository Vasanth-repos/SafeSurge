# Layer 11–12 — Sensor Telemetry Measurement & Validation Subsystem

## Overview
Layers 11–12 establish a deterministic boundary between physical/simulated sensor hardware (ESP32 ultrasonic distance burst + float contact switch) and the flood intelligence engine.

## Layer Responsibilities
- **Layer 11 (Ultrasonic & Float Measurement)**: Echo burst sampling (5 pulses), outlier filtering, median distance extraction, and conversion to water level ($L = H_{\text{ref}} - D$) without silent clamping.
- **Layer 12 (Validation & Sensor Health)**: Identity checking, timestamp ordering, sequence tracking, physical bounds checking, rate-of-rise validation against previous *accepted* readings, float switch consistency, and device connectivity state machine (`ONLINE`, `STALE`, `OFFLINE`, `INVALID`).

## Canonical Anomaly Filtering Gate
When presented with the step sequence:
```text
10 cm -> ACCEPTED
11 cm -> ACCEPTED
12 cm -> ACCEPTED
90 cm -> REJECTED (RATE_SPIKE)
13 cm -> ACCEPTED (evaluated against 12 cm baseline)
```
Device connectivity remains `ONLINE` throughout, preventing isolated telemetry glitches from marking operational nodes as dead or corrupting the flood model.
