# Layer 6 — Stateful Subsurface Drainage Network Specification

## Overview
Layer 6 couples surface inundation capture with a stateful, directed acyclic graph (DAG) representing underground stormwater infrastructure (inlets, manholes, conduits, and outfalls).

## Core Physical Balance Equation
[
S_{t+1} = S_t + I_t - O_t - Q_t
]
where:
- $S_t$: Stored volume in drainage nodes ($\text{m}^3$)
- $I_t$: External inflow captured from surface flood storage ($\text{m}^3$)
- $O_t$: Outlet discharge out of modeled boundaries ($\text{m}^3$)
- $Q_t$: Surcharge volume rejected / backed up onto the surface ($\text{m}^3$)

## Key Architectural Invariants
1. **Zero Mass Loss**: All untransmitted volume remaining above pipe capacity is retained in node storage up to `storage_capacity_m3`. Any excess above storage capacity is explicitly returned as `surcharge_volume_m3`.
2. **Synchronous Timestep Transmission**: Transmitted pipe volume becomes downstream node storage at the start of the next timestep, providing realistic multi-step transit time.
3. **Proportional Branching & Redistribution**: Outflows at junction nodes split proportionally according to effective edge capacity ($C_{\text{eff}} = C_{\text{base}} \times f$).
4. **Degradation & Blockage**: Each pipe accepts a dynamic capacity factor $0 \le f \le 1.0$.
