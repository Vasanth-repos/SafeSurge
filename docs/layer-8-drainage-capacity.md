# Layer 8 — Controlled Drainage Capacity Scenario Specification

## Overview
Layer 8 introduces deterministic, time-varying drainage capacity scenario assumptions ($C_{\text{eff}}(t) = C_0 \times F(t)$) without mutating the underlying physical network topology or claiming unverified real-time sensor blockage detection.

## Core Formulation
[
C_{\text{eff}}(t) = C_0 \times F(t)
]
where:
- $C_0$: Immutable base physical conduit capacity ($\text{m}^3/\text{s}$)
- $F(t) \in [0, 1]$: Scenario capacity factor at timestamp $t$
- $C_{\text{eff}}(t)$: Effective conduit throughput capacity ($\text{m}^3/\text{s}$)

## Capacity Status Classifications
- `NORMAL`: $F \ge 0.8$
- `REDUCED`: $0.5 \le F < 0.8$
- `SEVERE`: $F < 0.5$

## Key Architectural Principles
1. **Explicit `SCENARIO` Mode**: Prevents synthetic assumptions from being conflated with live sensor measurements.
2. **Immutable Base Geometry**: Conduit base capacity $C_0$ is never modified in-place; factors are applied dynamically per timestep.
3. **No Surcharge Duplication**: Layer 6 handles all physical pipe storage, routing, and surcharge calculations; Layer 8 only adjusts effective capacities.
4. **Conservation of Mass**: Degraded throughput changes where water is stored (subsurface vs overland ponding), while total mass is strictly conserved.
