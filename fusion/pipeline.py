"""
Layers 13–15 — Complete Sensor Fusion & Confidence Pipeline Orchestrator:
Coordinates matching, bias estimation, spatial correction, and confidence scoring.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from fusion.bias import SensorBiasEstimator
from fusion.confidence import ConfidenceEstimator
from fusion.history import SensorHistoryTracker
from fusion.matching import match_sensor_to_model
from fusion.models import (
    FusedCellResult,
    FusionStepResult,
    SensorObservation,
)
from fusion.spatial import SpatialBiasCorrector


class FusionPipeline:
    def __init__(
        self,
        bias_alpha: float = 0.3,
        minimum_bias_observations: int = 3,
        max_residual_for_bias_update_cm: float = 20.0,
        max_bias_cm: float = 50.0,
        max_observation_time_difference_seconds: int = 30,
        spatial_power: float = 2.0,
        spatial_max_distance_m: float = 1000.0,
        spatial_max_absolute_correction_cm: float = 15.0,
        minimum_model_depth_for_spatial_correction_cm: float = 1.0,
        confidence_weight_coverage: float = 0.30,
        confidence_weight_freshness: float = 0.30,
        confidence_weight_agreement: float = 0.40,
        agreement_scale_cm: float = 20.0,
        minimum_agreement_observations: int = 5,
        target_history_observations: int = 10,
        max_sensor_age_seconds: float = 180.0,
    ):
        self.max_time_diff_s = int(max_observation_time_difference_seconds)

        self.history_tracker = SensorHistoryTracker(max_history_steps=target_history_observations)

        self.bias_estimator = SensorBiasEstimator(
            bias_alpha=bias_alpha,
            minimum_bias_observations=minimum_bias_observations,
            max_residual_for_bias_update_cm=max_residual_for_bias_update_cm,
            max_bias_cm=max_bias_cm,
        )

        self.spatial_corrector = SpatialBiasCorrector(
            power=spatial_power,
            max_distance_m=spatial_max_distance_m,
            max_absolute_correction_cm=spatial_max_absolute_correction_cm,
            minimum_model_depth_for_spatial_correction_cm=minimum_model_depth_for_spatial_correction_cm,
            max_sensor_age_seconds=max_sensor_age_seconds,
        )

        self.confidence_estimator = ConfidenceEstimator(
            weight_coverage=confidence_weight_coverage,
            weight_freshness=confidence_weight_freshness,
            weight_agreement=confidence_weight_agreement,
            max_distance_m=spatial_max_distance_m,
            max_sensor_age_seconds=max_sensor_age_seconds,
            agreement_scale_cm=agreement_scale_cm,
            minimum_agreement_observations=minimum_agreement_observations,
            target_history_observations=target_history_observations,
        )

    def reset(self) -> None:
        self.history_tracker.reset()
        self.bias_estimator.reset()

    def step(
        self,
        timestamp_seconds: int,
        model_depth_cm_by_cell: Mapping[str, float],
        cell_coords_m_by_id: Mapping[str, tuple[float, float]],
        sensor_observations: Sequence[SensorObservation],
        sensor_coords_m_by_id: Mapping[str, tuple[float, float]],
    ) -> FusionStepResult:
        """
        Executes one full fusion timestep:
        1. Matches validated observations to model cells.
        2. Updates historical records and EWMA biases.
        3. Spatially propagates corrections across grid.
        4. Calculates independent multi-factor confidence.
        5. Packages FusedCellResult per cell.
        """
        t = int(timestamp_seconds)

        sensor_health_map: dict[str, str] = {}
        sensor_quality_map: dict[str, float] = {}
        sensor_last_updated_map: dict[str, int] = {}
        sensor_cell_id_map: dict[str, str] = {}

        # 1. Process and update each incoming observation
        for obs in sensor_observations:
            sid = obs.sensor_id
            sensor_health_map[sid] = obs.sensor_state
            sensor_quality_map[sid] = obs.quality
            sensor_last_updated_map[sid] = obs.timestamp_seconds
            sensor_cell_id_map[sid] = obs.cell_id

            matched, model_depth, residual = match_sensor_to_model(
                observation=obs,
                model_depth_cm_by_cell=model_depth_cm_by_cell,
                model_timestamp_seconds=t,
                max_time_difference_seconds=self.max_time_diff_s,
            )

            if matched and model_depth is not None:
                self.bias_estimator.update_observation(
                    observation=obs,
                    model_depth_cm=model_depth,
                    history_tracker=self.history_tracker,
                )

        # 2. Extract current sensor bias states
        sensor_states = {
            sid: self.bias_estimator.get_state(sid)
            for sid in sensor_coords_m_by_id.keys()
        }
        sensor_biases = {
            sid: state.bias_cm for sid, state in sensor_states.items()
        }

        # 3. Spatial Bias Correction
        corrections_map = self.spatial_corrector.correct_grid(
            model_depth_cm_by_cell=model_depth_cm_by_cell,
            cell_coords_m_by_id=cell_coords_m_by_id,
            sensor_states=sensor_states,
            sensor_coords_m_by_id=sensor_coords_m_by_id,
            sensor_health_by_id=sensor_health_map,
            sensor_qualities_by_id=sensor_quality_map,
            current_timestamp_seconds=t,
            sensor_cell_id_by_id=sensor_cell_id_map,
        )

        # 4. Multi-Factor Confidence Estimation
        confidence_map = self.confidence_estimator.estimate_grid(
            cell_coords_m_by_id=cell_coords_m_by_id,
            sensor_coords_m_by_id=sensor_coords_m_by_id,
            sensor_health_by_id=sensor_health_map,
            sensor_last_updated_by_id=sensor_last_updated_map,
            history_tracker=self.history_tracker,
            current_timestamp_seconds=t,
        )

        # 5. Assemble Fused Cell Results
        fused_cells: dict[str, FusedCellResult] = {}
        for cid, model_d in model_depth_cm_by_cell.items():
            corr, corrected_d = corrections_map.get(cid, (0.0, model_d))
            conf = confidence_map[cid]

            fused_cells[cid] = FusedCellResult(
                cell_id=cid,
                model_depth_cm=model_d,
                correction_cm=corr,
                corrected_depth_cm=corrected_d,
                confidence=conf,
            )

        return FusionStepResult(
            timestamp_seconds=t,
            cells=fused_cells,
            sensor_biases=sensor_biases,
        )

    @classmethod
    def load_from_config(cls, config_path: str | Path = "config.yaml") -> FusionPipeline:
        p = Path(config_path)
        if not p.exists():
            return cls()

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        f_cfg = data.get("fusion", {})
        s_cfg = f_cfg.get("spatial_correction", {})
        c_cfg = f_cfg.get("confidence", {})
        w_cfg = c_cfg.get("weights", {})

        return cls(
            bias_alpha=float(f_cfg.get("bias_alpha", 0.3)),
            minimum_bias_observations=int(f_cfg.get("minimum_bias_observations", 3)),
            max_residual_for_bias_update_cm=float(f_cfg.get("max_residual_for_bias_update_cm", 20.0)),
            max_bias_cm=float(f_cfg.get("max_bias_cm", 50.0)),
            max_observation_time_difference_seconds=int(f_cfg.get("max_observation_time_difference_seconds", 30)),
            spatial_power=float(s_cfg.get("power", 2.0)),
            spatial_max_distance_m=float(s_cfg.get("max_distance_m", 1000.0)),
            spatial_max_absolute_correction_cm=float(s_cfg.get("max_absolute_correction_cm", 15.0)),
            minimum_model_depth_for_spatial_correction_cm=float(f_cfg.get("minimum_model_depth_for_spatial_correction_cm", 1.0)),
            confidence_weight_coverage=float(w_cfg.get("coverage", 0.30)),
            confidence_weight_freshness=float(w_cfg.get("freshness", 0.30)),
            confidence_weight_agreement=float(w_cfg.get("agreement", 0.40)),
            agreement_scale_cm=float(c_cfg.get("agreement_scale_cm", 20.0)),
            minimum_agreement_observations=int(c_cfg.get("minimum_agreement_observations", 5)),
            target_history_observations=int(c_cfg.get("target_history_observations", 10)),
            max_sensor_age_seconds=float(c_cfg.get("max_sensor_age_seconds", 180.0)),
        )
