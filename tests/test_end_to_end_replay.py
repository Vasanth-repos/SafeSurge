"""
Scenario 6: End-to-End Pipeline & Replay Validation
Runs a complete storm scenario from rainfall ingestion to sensor telemetry,
flood depth fusion, safe emergency route computation, and mass balance conservation.
"""

from fastapi.testclient import TestClient

from backend.app import app


def test_end_to_end_system_replay():
    client = TestClient(app)

    # 1. Reset system
    res = client.post("/api/scenarios/reset")
    assert res.status_code == 200

    # 2. Get scenario list
    scenarios_res = client.get("/api/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()["scenarios"]
    assert len(scenarios) >= 3

    # 3. Step through Flash Flood scenario (10 steps)
    for step_num in range(10):
        step_res = client.post("/api/scenarios/step?scenario=flash_flood")
        assert step_res.status_code == 200
        step_data = step_res.json()
        assert step_data["step"] == step_num + 1

        # Check mass balance on each step
        mb = step_data["step_result"]["mass_balance"]
        assert mb["status"] == "PASS"

    # 4. Check 2D Grid state
    grid_res = client.get("/api/flood/grid")
    assert grid_res.status_code == 200
    cells = grid_res.json()
    assert len(cells) == 400  # 20x20 grid

    # 5. Check road risk state
    roads_res = client.get("/api/flood/roads")
    assert roads_res.status_code == 200
    roads = roads_res.json()
    assert len(roads) > 0

    # 6. Compute safe route for emergency vehicle
    route_res = client.post("/api/routes/safe", json={
        "origin": "J1",
        "destination": "J16",
        "mode": "emergency"
    })
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert route_data["success"] is True
    assert len(route_data["path_nodes"]) >= 2
    assert route_data["eta_minutes"] > 0

    # 7. Check diagnostics endpoint
    diag_res = client.get("/api/diagnostics/mass_balance")
    assert diag_res.status_code == 200
    diag = diag_res.json()
    assert diag["status"] == "PASS"
