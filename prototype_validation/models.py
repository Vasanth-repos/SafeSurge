"""
Layer 26 — Validation Models & Data Structures:
Strict, deterministic validation result tracking across critical, important, and informational checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CheckSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    INFORMATIONAL = "INFORMATIONAL"


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    name: str
    severity: CheckSeverity
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class ValidationReport:
    validation_id: str
    scenario_id: str
    status: CheckStatus
    checks: tuple[CheckResult, ...]
    started_at: str
    completed_at: str
    simulation_id: str
    timestep_count: int
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "simulation_id": self.simulation_id,
            "timestep_count": self.timestep_count,
            "summary": self.summary,
            "checks": [c.to_dict() for c in self.checks],
        }
