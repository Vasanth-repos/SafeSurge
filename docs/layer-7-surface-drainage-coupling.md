# Layer 7 — Surface ↔ Drainage Coupling Specification

## Overview
Layer 7 orchestrates the bidirectional mass-conserving exchange between 2D surface overland flow (Layer 5) and the 1D underground pipe drainage network (Layer 6).

## Key Architectural Responsibilities
- **Surface Inundation Capture**: Quantifies water captured into stormwater curb inlets and grated catch basins ($D = \min(S_{\text{avail}}, C_{\text{eff}} \Delta t)$).
- **Proportional Multi-Inlet/Cell Allocation**: Distributes capacity proportionally when multiple cells feed one inlet, or multiple inlets drain a single ponding depression.
- **One-Timestep Delayed Surcharge**: Prevents unphysical algebraic feedback loops by queuing subsurface surcharge generated at timestep $t$ as available surface water at timestep $t+1$.
- **System-Wide Mass Conservation**:
  [
  \sum R_{\text{cum}} = S_{\text{surface}} + S_{\text{drainage}} + S_{\text{pending\_surcharge}} + B_{\text{surface}} + O_{\text{outlet}}
  ]
  where internal capture and surcharge exchanges cancel out identically.
