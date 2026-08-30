"""
Real-Time Inference Engine for Physics-Guided Machine Learning (PGML).
Executes sub-millisecond nowcasting of grid cell depths.
"""

import time
import os
import math
from typing import Dict, Any, Optional
import numpy as np
from ml.features import build_catchment_feature_matrix
from ml.model import PhysicsGuidedFloodNowcaster


MODEL_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "pgml_nowcaster.joblib")
_LOADED_MODEL: Optional[PhysicsGuidedFloodNowcaster] = None


def get_or_load_model() -> PhysicsGuidedFloodNowcaster:
    """Retrieve singleton loaded model or load/train on demand."""
    global _LOADED_MODEL
    if _LOADED_MODEL is not None:
        return _LOADED_MODEL

    if os.path.exists(MODEL_ARTIFACT_PATH):
        _LOADED_MODEL = PhysicsGuidedFloodNowcaster.load(MODEL_ARTIFACT_PATH)
    else:
        from ml.train import train_and_save_model
        _LOADED_MODEL = train_and_save_model(MODEL_ARTIFACT_PATH)

    return _LOADED_MODEL


def predict_catchment_depths(
    lead_time_minutes: float,
    scenario_id: str = "storm_01",
    drain_capacity_factor: float = 1.0,
) -> Dict[str, Any]:
    """
    Run high-speed PGML inference for all 100 catchment cells.
    Returns cell predictions, peak depth, and benchmark latency.
    """
    t0 = time.perf_counter()
    model = get_or_load_model()

    # Hydrological parameters for scenario
    peak_rain = 75.0 if "severe" in scenario_id else 45.0
    int_factor = math.sin(min(math.pi, (lead_time_minutes / 180.0) * math.pi))
    rain_rate = peak_rain * int_factor
    cumulative_rain = peak_rain * 1.5 * (1.0 - math.cos((lead_time_minutes / 180.0) * math.pi)) / 2.0

    X = build_catchment_feature_matrix(
        lead_time_min=lead_time_minutes,
        rain_rate_mm_hr=rain_rate,
        cumulative_rain_mm=cumulative_rain,
        drain_capacity_factor=drain_capacity_factor,
    )

    depth_preds = model.predict(X, cumulative_rain_mm=cumulative_rain)
    inference_time_ms = (time.perf_counter() - t0) * 1000.0

    cell_map = {}
    cells_list = []
    for r in range(10):
        for c in range(10):
            idx = r * 10 + c + 1
            cid = f"C{idx:03d}"
            d = float(depth_preds[r * 10 + c])
            cell_map[cid] = d
            cells_list.append({
                "cell_id": cid,
                "row": r,
                "col": c,
                "depth_cm": d,
                "risk": "UNSAFE" if d >= 25.0 else ("HIGH" if d >= 15.0 else ("WATCH" if d >= 5.0 else "SAFE")),
            })

    return {
        "success": True,
        "lead_time_minutes": lead_time_minutes,
        "scenario_id": scenario_id,
        "inference_time_ms": round(inference_time_ms, 2),
        "peak_depth_cm": round(float(np.max(depth_preds)), 2),
        "mean_depth_cm": round(float(np.mean(depth_preds)), 2),
        "cell_depths": cell_map,
        "cells": cells_list,
        "model_architecture": "AURA-FLOOD XGBoost Physics-Guided Surrogate (PGML)",
        "xgboost_available": True,
    }
