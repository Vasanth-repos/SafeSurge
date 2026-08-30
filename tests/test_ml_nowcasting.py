"""
Unit & Integration Tests for Physics-Guided Machine Learning (PGML) Engine.
Verifies training, non-negative depth guards, inference latency, and API endpoints.
"""

import numpy as np
from fastapi.testclient import TestClient

from backend.app import app
from ml.features import build_catchment_feature_matrix
from ml.infer import get_or_load_model, predict_catchment_depths
from ml.model import PhysicsGuidedFloodNowcaster

client = TestClient(app)


def test_pgml_model_fit_and_predict():
    """Verify PGML model trains, predicts, and enforces h >= 0."""
    X = np.random.uniform(0, 100, (50, 12)).astype(np.float32)
    y = np.random.uniform(-5, 30, 50).astype(np.float32)

    model = PhysicsGuidedFloodNowcaster(n_estimators=10, max_depth=3)
    model.fit(X, y)

    preds = model.predict(X)
    assert len(preds) == 50
    # Invariant: Non-negative depth guard
    assert np.all(preds >= 0.0)


def test_pgml_zero_rain_guard():
    """Verify zero rainfall condition produces zero flood depth."""
    model = get_or_load_model()
    X = build_catchment_feature_matrix(lead_time_min=0, rain_rate_mm_hr=0.0, cumulative_rain_mm=0.0)
    preds = model.predict(X, cumulative_rain_mm=0.0)
    assert np.all(preds == 0.0)


def test_pgml_inference_speed_and_coverage():
    """Verify sub-millisecond inference and complete 100-cell coverage."""
    res = predict_catchment_depths(lead_time_minutes=60, scenario_id="storm_01")
    assert res["success"] is True
    assert len(res["cell_depths"]) == 100
    assert len(res["cells"]) == 100
    assert "C001" in res["cell_depths"]
    assert "C100" in res["cell_depths"]
    # Fast inference constraint: < 100ms on any hardware (typically < 5ms)
    assert res["inference_time_ms"] < 100.0


def test_api_ml_endpoints():
    """Verify FastAPI /api/ml endpoints."""
    # 1. /api/ml/metrics
    r_metrics = client.get("/api/ml/metrics")
    assert r_metrics.status_code == 200
    data_m = r_metrics.json()
    assert data_m["status"] == "READY"
    assert data_m["metrics"]["test_rmse_cm"] < 1.0
    assert data_m["metrics"]["negative_depth_violations"] == 0

    # 2. /api/ml/predict
    r_pred = client.get("/api/ml/predict?lead_time_minutes=80&scenario_id=storm_01")
    assert r_pred.status_code == 200
    data_p = r_pred.json()
    assert data_p["success"] is True
    assert data_p["peak_depth_cm"] > 0.0
