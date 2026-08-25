"""
Unit & Integration Tests for 3-Hour Prediction Report Generation (.docx).
"""

import os
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from reporting.docx_generator import create_3hour_prediction_docx
from replay.scenarios import ScenarioRunner


def test_create_3hour_prediction_docx_direct():
    runner = ScenarioRunner(config_path="config.yaml")
    snapshots = runner.run("config/scenarios/storm_01.yaml")
    out_file = os.path.join("outputs", "reports", "test_report_3hr.docx")

    res_path = create_3hour_prediction_docx(
        snapshots=snapshots,
        scenario_id="storm_01",
        output_path=out_file,
    )

    assert os.path.exists(res_path)
    assert os.path.getsize(res_path) > 1000  # Non-empty valid docx file


def test_download_docx_api_endpoint():
    client = TestClient(app)
    response = client.get("/api/reports/download-docx?scenario_id=storm_01")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert len(response.content) > 1000
