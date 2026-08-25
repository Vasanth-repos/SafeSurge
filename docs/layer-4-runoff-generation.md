# Layer 4 — Runoff Generation Engine Specification (SCS-CN)

## Overview
Layer 4 transforms input rainfall depth $P(t, \text{cell})$ into incremental direct surface runoff volume $\Delta V_t(\text{cell})$ using the Soil Conservation Service Curve Number (SCS-CN) method.

## Hydrological Formulation
1. **Potential Soil Retention $S$ (mm)**:
   [
   S = \frac{25400}{CN} - 254
   ]
2. **Initial Abstraction $I_a$ (mm)**:
   [
   I_a = 0.2 S
   ]
3. **Cumulative Direct Runoff $Q(P_t)$ (mm)**:
   [
   Q(P_t) =
   \begin{cases}
   0 & P_t \le I_a \\
   \frac{(P_t - I_a)^2}{P_t - I_a + S} & P_t > I_a
   \end{cases}
   ]
4. **Incremental Runoff Depth $\Delta Q_t$ (mm)**:
   [
   \Delta Q_t = \max(0.0, Q(P_t) - Q(P_{t-1}))
   ]
5. **Incremental Direct Runoff Volume $V_t$ ($\text{m}^3$)**:
   [
   V_t = \frac{\Delta Q_t}{1000} \times A_{\text{cell}}
   ]

## Key Modeling Assumptions & Boundaries
- **Prototype Approximation**: SCS-CN is used as an established first-order runoff approximation.
- **Fixed Effective CN**: The effective Curve Number is fixed during a storm event; antecedent moisture is not dynamically simulated in this MVP layer.
- **Layer Separation**: Layer 4 **does not** perform D8 surface routing, does not calculate flood depth, and does not model underground drainage hydraulics.
