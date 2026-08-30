"""
Layer 8 — Drainage Capacity Scenario Module:
Enables time-varying drainage capacity assumptions (C_eff = C0 * F(t))
for resilience and stress-testing simulations without modifying base network geometry.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

EPSILON = 1e-12


def _validate_factor(
    value: float,
    name: str = "capacity_factor",
) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric.")

    try:
        val = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc

    if not math.isfinite(val):
        raise ValueError(f"{name} must be finite.")

    if not 0.0 <= val <= 1.0:
        raise ValueError(f"{name} must be in [0, 1].")

    return val


def effective_capacity_m3_s(
    base_capacity_m3_s: float,
    capacity_factor: float,
) -> float:
    """
    Computes effective capacity: C_eff = C0 * F
    Base capacity is strictly immutable.
    """
    if isinstance(base_capacity_m3_s, bool):
        raise ValueError("base_capacity_m3_s must be numeric.")

    base = float(base_capacity_m3_s)

    if not math.isfinite(base):
        raise ValueError("base_capacity_m3_s must be finite.")

    if base < 0:
        raise ValueError("base_capacity_m3_s must be >= 0.")

    factor = _validate_factor(capacity_factor)
    return base * factor


@dataclass(frozen=True)
class CapacityEvent:
    timestamp_seconds: int
    edge_ids: tuple[str, ...]
    capacity_factor: float

    def __post_init__(self):
        if (
            isinstance(self.timestamp_seconds, bool)
            or not isinstance(self.timestamp_seconds, int)
            or self.timestamp_seconds < 0
        ):
            raise ValueError("timestamp_seconds must be an integer >= 0.")

        if not self.edge_ids:
            raise ValueError("edge_ids cannot be empty.")

        cleaned = tuple(dict.fromkeys(self.edge_ids))

        if any(not edge_id for edge_id in cleaned):
            raise ValueError("edge_ids cannot contain empty IDs.")

        object.__setattr__(self, "edge_ids", cleaned)
        _validate_factor(self.capacity_factor)


class CapacityScenario:
    def __init__(
        self,
        scenario_id: str,
        name: str,
        edge_ids: Iterable[str],
        events: Iterable[CapacityEvent],
        description: str = "",
        mode: str = "SCENARIO",
    ):
        if not scenario_id:
            raise ValueError("scenario_id cannot be empty.")
        if not name:
            raise ValueError("name cannot be empty.")

        self.scenario_id = scenario_id
        self.name = name
        self.description = description
        self.mode = mode

        edges = tuple(dict.fromkeys(edge_ids))
        if not edges or any(not edge_id for edge_id in edges):
            raise ValueError("edge_ids must contain non-empty IDs.")

        self.edge_ids = edges
        edge_set = set(edges)

        ordered = tuple(sorted(events, key=lambda ev: ev.timestamp_seconds))
        seen = set()

        for event in ordered:
            unknown = set(event.edge_ids) - edge_set
            if unknown:
                raise ValueError(f"Scenario references unknown edges: {sorted(unknown)}")

            for edge_id in event.edge_ids:
                key = (event.timestamp_seconds, edge_id)
                if key in seen:
                    raise ValueError(
                        f"Duplicate capacity event for {edge_id} at t={event.timestamp_seconds}s."
                    )
                seen.add(key)

        self.events = ordered
        self._timestamps = tuple(event.timestamp_seconds for event in ordered)

    def factors_at(
        self,
        timestamp_seconds: int,
    ) -> dict[str, float]:
        if (
            isinstance(timestamp_seconds, bool)
            or not isinstance(timestamp_seconds, int)
            or timestamp_seconds < 0
        ):
            raise ValueError("timestamp_seconds must be an integer >= 0.")

        factors = {edge_id: 1.0 for edge_id in self.edge_ids}
        index = bisect_right(self._timestamps, timestamp_seconds)

        for event in self.events[:index]:
            for edge_id in event.edge_ids:
                factors[edge_id] = event.capacity_factor

        return factors

    def effective_capacities_at(
        self,
        timestamp_seconds: int,
        base_capacity_m3_s_by_edge: Mapping[str, float],
    ) -> dict[str, float]:
        expected = set(self.edge_ids)
        provided = set(base_capacity_m3_s_by_edge)

        if expected != provided:
            raise ValueError("base_capacity_m3_s_by_edge must contain exactly the scenario edge IDs.")

        factors = self.factors_at(timestamp_seconds)
        return {
            edge_id: effective_capacity_m3_s(
                base_capacity_m3_s_by_edge[edge_id],
                factors[edge_id],
            )
            for edge_id in self.edge_ids
        }


def capacity_status(
    capacity_factor: float,
) -> str:
    factor = _validate_factor(capacity_factor)
    if factor >= 0.8:
        return "NORMAL"
    if factor >= 0.5:
        return "REDUCED"
    return "SEVERE"


@dataclass(frozen=True)
class CapacityScenarioState:
    timestamp_seconds: int
    scenario_id: str
    mode: str
    capacity_factor_by_edge: dict[str, float]
    effective_capacity_m3_s_by_edge: dict[str, float]

    def __post_init__(self):
        if self.mode != "SCENARIO":
            raise ValueError("Layer 8 states must use mode='SCENARIO'.")


def build_state(
    scenario: CapacityScenario,
    timestamp_seconds: int,
    base_capacity_m3_s_by_edge: Mapping[str, float],
) -> CapacityScenarioState:
    factors = scenario.factors_at(timestamp_seconds)
    effective = scenario.effective_capacities_at(
        timestamp_seconds,
        base_capacity_m3_s_by_edge,
    )
    return CapacityScenarioState(
        timestamp_seconds=timestamp_seconds,
        scenario_id=scenario.scenario_id,
        mode="SCENARIO",
        capacity_factor_by_edge=factors,
        effective_capacity_m3_s_by_edge=effective,
    )


def utilization(
    transmitted_volume_m3: float,
    effective_capacity_m3_s: float,
    dt_seconds: float,
) -> float:
    if transmitted_volume_m3 < 0:
        raise ValueError("transmitted_volume_m3 must be >= 0.")
    if effective_capacity_m3_s < 0:
        raise ValueError("effective_capacity_m3_s must be >= 0.")
    if dt_seconds <= 0:
        raise ValueError("dt_seconds must be > 0.")

    capacity_volume = effective_capacity_m3_s * dt_seconds
    if capacity_volume <= EPSILON:
        return 1.0 if transmitted_volume_m3 > EPSILON else 0.0

    return min(1.0, max(0.0, transmitted_volume_m3 / capacity_volume))


def load_capacity_scenario(
    path: str | Path,
    known_edge_ids: Iterable[str] | None = None,
) -> CapacityScenario:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Capacity scenario file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = []
    for ev in data.get("events", []):
        events.append(
            CapacityEvent(
                timestamp_seconds=int(ev["timestamp_seconds"]),
                edge_ids=tuple(ev["edge_ids"]),
                capacity_factor=float(ev["capacity_factor"]),
            )
        )

    edges = data.get("affected_edges", [])
    if known_edge_ids:
        # Include all known edges in network so unaffected edges are also tracked
        edges = list(dict.fromkeys(list(edges) + list(known_edge_ids)))

    return CapacityScenario(
        scenario_id=data.get("scenario_id", "scenario_01"),
        name=data.get("name", "Drainage Capacity Scenario"),
        edge_ids=edges,
        events=events,
        description=data.get("description", ""),
        mode=data.get("mode", "SCENARIO"),
    )
