"""
Layer 3 (Hardened) — Rainfall Replay Engine:
Deterministic scalar and spatial precipitation replay with schema validation,
provenance fingerprinting, configuration timestep alignment, and physical unit conversions.
"""

import hashlib
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flood_engine.config import load_config


@dataclass(frozen=True)
class RainfallStep:
    minute: int
    timestamp_seconds: int
    rainfall_mm: float
    timestep_seconds: int


@dataclass(frozen=True)
class SpatialRainfallStep:
    timestamp_seconds: int
    timestep_seconds: int
    cells: dict[str, float]


def rainfall_mm_to_meters(rainfall_mm: float) -> float:
    """Converts rainfall depth from millimeters to meters: P_m = P_mm / 1000.0"""
    return float(rainfall_mm) / 1000.0


def rainfall_depth_to_volume_m3(rainfall_mm: float, area_m2: float) -> float:
    """
    Computes gross precipitation volume in cubic meters:
    V_rain = (rainfall_mm / 1000.0) * area_m2
    """
    return (float(rainfall_mm) / 1000.0) * float(area_m2)


def compute_file_sha256(path: Path) -> str:
    """Calculates SHA-256 fingerprint of raw file bytes."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_content_fingerprint(data: Any) -> str:
    """Calculates deterministic SHA-256 fingerprint of canonical JSON structure."""
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ScalarRainfallReplay:
    def __init__(
        self,
        steps: list[RainfallStep],
        timestep_seconds: int,
        source_sha256: str = "",
        content_fingerprint: str = "",
        schema_version: str = "rainfall-replay-v1",
    ):
        self.steps = steps
        self.timestep_seconds = timestep_seconds
        self.source_sha256 = source_sha256
        self.content_fingerprint = content_fingerprint
        self.schema_version = schema_version

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def duration_seconds(self) -> int:
        return self.step_count * self.timestep_seconds

    @property
    def total_rainfall_mm(self) -> float:
        return sum(s.rainfall_mm for s in self.steps)

    @property
    def max_timestep_rainfall_mm(self) -> float:
        return max((s.rainfall_mm for s in self.steps), default=0.0)

    @property
    def mean_timestep_rainfall_mm(self) -> float:
        return self.total_rainfall_mm / max(1, self.step_count)

    def replay(self) -> Iterator[RainfallStep]:
        """Pure deterministic generator yielding RainfallStep per timestep."""
        yield from self.steps

    @classmethod
    def load_from_dict(
        cls,
        data: dict[str, Any],
        expected_timestep_seconds: int | None = None,
        source_sha256: str = "",
    ) -> "ScalarRainfallReplay":
        """Validates schema and loads a ScalarRainfallReplay instance."""
        if not isinstance(data, dict):
            raise ValueError("Root of rainfall replay must be a JSON object.")

        schema = data.get("schema_version", "rainfall-replay-v1")
        if schema not in ("rainfall-replay-v1", "replay-v1"):
            raise ValueError(f"Unsupported schema version: '{schema}'")

        if "timestep_seconds" not in data:
            raise ValueError("Missing 'timestep_seconds' in rainfall replay.")

        ts_sec = data["timestep_seconds"]
        if not isinstance(ts_sec, (int, float)) or ts_sec <= 0:
            raise ValueError("timestep_seconds must be a positive integer.")
        ts_sec = int(ts_sec)

        if expected_timestep_seconds is not None and ts_sec != expected_timestep_seconds:
            raise ValueError(
                f"Rainfall replay timestep ({ts_sec}s) does not match configured simulation timestep ({expected_timestep_seconds}s)."
            )

        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or len(raw_steps) == 0:
            raise ValueError("Rainfall replay must contain a non-empty 'steps' array.")

        parsed_steps: list[RainfallStep] = []
        expected_minute = 1

        for idx, step_item in enumerate(raw_steps):
            if not isinstance(step_item, dict):
                raise ValueError(f"Step {idx} is not a valid JSON object.")

            minute = step_item.get("minute")
            if minute is None or not isinstance(minute, int) or minute != expected_minute:
                raise ValueError(f"Step {idx} has invalid or non-contiguous minute {minute}; expected {expected_minute}.")

            val = step_item.get("rainfall_mm")
            if val is None or not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"Step {minute} contains invalid non-numeric rainfall value: {val}")

            if val < 0.0:
                raise ValueError(f"Step {minute} has negative rainfall: {val}")

            t_sec = minute * ts_sec
            parsed_steps.append(
                RainfallStep(
                    minute=minute,
                    timestamp_seconds=t_sec,
                    rainfall_mm=float(val),
                    timestep_seconds=ts_sec,
                )
            )
            expected_minute += 1

        content_fp = compute_content_fingerprint(data)
        return cls(
            steps=parsed_steps,
            timestep_seconds=ts_sec,
            source_sha256=source_sha256,
            content_fingerprint=content_fp,
            schema_version=schema,
        )


class SpatialRainfallReplay:
    def __init__(
        self,
        steps: list[SpatialRainfallStep],
        timestep_seconds: int,
        source_sha256: str = "",
        content_fingerprint: str = "",
        schema_version: str = "spatial-rainfall-replay-v1",
    ):
        self.steps = steps
        self.timestep_seconds = timestep_seconds
        self.source_sha256 = source_sha256
        self.content_fingerprint = content_fingerprint
        self.schema_version = schema_version

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def replay(self) -> Iterator[SpatialRainfallStep]:
        yield from self.steps

    @classmethod
    def load_from_dict(
        cls,
        data: dict[str, Any],
        expected_timestep_seconds: int | None = None,
        valid_cell_ids: set[str] | None = None,
        strict_coverage: bool = False,
        source_sha256: str = "",
    ) -> "SpatialRainfallReplay":
        """Loads and validates a 2D spatial rainfall replay dataset."""
        if not isinstance(data, dict):
            raise ValueError("Root of spatial rainfall replay must be a JSON object.")

        schema = data.get("schema_version", "spatial-rainfall-replay-v1")
        if schema != "spatial-rainfall-replay-v1":
            raise ValueError(f"Unsupported spatial schema version: '{schema}'")

        ts_sec = int(data.get("timestep_seconds", 60))
        if expected_timestep_seconds is not None and ts_sec != expected_timestep_seconds:
            raise ValueError(
                f"Spatial rainfall replay timestep ({ts_sec}s) does not match configured simulation timestep ({expected_timestep_seconds}s)."
            )

        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or len(raw_steps) == 0:
            raise ValueError("Spatial rainfall replay must contain a non-empty 'steps' array.")

        parsed_steps: list[SpatialRainfallStep] = []
        for idx, s in enumerate(raw_steps):
            t_sec = int(s.get("timestamp", (idx + 1) * ts_sec))
            cells_map = s.get("cells", {})
            if not isinstance(cells_map, dict):
                raise ValueError(f"Step {idx} 'cells' must be a mapping of cell_id to rainfall_mm.")

            # Validate unknown cells
            if valid_cell_ids is not None:
                for cid in cells_map:
                    if cid not in valid_cell_ids:
                        raise ValueError(f"Unknown cell ID '{cid}' in spatial rainfall not found in computational grid.")

                # Strict coverage check
                if strict_coverage:
                    missing = valid_cell_ids - set(cells_map.keys())
                    if missing:
                        raise ValueError(f"Strict coverage failed: {len(missing)} grid cells missing spatial rainfall at step {idx}.")

            # Validate values & sort keys deterministically
            norm_cells: dict[str, float] = {}
            for cid in sorted(cells_map.keys()):
                val = cells_map[cid]
                if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val) or val < 0:
                    raise ValueError(f"Invalid rainfall value for cell {cid} at step {idx}: {val}")
                norm_cells[cid] = float(val)

            parsed_steps.append(
                SpatialRainfallStep(
                    timestamp_seconds=t_sec,
                    timestep_seconds=ts_sec,
                    cells=norm_cells,
                )
            )

        content_fp = compute_content_fingerprint(data)
        return cls(
            steps=parsed_steps,
            timestep_seconds=ts_sec,
            source_sha256=source_sha256,
            content_fingerprint=content_fp,
            schema_version=schema,
        )


def load_rainfall_replay(
    replay_path: str | Path,
    config_path: str | Path = "config.yaml",
    valid_cell_ids: set[str] | None = None,
    strict_coverage: bool = False,
) -> ScalarRainfallReplay | SpatialRainfallReplay:
    """
    Universal rainfall loader reading configuration timestep and validating schema,
    timestamps, and values.
    """
    path = Path(replay_path)
    if not path.exists():
        raise FileNotFoundError(f"Rainfall replay file not found: {path}")

    # Load configured simulation timestep
    cfg_path = Path(config_path)
    expected_ts = None
    if cfg_path.exists():
        cfg = load_config(cfg_path)
        expected_ts = cfg.get("simulation", {}).get("timestep_seconds", 60)

    # Calculate raw file hash
    file_sha = compute_file_sha256(path)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    schema = data.get("schema_version", "")
    if schema == "spatial-rainfall-replay-v1" or "cells" in (data.get("steps", [{}])[0]):
        return SpatialRainfallReplay.load_from_dict(
            data=data,
            expected_timestep_seconds=expected_ts,
            valid_cell_ids=valid_cell_ids,
            strict_coverage=strict_coverage,
            source_sha256=file_sha,
        )
    else:
        return ScalarRainfallReplay.load_from_dict(
            data=data,
            expected_timestep_seconds=expected_ts,
            source_sha256=file_sha,
        )
