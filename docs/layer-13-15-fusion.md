# Layers 13–15 — Sensor Fusion, Spatial Bias Correction & Confidence Subsystem

## Overview
Layers 13–15 establish a physically grounded, anti-circular sensor fusion subsystem that uses validated observations to estimate local temporal residuals, cautious spatial bias corrections, and transparent trust metrics without overwriting baseline flood physics.

## Architecture
```text
                     LAYER 9 Original Model Depth
                                  │
                                  ▼
                             ┌─────────┐
                             │ Layer 13│ Temporal Residual / EWMA Bias
                             └────┬────┘
                                  │ local bias
                                  ▼
                             ┌─────────┐
                             │ Layer 14│ Freshness/Quality Spatial Correction
                             └────┬────┘
                                  │
                                  ▼ Corrected Depth
      Original Model Depth ───────┤
                                  ▼
                             ┌─────────┐
                             │ Layer 15│ Anti-Circular Confidence (MAE vs Original)
                             └────┬────┘
                                  ▼
                      Depth + Confidence + Provenance
```

## Mathematical Formulations

1. **Residual Calculation & EWMA Bias (Layer 13)**:
   [
   e_t = H_{\text{obs}, t} - H_{\text{model}, t}
   ]
   [
   B_t = (\alpha q) e_t + (1 - \alpha q) B_{t-1} \quad \text{for } N \ge 3 \text{ and } |e_t| \le 20\text{ cm}
   ]
   [
   B_t = \text{clip}(B_t, -50, +50)
   ]

2. **Spatial Bias Propagation (Layer 14)**:
   [
   w_{ij} = \frac{F_j Q_j}{(d_{ij} + \epsilon)^p}, \quad F_j = \text{clip}\left(1 - \frac{\text{age}}{T_{\text{max}}}, 0, 1\right)
   ]
   [
   C_i = \text{clip}\left(\frac{\sum_j w_{ij} B_j}{\sum_j w_{ij}}, -15, +15\right)
   ]
   [
   H_{\text{corrected}} = \max(0, H_{\text{model}} + C_i)
   ]

3. **Anti-Circular Confidence Scoring (Layer 15)**:
   [
   C_{\text{base}} = 0.30 C_{\text{coverage}} + 0.30 C_{\text{freshness}} + 0.40 C_{\text{agreement}}
   ]
   where $C_{\text{agreement}} = \text{clip}(1 - \text{MAE} / S, 0, 1)$ evaluated against the **ORIGINAL MODEL** baseline $H_{\text{model}}$, and scaled by the history factor $H = \text{clip}(N / 10, 0, 1)$.

## Key Principles & Anti-Patterns Avoided
- **No Circular Self-Grading**: Agreement is never evaluated against the corrected output.
- **Large Residual Protection**: Anomalous spikes ($|e| > 20\text{ cm}$) are recorded in diagnostics but never corrupt the persistent EWMA bias state.
- **Zero Spatial Drift for Inactive Nodes**: Offline nodes have zero live spatial propagation.
