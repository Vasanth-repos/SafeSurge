"""
SafeSurge — Physics-Guided Machine Learning (PGML) Engine.
Couples hydrodynamic physical invariants with fast statistical surrogate models
for sub-millisecond urban flood nowcasting.
"""

from ml.model import PhysicsGuidedFloodNowcaster
from ml.infer import predict_catchment_depths

__all__ = ["PhysicsGuidedFloodNowcaster", "predict_catchment_depths"]
