"""
Fusion Subsystem (Layers 13–15):
Temporal residual bias estimation, spatial inverse-distance correction,
and independent multi-factor confidence estimation.
"""

from fusion.bias import SensorBiasEstimator, calculate_residual, update_ewma_bias
from fusion.confidence import (
    ConfidenceEstimator,
    calculate_agreement,
    calculate_coverage,
    calculate_history_factor,
)
from fusion.history import SensorHistoryTracker
from fusion.matching import match_sensor_to_model
from fusion.models import (
    CellConfidence,
    FusedCellResult,
    FusionStepResult,
    ObservationHistoryRecord,
    SensorBiasState,
    SensorObservation,
)
from fusion.pipeline import FusionPipeline
from fusion.spatial import SpatialBiasCorrector, calculate_freshness

__all__ = [
    "CellConfidence",
    "ConfidenceEstimator",
    "FusedCellResult",
    "FusionPipeline",
    "FusionStepResult",
    "ObservationHistoryRecord",
    "SensorBiasEstimator",
    "SensorBiasState",
    "SensorHistoryTracker",
    "SensorObservation",
    "SpatialBiasCorrector",
    "calculate_agreement",
    "calculate_coverage",
    "calculate_freshness",
    "calculate_history_factor",
    "calculate_residual",
    "match_sensor_to_model",
    "update_ewma_bias",
]
