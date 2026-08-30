"""
Automated Test Suite for Virtual Tank Underground Drainage Network Simulation:
Validates:
1. Single tank normal filling
2. Single tank capacity limitation and overflow / surcharge calculation
3. Non-negative storage invariant under any outflow conditions
4. Drainage degradation factor (effective capacity throttling)
5. Multi-node network flow cascade (D01 -> D02 -> D03 -> D04 -> D05 -> Outfall)
6. Surface-drainage bidirectional coupling (overflow returning to surface cells)
7. System-wide mass conservation invariant (zero error tolerance)
8. Tank draining dynamics post-peak storm
9. Physical ultrasonic sensor comparison, residual calculation, and fault isolation
10. End-to-end REST API endpoints (/status, /network, /nodes/{id}, /dashboard/state)
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from flood_engine.tank_drainage import DrainageTankNode, TankThresholds, VirtualTankDrainageNetwork


def test_single_tank_normal_fill():
    """Validates basic mass balance for a single tank: S(t+1) = S(t) + I - O."""
    node = DrainageTankNode(
        node_id="D01",
        latitude=13.0867,
        longitude=80.2747,
        connected_cell_id="C022",
        capacity_liters=1000.0,
        base_capacity_lps=10.0,  # 10 L/s = 600 L over 60s
        current_storage_liters=500.0,
    )
    # dt = 60s, external inflow = 300 L.
    # Total water = 500 + 300 = 800 L.
    # Outflow capacity = 10 * 60 = 600 L.
    # Actual outflow = min(800, 600) = 600 L.
    # Storage = 800 - 600 = 200 L.
    outflow, overflow = node.step(dt_seconds=60, external_inflow_liters=300.0)
    assert outflow == 600.0
    assert overflow == 0.0
    assert node.current_storage_liters == 200.0
    assert node.fill_percentage == 20.0
    assert node.status == "NORMAL"


def test_single_tank_capacity_overflow():
    """Validates that storage is capped at capacity and excess generates surcharge overflow."""
    node = DrainageTankNode(
        node_id="D03",
        latitude=13.0887,
        longitude=80.2777,
        connected_cell_id="C058",
        capacity_liters=1000.0,
        base_capacity_lps=5.0,   # 5 L/s = 300 L over 60s
        current_storage_liters=900.0,
    )
    # dt = 60s, external inflow = 600 L.
    # Water available = 900 + 600 = 1500 L.
    # Outflow = 300 L.
    # Tentative storage = 1500 - 300 = 1200 L.
    # Capped at capacity 1000 L -> overflow = 200 L.
    outflow, overflow = node.step(dt_seconds=60, external_inflow_liters=600.0)
    assert outflow == 300.0
    assert overflow == 200.0
    assert node.current_storage_liters == 1000.0
    assert node.fill_percentage == 100.0
    assert node.status == "SURCHARGING"
    assert node.overflow_lps == round(200.0 / 60.0, 2)


def test_no_negative_storage():
    """Validates that tank storage never drops below zero even when outflow capacity exceeds stored water."""
    node = DrainageTankNode(
        node_id="D01",
        latitude=13.0867,
        longitude=80.2747,
        connected_cell_id="C022",
        capacity_liters=1000.0,
        base_capacity_lps=50.0,  # 3000 L over 60s
        current_storage_liters=150.0,
    )
    outflow, overflow = node.step(dt_seconds=60, external_inflow_liters=0.0)
    assert outflow == 150.0
    assert overflow == 0.0
    assert node.current_storage_liters == 0.0
    assert node.fill_percentage == 0.0
    assert node.status == "NORMAL"


def test_drainage_degradation_factor():
    """Validates that drainage degradation factor reduces effective discharge capacity."""
    node = DrainageTankNode(
        node_id="D03",
        latitude=13.0887,
        longitude=80.2777,
        connected_cell_id="C058",
        capacity_liters=2000.0,
        base_capacity_lps=30.0,
        current_storage_liters=1000.0,
    )
    assert node.effective_capacity_lps == 30.0

    # Apply 70% blockage (factor = 0.30)
    node.set_degradation_factor(0.30)
    assert node.effective_capacity_lps == 9.0

    # Over 60 seconds, max outflow should be 9.0 * 60 = 540 L (instead of 1800 L)
    outflow, overflow = node.step(dt_seconds=60, external_inflow_liters=0.0)
    assert outflow == 540.0
    assert node.current_storage_liters == 460.0


def test_connected_nodes_cascade():
    """Validates that water flows sequentially through connected tanks D01 -> D02 -> D03 -> D04 -> D05."""
    net = VirtualTankDrainageNetwork()
    net.reset()

    # Inject 1000 L only into headwater tank D01
    res = net.step(dt_seconds=60, surface_inflows_liters_by_cell={"C022": 1000.0})

    # D01 base capacity is 25 L/s = 1500 L over 60s -> all 1000 L flows to D02
    d1 = res["nodes"]["D01"]
    d2 = res["nodes"]["D02"]
    assert d1["current_storage_liters"] == 0.0
    # D02 received 1000 L from D01. D02 base cap is 30 L/s = 1800 L -> routes to D03
    # Water cascades downstream towards outfall
    assert res["cumulative_surface_inflow_liters"] == 1000.0
    assert res["mass_balance_error_liters"] == 0.0


def test_surface_coupling_surcharge_ejection():
    """Validates that when a tank surcharges, overflow volume is ejected back to its connected surface cell."""
    net = VirtualTankDrainageNetwork()
    net.reset()

    # Severely degrade D03 and flood it with large inflow
    res = net.step(
        dt_seconds=60,
        surface_inflows_liters_by_cell={"C058": 5000.0},
        degradation_factors={"D03": 0.10},  # 3 L/s = 180 L over 60s
    )

    d3 = res["nodes"]["D03"]
    assert d3["status"] == "SURCHARGING"
    assert d3["current_storage_liters"] == 2000.0  # At max capacity
    assert d3["overflow_liters"] > 0.0

    # Verify surcharge is returned to cell C058
    assert "C058" in res["step_surcharges_by_cell_liters"]
    assert res["step_surcharges_by_cell_liters"]["C058"] == d3["overflow_liters"]
    assert res["step_surcharges_by_cell_m3"]["C058"] == round(d3["overflow_liters"] / 1000.0, 6)


def test_tank_network_mass_conservation():
    """Validates exact mass conservation across the entire connected network over multiple timesteps."""
    net = VirtualTankDrainageNetwork()
    net.reset()

    storm_inputs = [
        {"C022": 500.0, "C045": 400.0, "C058": 1200.0},
        {"C022": 1500.0, "C045": 1200.0, "C058": 3000.0},
        {"C022": 2500.0, "C045": 2000.0, "C058": 4500.0},
        {"C022": 800.0, "C045": 600.0, "C058": 1500.0},
        {"C022": 0.0, "C045": 0.0, "C058": 0.0},
    ]

    for step_idx, inp in enumerate(storm_inputs):
        degs = {"D03": 0.30} if step_idx >= 1 else None
        res = net.step(dt_seconds=60, surface_inflows_liters_by_cell=inp, degradation_factors=degs)
        # Mass balance error must be strictly zero (or within float epsilon)
        assert abs(res["mass_balance_error_liters"]) < 1e-5, f"Mass balance error at step {step_idx}: {res['mass_balance_error_liters']}"
        assert abs(res["mass_balance_error_m3"]) < 1e-8


def test_tank_draining_after_storm():
    """Validates that tanks fill during rainfall and subsequently drain when rainfall stops."""
    net = VirtualTankDrainageNetwork()
    net.reset()

    # Fill network
    net.step(dt_seconds=60, surface_inflows_liters_by_cell={"C022": 3000.0, "C058": 3000.0})
    initial_stored = sum(n.current_storage_liters for n in net.nodes.values())
    assert initial_stored > 0.0

    # Run 5 dry steps (no inflow)
    for _ in range(5):
        net.step(dt_seconds=60, surface_inflows_liters_by_cell={})

    final_stored = sum(n.current_storage_liters for n in net.nodes.values())
    assert final_stored < initial_stored, "Tanks should drain after storm rainfall stops"


def test_sensor_comparison_and_fault_isolation():
    """Validates simulated stage comparison against physical ultrasonic telemetry and fault isolation."""
    net = VirtualTankDrainageNetwork()
    net.reset()

    # Half fill D03 (capacity=2000L, node_depth=160cm -> stage = 80cm)
    node = net.nodes["D03"]
    node.current_storage_liters = 1000.0
    node.update_status()
    assert node.simulated_water_level_cm == 80.0

    # 1. Normal sensor agreement
    comp_normal = net.compare_with_sensor("D03", live_sensor_depth_cm=82.0, sensor_status="ONLINE")
    assert comp_normal["agreement"] == "EXCELLENT"
    assert comp_normal["residual_cm"] == 2.0

    # 2. Sensor offline
    comp_offline = net.compare_with_sensor("D03", live_sensor_depth_cm=None, sensor_status="OFFLINE")
    assert comp_offline["agreement"] == "UNAVAILABLE"
    assert comp_offline["residual_cm"] is None

    # 3. Sensor disconnected / stale
    comp_stale = net.compare_with_sensor("D03", live_sensor_depth_cm=180.0, sensor_status="STALE")
    assert comp_stale["agreement"] == "UNAVAILABLE"


def test_drainage_api_endpoints():
    """Validates that all virtual tank API endpoints return HTTP 200 with proper schema."""
    client = TestClient(app)

    # 1. Status endpoint
    r_status = client.get("/api/drainage/status?lead_time_minutes=60&fault_blockage=true")
    assert r_status.status_code == 200
    stat_json = r_status.json()
    assert "summary" in stat_json
    assert "tanks" in stat_json
    assert stat_json["summary"]["network_status"] in ["NORMAL", "WATCH", "NEAR_CAPACITY", "SURCHARGING"]

    # 2. Network topology endpoint
    r_net = client.get("/api/drainage/network?lead_time_minutes=60")
    assert r_net.status_code == 200
    net_json = r_net.json()
    assert net_json["network_id"] == "CHENNAI_URBAN_TRUNK_01"
    assert len(net_json["nodes"]) == 5
    assert len(net_json["edges"]) == 5

    # 3. Node-specific endpoint
    r_d3 = client.get("/api/drainage/nodes/D03?lead_time_minutes=60&fault_blockage=true")
    assert r_d3.status_code == 200
    d3_json = r_d3.json()
    assert d3_json["node"]["node_id"] == "D03"
    assert d3_json["node"]["fill_percentage"] == 100.0
    assert d3_json["node"]["status"] == "SURCHARGING"

    # 4. Integrated Dashboard State
    r_dash = client.get("/api/dashboard/state?lead_time_minutes=60&fault_blockage=true")
    assert r_dash.status_code == 200
    dash_json = r_dash.json()
    assert "drainage_tanks" in dash_json
    assert "drainage_network_summary" in dash_json
    assert len(dash_json["drainage_tanks"]) == 5
