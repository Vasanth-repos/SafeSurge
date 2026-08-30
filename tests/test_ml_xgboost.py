"""
Unit and Integration Tests for AURA-FLOOD XGBoost Model Integration:
1. Model loading and persistence
2. Scenario-level XGBoost inference
3. Full catchment nowcasting
4. Independent validation dataset verification (MAE, RMSE, R^2, GO verdict)
5. FastAPI endpoints (/api/ml/scenario-predict, /api/ml/validate-xgboost, /api/ml/metrics)
"""

import os
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from ml.model import AuraFloodScenarioXGBoost, PhysicsGuidedFloodNowcaster
from ml.infer import predict_catchment_depths

client = TestClient(app)


def test_xgboost_artifact_exists():
    art_path = os.path.join("ml", "artifacts", "aura_flood_xgb.joblib")
    assert os.path.exists(art_path), f"Artifact missing: {art_path}"
    assert os.path.getsize(art_path) > 1000


def test_scenario_xgboost_inference():
    xgb_model = AuraFloodScenarioXGBoost()
    # Test nominal conditions
    depth_mm = xgb_model.predict_max_depth_mm(
        rainfall_intensity_mm_per_hr=50.0,
        duration_hr=3.0,
        timestep_min=10,
        drainage_degradation_factor=1.0,
    )
    assert isinstance(depth_mm, float)
    assert depth_mm >= 0.0

    # Severe storm with clogged culvert should produce higher depth
    depth_clogged = xgb_model.predict_max_depth_mm(
        rainfall_intensity_mm_per_hr=85.0,
        duration_hr=4.0,
        timestep_min=10,
        drainage_degradation_factor=0.2,
    )
    assert depth_clogged > depth_mm


def test_catchment_pgml_nowcaster_xgboost():
    res = predict_catchment_depths(lead_time_minutes=45, scenario_id="storm_01")
    assert res["success"] is True
    assert res["inference_time_ms"] < 20.0  # Fast sub-millisecond to low ms
    assert len(res["cells"]) == 100
    assert "AURA-FLOOD XGBoost" in res["model_architecture"]


def test_api_scenario_predict_endpoint():
    response = client.get(
        "/api/ml/scenario-predict?rainfall_intensity_mm_per_hr=60.0&duration_hr=3.0&drainage_degradation_factor=0.5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "predictions" in data
    assert "max_water_depth_sensor_mm" in data["predictions"]
    assert data["predictions"]["max_water_depth_sensor_mm"] >= 0.0


def test_api_validate_xgboost_endpoint():
    response = client.get("/api/ml/validate-xgboost")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["dataset_rows"] >= 15
    assert data["metrics"]["r2_score"] >= 0.90
    assert data["comparison_with_baseline"]["verdict"] == "GO"


def test_api_ml_metrics_xgboost_info():
    response = client.get("/api/ml/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "XGBoost" in data["model_architecture"]
    assert "independent_validation" in data
    assert data["independent_validation"]["verdict"] == "GO"
