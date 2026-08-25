# Layer 9 — Water Depth Engine & Spatial Road Inundation Field

## Overview
Layer 9 performs the deterministic transformation from 2D surface flood storage ($S_i$, $\text{m}^3$) into cell-average depth fields ($h_i = S_i / A_i$) and calculates area-weighted road flood inundation ($h_r$) using projected GIS geometries.

## Mathematical Formulations

1. **Cell-Average Modeled Water Depth**:
   [
   h_i = \frac{S_i}{A_i} \quad (\text{m}), \quad h_{i, \text{cm}} = 100 \times h_i
   ]
   where:
   - $S_i$: Modeled surface water storage ($\text{m}^3$)
   - $A_i$: Authoritative computational cell geometric area ($\text{m}^2$)

2. **Area-Weighted Road Inundation Depth**:
   [
   h_r = \frac{\sum_i A_{ri} h_i}{\sum_i A_{ri}}
   ]
   where $A_{ri} = \text{Area}(\text{Road} \cap \text{Cell}_i)$.

3. **Spatial Coverage Ratio & Quality States**:
   [
   \text{Coverage} = \frac{\sum_i A_{ri}}{A_{\text{road}}}
   ]
   - `FULL`: $\text{Coverage} \ge 95\%$
   - `PARTIAL`: $0 < \text{Coverage} < 95\%$
   - `NO_COVERAGE`: $\text{Coverage} = 0$ (depth reported as `null` / `None`, not $0\text{ cm}$)

## Key Architectural Principles
- **Read-Only Hydrologic Invariant**: Layer 9 never mutates surface storage states.
- **Projected Metric CRS**: All buffer operations, polygon intersections, and area calculations occur strictly in projected metric coordinate systems (e.g. `EPSG:32644`).
- **No Sub-Cell Pretensions**: Cell depths represent cell-average depths, and road depths represent area-weighted estimates.
