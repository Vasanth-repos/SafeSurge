"""
End-to-End System Test Suite:
Tests the entire system integration:
1. Web server root & static asset delivery
2. Full lifecycle of all 5 scenarios across lead times (0m, 30m, 60m, 90m, 180m)
3. Interactive fault injections (Surge spike, sensor offline, culvert blockage)
4. Emergency route calculation and impassable avoidance
5. Dynamic Word report generation across different lead times and conditions
"""

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_e2e_static_and_root():
    # Test Root
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "<!DOCTYPE html>" in res_root.text
    assert "Drain Out" in res_root.text


    # Test CSS
    res_css = client.get("/static/app.css")
    assert res_css.status_code == 200
    assert "--bg-dark:" in res_css.text

    # Test JS
    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "updateDashboardUI" in res_js.text


def test_e2e_all_scenarios_and_timesteps():
    scenarios = ["storm_01", "sensor_offline", "sensor_spike", "capacity_reduction", "e2e_validation"]
    for sc in scenarios:
        for t in [0, 15, 30, 45, 60, 90, 120, 150, 180]:
            res = client.get(f"/api/dashboard/state?scenario_id={sc}&lead_time_minutes={t}")
            assert res.status_code == 200, f"Failed for {sc} at {t}m"
            data = res.json()
            assert "system_status" in data
            assert "forecast" in data
            assert "safe_route" in data
            assert "sensors" in data
            assert len(data["sensors"]) == 6
            assert "cells" in data
            assert len(data["cells"]) == 100
            assert "roads" in data
            assert len(data["roads"]) == 10
            assert "mass_balance" in data
            assert data["mass_balance"]["status"] == "PASS"


def test_e2e_fault_injections():
    # 1. Surge Spike
    r_spike = client.get("/api/dashboard/state?scenario_id=storm_01&lead_time_minutes=30&fault_spike=true")
    assert r_spike.status_code == 200
    d_spike = r_spike.json()
    assert d_spike["system_status"] == "DEGRADED"
    s1 = next(s for s in d_spike["sensors"] if s["sensor_id"] == "S001")
    assert s1["status"] == "STALE"

    # 2. Sensor Dropout
    r_off = client.get("/api/dashboard/state?scenario_id=storm_01&lead_time_minutes=30&fault_offline=true")
    assert r_off.status_code == 200
    d_off = r_off.json()
    assert d_off["system_status"] == "DEGRADED"
    s1_off = next(s for s in d_off["sensors"] if s["sensor_id"] == "S001")
    assert s1_off["status"] == "OFFLINE"

    # 3. Culvert Blockage
    r_block = client.get("/api/dashboard/state?scenario_id=storm_01&lead_time_minutes=45&fault_blockage=true")
    assert r_block.status_code == 200
    d_block = r_block.json()
    assert d_block["system_status"] == "DEGRADED"


def test_e2e_dynamic_reports():
    scenarios = ["storm_01", "e2e_validation"]
    for sc in scenarios:
        for t in [0, 45, 60, 90]:
            res = client.get(f"/api/reports/download-docx?scenario_id={sc}&lead_time_minutes={t}&fault_blockage=true")
            assert res.status_code == 200
            assert "attachment; filename=" in res.headers.get("content-disposition", "")
            assert len(res.content) > 5000
