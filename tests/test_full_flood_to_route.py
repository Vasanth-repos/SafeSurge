"""
Master End-to-End System Test:
Replays storm event through full pipeline:
Rainfall -> Runoff -> Overland Routing -> Drainage -> Depth -> Risk -> Sensor Fusion -> Anomalies -> Road Exposure -> Dynamic Emergency Routing.
"""

from backend.services.simulation_manager import SimulationManager


def test_master_flood_forecast_to_dynamic_route():
    """
    Master integration verification:
    1. Runs storm simulation replay.
    2. Inspects t=0s: R001 & R002 are SAFE -> Route is A -> B -> D.
    3. Inspects peak flood snapshot: R002 accumulates deep water and becomes UNSAFE.
    4. Emergency router dynamically adapts to safe alternate path: A -> C -> D.
    5. Avoided road list explicitly explains why R002 was rejected.
    """
    manager = SimulationManager(config_path="config.yaml")
    sim = manager.start_simulation("storm_demo.json")

    # t = 0m (Dry state)
    r_initial = manager.route_emergency(sim.simulation_id, origin="A", destination="D", lead_time_minutes=0)
    assert r_initial.route_available is True
    assert r_initial.road_path == ("R001", "R002")

    # t = 20m (Flood accumulated on east side R002)
    r_flood = manager.route_emergency(sim.simulation_id, origin="A", destination="D", lead_time_minutes=20)
    assert r_flood.route_available is True
    # Successfully switches to alternate safe corridor A -> C -> D
    assert r_flood.road_path == ("R003", "R004")
    assert any(avoided.road_id == "R002" for avoided in r_flood.avoided_roads)
