"""
Fusion Subsystem (Layers 13–15):
Temporal residual bias estimation, spatial inverse-distance correction,
and independent multi-factor confidence estimation.
"""

from fusion.models import (
    SensorObservation,
    SensorBiasState,
    ObservationHistoryRecord,
    CellConfidence,
    FusedCellResult,
    FusionStepResult,
)
from fusion.history import SensorHistoryTracker
from fusion.matching import match_sensor_to_model
from fusion.bias import calculate_residual, update_ewma_bias, SensorBiasEstimator
from fusion.spatial import calculate_freshness, SpatialBiasCorrector
from fusion.confidence import (
    calculate_coverage,
    calculate_agreement,
    calculate_history_factor,
    ConfidenceEstimator,
)
from fusion.pipeline import FusionPipeline

__all__ = [
    "SensorObservation",
    "SensorBiasState",
    "ObservationHistoryRecord",
    "CellConfidence",
    "FusedCellResult",
    "FusionStepResult",
    "SensorHistoryTracker",
    "match_sensor_to_model",
    "calculate_residual",
    "update_ewma_bias",
    "SensorBiasEstimator",
    "calculate_freshness",
    "SpatialBiasCorrector",
    "calculate_coverage",
    "calculate_agreement",
    "calculate_history_factor",
    "ConfidenceEstimator",
    "FusionPipeline",
]
