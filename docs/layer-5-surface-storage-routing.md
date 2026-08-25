# Layer 5 — Dynamic Surface Storage & D8 Routing Specification

## Overview
Layer 5 couples incremental runoff volume $\Delta V_t(\text{cell})$ from Layer 4 with the D8 flow topology from Layer 2 to simulate dynamic, time-evolving surface ponding and slope-weighted 2D routing.

## Hydrological Formulation
1. **Governing Water Balance**:
   [
   S_{t+1} = S_t + R_t + I_t - O_t - D_t
   ]
   where:
   - $S$: Active surface water storage ($\text{m}^3$)
   - $R$: Incremental direct surface runoff volume ($\text{m}^3$)
   - $I$: Upstream surface inflow from uphill D8 neighbors ($\text{m}^3$)
   - $O$: Surface outflow routed downhill or discharged to boundary ($\text{m}^3$)
   - $D$: Drainage network capture volume ($\text{m}^3$, $= 0$ in Layer 5, active in Layer 6)

2. **Synchronous Slope-Weighted Routing**:
   [
   f = \text{clip}\left(k \sqrt{s} \Delta t, 0, f_{\max}\right)
   ]
   [
   O = f \times (S_t + R_t), \quad O \le S_t + R_t
   ]
   where $k$ is an empirical prototype routing coefficient and $s$ is the dimensionless D8 slope ratio.

3. **Water Depth Computation**:
   [
   h_{t+1} = \frac{S_{t+1}}{A_{\text{effective}}}
   ]

4. **Depth Risk Classification**:
   - `NORMAL`: $< 5\text{ cm}$
   - `WARNING`: $5 - 15\text{ cm}$
   - `HAZARDOUS`: $15 - 30\text{ cm}$
   - `SEVERE`: $30 - 60\text{ cm}$
   - `CRITICAL`: $\ge 60\text{ cm}$

## Boundaries & Constraints
- Synchronous timesteps prevent instantaneous multi-cell propagation.
- Strict mass conservation: $\Delta \text{Storage} + \text{BoundaryDischarge} + \text{DrainageCapture} = \text{RunoffInput}$.
