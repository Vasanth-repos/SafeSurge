# Layer 10 — Flood Risk Classification & Spatial Forecast State Engine

## Overview
Layer 10 transforms modeled flood depths (cm) into prototype risk states (`SAFE`, `WATCH`, `HIGH`, `UNSAFE`) across spatial computational cells and road networks while preserving data quality, timing context (reference, valid, and lead times), and provenance.

## Core Classification Rules
Based on configured threshold profile (default `prototype_v1`):
- $h < 5.0\text{ cm} \Rightarrow \text{SAFE}$
- $5.0\text{ cm} \le h < 15.0\text{ cm} \Rightarrow \text{WATCH}$
- $15.0\text{ cm} \le h < 25.0\text{ cm} \Rightarrow \text{HIGH}$
- $h \ge 25.0\text{ cm} \Rightarrow \text{UNSAFE}$

## Timing Context
- **Reference Time ($t_{\text{ref}}$)**: Time when nowcast model run was initialized.
- **Valid Time ($t_{\text{valid}}$)**: Time for which the forecast prediction applies.
- **Lead Time**: $\Delta t = t_{\text{valid}} - t_{\text{ref}}$ (e.g. $+30\text{ min}$, $+60\text{ min}$).

## Key Architectural Principles
1. **Separation of Risk & Data Quality**: Missing data or unmodeled road segments produce `data_status=NO_DATA` and `risk_state=null`, never erroneously falling back to `SAFE`.
2. **Partial Coverage Transparency**: Partial road overlays preserve both the weighted depth and coverage fraction without artificially altering the classification.
3. **Read-Only Hydrologic State**: Layer 10 strictly consumes depth values and does not mutate physical surface or drainage storage.
