"""
Layer 4 (Hardened) — Runoff Generation Engine (SCS-CN):
Converts deterministic rainfall depth into incremental direct runoff depth and volume per cell.
Enforces cumulative SCS-CN monotonicity, timestamp integrity, spatial land-use Curve Numbers,
and mass balance accounting.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path
import math
import json
import numpy as np

from flood_engine.config import load_config
from replay.rainfall import RainfallStep, SpatialRainfallStep


class CellRunoffState:
    def __init__(
        self,
        cell_id: str = "",
        curve_number: Optional[float] = None,
        cn_value: Optional[float] = None,
        area_m2: float = 100.0,
        land_use: str = "urban_composite",
        potential_retention_S: Optional[float] = None,
        initial_abstraction_Ia: Optional[float] = None,
        cumulative_rainfall_mm: float = 0.0,
        cumulative_runoff_mm: float = 0.0,
        incremental_runoff_mm: float = 0.0,
        runoff_volume_m3: float = 0.0,
    ):
        self.cell_id = cell_id
        cn = float(curve_number if curve_number is not None else (cn_value if cn_value is not None else 85.0))
        self.curve_number = cn
        self.cn_value = cn
        self.area_m2 = float(area_m2)
        self.land_use = str(land_use)
        self.potential_retention_S = float(potential_retention_S if potential_retention_S is not None else compute_scs_cn_potential_retention(cn))
        self.initial_abstraction_Ia = float(initial_abstraction_Ia if initial_abstraction_Ia is not None else (0.2 * self.potential_retention_S))
        self.cumulative_rainfall_mm = float(cumulative_rainfall_mm)
        self.cumulative_runoff_mm = float(cumulative_runoff_mm)
        self.incremental_runoff_mm = float(incremental_runoff_mm)
        self.runoff_volume_m3 = float(runoff_volume_m3)

    def compute_incremental_runoff(self, rainfall_mm: float) -> float:
        """Updates internal cumulative rainfall and returns incremental runoff volume in m³."""
        self.cumulative_rainfall_mm += float(rainfall_mm)
        curr_q = compute_cumulative_scs_cn_runoff(self.cumulative_rainfall_mm, self.potential_retention_S)
        delta_q = max(0.0, curr_q - self.cumulative_runoff_mm)
        self.cumulative_runoff_mm = curr_q
        self.incremental_runoff_mm = delta_q
        self.runoff_volume_m3 = (delta_q / 1000.0) * self.area_m2
        return self.runoff_volume_m3


@dataclass
class RunoffStep:
    timestamp_seconds: int
    timestep_seconds: int
    cell_states: Dict[str, CellRunoffState]
    total_rainfall_volume_m3: float
    total_runoff_volume_m3: float
    total_non_runoff_volume_m3: float


def compute_scs_cn_potential_retention(cn: float) -> float:
    """Computes potential maximum soil retention S in mm: S = (25400 / CN) - 254"""
    if not (0 < cn <= 100):
        raise ValueError(f"Curve Number must be in (0, 100], got {cn}")
    return (25400.0 / float(cn)) - 254.0


def compute_cumulative_scs_cn_runoff(cumulative_p_mm: float, potential_retention_s: float) -> float:
    """
    Computes total cumulative direct runoff Q(P) in mm from cumulative rainfall P:
    Ia = 0.2 * S
    Q(P) = 0 if P <= Ia else (P - Ia)^2 / (P - Ia + S)
    """
    if cumulative_p_mm <= 0.0:
        return 0.0

    ia = 0.2 * potential_retention_s
    if cumulative_p_mm <= ia:
        return 0.0

    numerator = (cumulative_p_mm - ia) ** 2
    denominator = cumulative_p_mm - ia + potential_retention_s
    q = numerator / max(1e-9, denominator)
    return min(float(cumulative_p_mm), max(0.0, float(q)))


class RunoffEngine:
    def __init__(
        self,
        cell_areas_m2: Dict[str, float],
        curve_numbers: Optional[Dict[str, float]] = None,
        land_uses: Optional[Dict[str, str]] = None,
        default_cn: Optional[float] = None,
        expected_timestep_seconds: int = 60,
        config_path: Optional[Union[str, Path]] = "config.yaml",
    ):
        self.cell_areas_m2 = {cid: float(a) for cid, a in cell_areas_m2.items()}
        for cid, a in self.cell_areas_m2.items():
            if a <= 0.0:
                raise ValueError(f"Cell area for {cid} must be positive, got {a}")

        # Resolve default CN from config or parameter
        if default_cn is None:
            if config_path and Path(config_path).exists():
                cfg = load_config(Path(config_path))
                self.default_cn = float(cfg.get("hydrology", {}).get("default_cn", 85.0))
                self.expected_timestep_seconds = int(cfg.get("simulation", {}).get("timestep_seconds", expected_timestep_seconds))
            else:
                self.default_cn = 85.0
                self.expected_timestep_seconds = expected_timestep_seconds
        else:
            self.default_cn = float(default_cn)
            self.expected_timestep_seconds = expected_timestep_seconds

        self.curve_numbers: Dict[str, float] = {}
        self.land_uses: Dict[str, str] = {}
        self.retention_S: Dict[str, float] = {}
        self.abstraction_Ia: Dict[str, float] = {}

        cn_map = curve_numbers or {}
        lu_map = land_uses or {}

        for cid in self.cell_areas_m2.keys():
            cn = float(cn_map.get(cid, self.default_cn))
            if not (0 < cn <= 100):
                raise ValueError(f"Curve Number for cell {cid} must be in (0, 100], got {cn}")
            self.curve_numbers[cid] = cn
            self.land_uses[cid] = lu_map.get(cid, "urban_composite")
            s = compute_scs_cn_potential_retention(cn)
            self.retention_S[cid] = s
            self.abstraction_Ia[cid] = 0.2 * s

        # State tracking per cell
        self.cumulative_rainfall_mm: Dict[str, float] = {cid: 0.0 for cid in self.cell_areas_m2.keys()}
        self.cumulative_runoff_mm: Dict[str, float] = {cid: 0.0 for cid in self.cell_areas_m2.keys()}
        self.cumulative_direct_runoff_volume_m3: float = 0.0
        self.cumulative_gross_rainfall_volume_m3: float = 0.0

        # Timestamp tracking
        self.last_timestamp_seconds: Optional[int] = None
        self.step_history: List[RunoffStep] = []

    def reset(self) -> None:
        """Resets all cumulative hydrological state and timestamp history."""
        for cid in self.cell_areas_m2.keys():
            self.cumulative_rainfall_mm[cid] = 0.0
            self.cumulative_runoff_mm[cid] = 0.0
        self.cumulative_direct_runoff_volume_m3 = 0.0
        self.cumulative_gross_rainfall_volume_m3 = 0.0
        self.last_timestamp_seconds = None
        self.step_history.clear()

    def validate_timestamp(self, timestamp_seconds: int) -> None:
        """Enforces strictly monotonic advancing timestamps matching configured spacing."""
        if not isinstance(timestamp_seconds, (int, float)) or math.isnan(timestamp_seconds) or math.isinf(timestamp_seconds):
            raise ValueError(f"Invalid timestamp: {timestamp_seconds}")
        t = int(timestamp_seconds)

        if self.last_timestamp_seconds is not None:
            if t <= self.last_timestamp_seconds:
                raise ValueError(
                    f"Timestamp must be strictly greater than previous timestamp ({self.last_timestamp_seconds}s), got {t}s."
                )
            dt = t - self.last_timestamp_seconds
            if dt != self.expected_timestep_seconds:
                raise ValueError(
                    f"Timestep spacing ({dt}s) does not match expected simulation timestep ({self.expected_timestep_seconds}s)."
                )

    def process_timestep(
        self,
        timestamp_seconds: int,
        rainfall_input: Union[float, Dict[str, float]],
    ) -> RunoffStep:
        """
        Executes one hydrological timestep:
        1. Validates timestamp progression
        2. Ingests scalar or spatial rainfall depth
        3. Updates cumulative rainfall P_t
        4. Calculates cumulative runoff Q(P_t) using SCS-CN
        5. Computes incremental runoff Delta Q_t and direct runoff volume V_t
        6. Updates mass balance
        """
        self.validate_timestamp(timestamp_seconds)
        t = int(timestamp_seconds)

        # Convert scalar or spatial rainfall to per-cell mapping
        rainfall_by_cell: Dict[str, float] = {}
        if isinstance(rainfall_input, (int, float)):
            val = float(rainfall_input)
            if math.isnan(val) or math.isinf(val) or val < 0.0:
                raise ValueError(f"Invalid rainfall value: {val}")
            for cid in self.cell_areas_m2.keys():
                rainfall_by_cell[cid] = val
        elif isinstance(rainfall_input, dict):
            # Strict cell check
            for cid in rainfall_input.keys():
                if cid not in self.cell_areas_m2:
                    raise ValueError(f"Unknown cell ID '{cid}' in rainfall input not found in model domain.")
            missing = set(self.cell_areas_m2.keys()) - set(rainfall_input.keys())
            if missing:
                raise ValueError(f"Missing rainfall input for {len(missing)} cells in model domain.")

            for cid, val in rainfall_input.items():
                if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val) or val < 0.0:
                    raise ValueError(f"Invalid rainfall value for cell {cid}: {val}")
                rainfall_by_cell[cid] = float(val)
        else:
            raise TypeError("rainfall_input must be a float/int or Dict[str, float].")

        cell_states: Dict[str, CellRunoffState] = {}
        step_rain_vol = 0.0
        step_runoff_vol = 0.0

        for cid in sorted(self.cell_areas_m2.keys()):
            p_inc = rainfall_by_cell[cid]
            area = self.cell_areas_m2[cid]
            s = self.retention_S[cid]
            cn = self.curve_numbers[cid]
            lu = self.land_uses[cid]

            # 1. Update cumulative precipitation
            prev_p = self.cumulative_rainfall_mm[cid]
            curr_p = prev_p + p_inc
            self.cumulative_rainfall_mm[cid] = curr_p

            # 2. Cumulative SCS-CN runoff
            prev_q = self.cumulative_runoff_mm[cid]
            curr_q = compute_cumulative_scs_cn_runoff(curr_p, s)
            self.cumulative_runoff_mm[cid] = curr_q

            # 3. Incremental direct runoff depth and volume
            delta_q = max(0.0, curr_q - prev_q)
            runoff_vol_m3 = (delta_q / 1000.0) * area
            rain_vol_m3 = (p_inc / 1000.0) * area

            step_rain_vol += rain_vol_m3
            step_runoff_vol += runoff_vol_m3

            cell_states[cid] = CellRunoffState(
                cell_id=cid,
                curve_number=cn,
                area_m2=area,
                land_use=lu,
                potential_retention_S=s,
                initial_abstraction_Ia=self.abstraction_Ia[cid],
                cumulative_rainfall_mm=curr_p,
                cumulative_runoff_mm=curr_q,
                incremental_runoff_mm=delta_q,
                runoff_volume_m3=runoff_vol_m3,
            )

        step_non_runoff_vol = max(0.0, step_rain_vol - step_runoff_vol)
        self.cumulative_gross_rainfall_volume_m3 += step_rain_vol
        self.cumulative_direct_runoff_volume_m3 += step_runoff_vol
        self.last_timestamp_seconds = t

        step_result = RunoffStep(
            timestamp_seconds=t,
            timestep_seconds=self.expected_timestep_seconds,
            cell_states=cell_states,
            total_rainfall_volume_m3=step_rain_vol,
            total_runoff_volume_m3=step_runoff_vol,
            total_non_runoff_volume_m3=step_non_runoff_vol,
        )
        self.step_history.append(step_result)
        return step_result

    def process_replay_step(self, step: Union[RainfallStep, SpatialRainfallStep]) -> RunoffStep:
        """Processes a single step emitted directly by Layer 3 RainfallReplay."""
        if isinstance(step, RainfallStep):
            return self.process_timestep(step.timestamp_seconds, step.rainfall_mm)
        elif isinstance(step, SpatialRainfallStep):
            return self.process_timestep(step.timestamp_seconds, step.cells)
        else:
            raise TypeError(f"Unsupported replay step type: {type(step)}")

    def mass_balance(self) -> Dict[str, float]:
        """Returns cumulative gross rainfall, direct runoff, and initial/soil abstraction volume."""
        non_runoff_vol = max(0.0, self.cumulative_gross_rainfall_volume_m3 - self.cumulative_direct_runoff_volume_m3)
        runoff_fraction = (
            self.cumulative_direct_runoff_volume_m3 / max(1e-9, self.cumulative_gross_rainfall_volume_m3)
            if self.cumulative_gross_rainfall_volume_m3 > 0 else 0.0
        )
        return {
            "cumulative_rainfall_volume_m3": round(self.cumulative_gross_rainfall_volume_m3, 6),
            "cumulative_direct_runoff_volume_m3": round(self.cumulative_direct_runoff_volume_m3, 6),
            "cumulative_non_runoff_volume_m3": round(non_runoff_vol, 6),
            "effective_runoff_fraction": round(runoff_fraction, 4),
            "is_conserved": self.cumulative_direct_runoff_volume_m3 <= self.cumulative_gross_rainfall_volume_m3 + 1e-9,
        }

    @classmethod
    def from_cell_properties_file(
        cls,
        cell_props_path: Union[str, Path],
        config_path: Union[str, Path] = "config.yaml",
    ) -> "RunoffEngine":
        """Loads spatial CN and land-use mapping from JSON dataset."""
        path = Path(cell_props_path)
        if not path.exists():
            raise FileNotFoundError(f"Cell properties file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cells_data = data.get("cells", data)
        areas = {}
        cns = {}
        lus = {}

        for cid, info in cells_data.items():
            if isinstance(info, dict):
                areas[cid] = float(info.get("area_m2", 100.0))
                cns[cid] = float(info.get("curve_number", 85.0))
                lus[cid] = str(info.get("land_use", "urban_composite"))
            else:
                areas[cid] = 100.0
                cns[cid] = float(info)
                lus[cid] = "urban_composite"

        return cls(
            cell_areas_m2=areas,
            curve_numbers=cns,
            land_uses=lus,
            config_path=config_path,
        )
