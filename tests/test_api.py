"""
Layer 19 — Backend REST API Integration Tests:
Verifies FastAPI routing endpoints, health check, simulation replays, sensor ingestion, and routing requests.
"""

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verifies GET /health returns status: ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_simulation_replay_lifecycle_and_endpoints():
    """
    Verifies the complete REST API lifecycle:
    1. POST /api/rainfall/replay -> simulation_id
    2. GET /api/simulation/{id} -> status & snapshot count
    3. GET /api/flood/grid -> grid cells & anomalies
    4. GET /api/roads/risk -> road risks
    5. POST /api/routes/safe -> safe route result
    """
    # 1. Trigger replay
    rep_res = client.post("/api/rainfall/replay", json={"scenario": "storm_demo.json"})
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert "simulation_id" in rep_data
    sim_id = rep_data["simulation_id"]
    assert rep_data["status"] == "COMPLETED"

    # 2. Simulation Status
    stat_res = client.get(f"/api/simulation/{sim_id}")
    assert stat_res.status_code == 200
    stat_data = stat_res.json()
    assert stat_data["simulation_id"] == sim_id
    assert stat_data["snapshots_count"] > 0

    # 3. Flood Grid
    grid_res = client.get(f"/api/flood/grid?simulation_id={sim_id}&timestamp_seconds=600")
    assert grid_res.status_code == 200
    grid_data = grid_res.json()
    assert "flood_grid" in grid_data
    assert "anomalies" in grid_data

    # 4. Road Risk
    road_res = client.get(f"/api/roads/risk?simulation_id={sim_id}&timestamp_seconds=600")
    assert road_res.status_code == 200
    road_data = road_res.json()
    assert "roads" in road_data
    assert len(road_data["roads"]) > 0

    # 5. Route calculation
    route_res = client.post(
        "/api/routes/safe",
        json={
            "simulation_id": sim_id,
            "origin": "A",
            "destination": "D",
            "lead_time_minutes": 0,
            "mode": "vehicle",
        },
    )
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert "route_available" in route_data
    assert "road_path" in route_data


def test_sensor_ingestion_endpoint():
    """Verifies POST /api/sensors/reading."""
    res = client.post(
        "/api/sensors/reading",
        json={
            "sensor_id": "S001",
            "timestamp_seconds": 60,
            "distance_cm": 73.0,
            "float_state": "WATER_PRESENT",
            "boot_id": "boot-001",
            "sequence": 1,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sensor_id"] == "S001"
    assert data["accepted"] is True
    assert data["measurement_status"] == "ACCEPTED"
