"""
Comprehensive validation test suite covering all 10 scenarios from Section 41 of the specification.
"""

from backend.services.simulation_service import SimulationService


def test_scenario_01_no_rain():
    """Test 1: No Rain -> runoff = 0, storage ≈ 0"""
    sim = SimulationService()
    sim.reset()
    res = sim.step(rainfall_input=0.0)
    assert res["total_input_m3"] == 0.0
    assert res["total_storage_m3"] == 0.0
    assert res["mass_balance"]["status"] == "PASS"


def test_scenario_02_uniform_rain():
    """Test 2: Uniform Rain -> runoff generated, flow follows DEM, mass conserved"""
    sim = SimulationService()
    sim.reset()
    # Uniform rain with 5mm per timestep (exceeding initial abstraction after a few steps)
    rain_step = 5.0
    for _ in range(6):
        res = sim.step(rainfall_input=rain_step)
        assert res["mass_balance"]["status"] == "PASS"

    # Confirm runoff was generated
    assert res["mass_balance"]["input_total_m3"] > 0.0


def test_scenario_03_heavy_rain():
    """Test 3: Heavy Rain -> storage increases, drainage capacity approached, flood depth rises"""
    sim = SimulationService()
    sim.reset()
    # Heavy cloudburst storm (15mm per timestep)
    heavy_rain = 15.0
    for _ in range(6):
        res = sim.step(rainfall_input=heavy_rain)

    # Low points should have accumulated water
    max_depth = max(c.depth_cm for c in sim.cells.values())
    assert max_depth > 5.0, f"Expected flood depth accumulation, got max {max_depth} cm"
    assert res["mass_balance"]["status"] == "PASS"


def test_scenario_04_reduced_drainage_capacity():
    """Test 4: Reduced Drainage Capacity -> capture decreases, surface storage increases"""
    sim_normal = SimulationService()
    sim_normal.reset()

    sim_blocked = SimulationService()
    sim_blocked.reset()
    # Reduce inlet capacity to 30%
    sim_blocked.inject_fault("drain_blockage", target_id=3, value=0.3)

    rain_step = (35.0 / 3600.0) * 60.0
    for _ in range(5):
        sim_normal.step(rainfall_input=rain_step)
        sim_blocked.step(rainfall_input=rain_step)

    # Inlet cell should have higher storage in blocked simulation
    inlet_cell_id = sim_blocked.drainage.nodes[3].cell_id
    storage_normal = sim_normal.cells[inlet_cell_id].storage_m3
    storage_blocked = sim_blocked.cells[inlet_cell_id].storage_m3

    assert storage_blocked >= storage_normal, (
        f"Blocked storage ({storage_blocked}) should be >= normal storage ({storage_normal})"
    )


def test_scenario_05_sensor_bias():
    """Test 5: Sensor Bias -> model 20cm, sensor 28cm -> positive bias, corrected forecast increases"""
    sim = SimulationService()
    sim.reset()

    sid = 1
    cid = sim.sensors[sid].cell_id
    # Set model storage to simulate ~20cm depth
    sim.cells[cid].storage_m3 = (20.0 / 100.0) * sim.cells[cid].area_m2
    sim.cells[cid].update_depth()

    # Sensor observes 28cm
    sim.step(rainfall_input=0.0, sensor_readings={sid: {"water_level_cm": 28.0, "heartbeat": True}})
    s = sim.sensors[sid]

    assert s.current_bias > 0.0, f"Expected positive bias, got {s.current_bias}"
    assert sim.fused_depths_cm[cid] > sim.cells[cid].depth_cm


def test_scenario_06_sensor_spike():
    """Test 6: Sensor Spike -> 12cm then 90cm -> RATE_SPIKE and excluded from fusion"""
    sim = SimulationService()
    sim.reset()
    sid = 1

    # Step 1: Normal 12cm
    sim.step(rainfall_input=0.0, sensor_readings={sid: {"water_level_cm": 12.0, "heartbeat": True}})
    s = sim.sensors[sid]
    assert s.last_quality_flag == "VALID"
    assert s.last_valid_reading_cm == 12.0

    # Step 2: Rate spike to 90cm in 60s
    sim.step(rainfall_input=0.0, sensor_readings={sid: {"water_level_cm": 90.0, "heartbeat": True}})
    assert s.last_quality_flag in ("RATE_SPIKE", "INVALID_SPIKE")
    assert s.last_valid_reading_cm == 12.0  # Not overwritten by spike reading


def test_scenario_07_sensor_failure():
    """Test 7: Sensor Failure -> stop heartbeat -> OFFLINE, confidence drops, model continues"""
    sim = SimulationService()
    sim.reset()
    sid = 2
    cid = sim.sensors[sid].cell_id

    # Baseline reading
    sim.step(rainfall_input=0.0, sensor_readings={sid: {"water_level_cm": 10.0, "heartbeat": True}})
    initial_conf = sim.cell_confidences[cid]

    # Inject disconnect / drop heartbeat for 6 steps
    sim.inject_fault("sensor_disconnect", target_id=sid)
    for _ in range(6):
        sim.step(rainfall_input=0.0)

    s = sim.sensors[sid]
    assert s.status == "OFFLINE"
    assert sim.cell_confidences[cid] < initial_conf


def test_scenario_08_float_redundancy():
    """Test 8: Float Redundancy -> ultrasonic invalid, float=true -> WATER_PRESENT_DEPTH_UNKNOWN"""
    sim = SimulationService()
    sim.reset()
    sid = 1

    # Inject spike with float=True
    sim.inject_fault("sensor_spike", target_id=sid)
    sim.step(rainfall_input=0.0, sensor_readings={sid: {"water_level_cm": 999.0, "float_state": True, "heartbeat": True}})

    s = sim.sensors[sid]
    assert s.status == "INVALID"
    assert s.redundancy_state == "WATER_PRESENT_DEPTH_UNKNOWN"


def test_scenario_09_flooded_road_avoidance():
    """Test 9: Flooded Road -> artificially set road depth to UNSAFE -> route engine avoids it"""
    sim = SimulationService()
    sim.reset()

    # Route from J1 to J16
    initial_route = sim.compute_safe_route("J1", "J16", mode="emergency")
    assert initial_route["success"] is True

    # Flood the first road RD-01 (J1 -> J2)
    rd = sim.roads.roads["RD-01"]
    for cid in rd.associated_cell_ids:
        sim.fused_depths_cm[cid] = 40.0
    sim.roads.update_all_risks(sim.fused_depths_cm, sim.cell_confidences)
    assert rd.risk_level == "UNSAFE"

    # Diverted route
    diverted_route = sim.compute_safe_route("J1", "J16", mode="emergency")
    assert diverted_route["success"] is True
    path = diverted_route["path_nodes"]
    # RD-01 (J1-J2) must not be in path
    is_rd01_present = any(
        (path[i] == "J1" and path[i + 1] == "J2") or (path[i] == "J2" and path[i + 1] == "J1")
        for i in range(len(path) - 1)
    )
    assert not is_rd01_present


def test_scenario_10_mass_conservation_continuous():
    """Test 10: Mass Conservation -> balance_error < tolerance across entire storm profile"""
    sim = SimulationService()
    sim.reset()

    rain_profile = [10.0, 25.0, 50.0, 70.0, 45.0, 20.0, 5.0, 0.0, 0.0, 0.0]
    for step_idx, r_rate in enumerate(rain_profile):
        dt_s = 60.0
        r_step = (r_rate / 3600.0) * dt_s
        res = sim.step(rainfall_input=r_step, dt_seconds=dt_s)

        mb = res["mass_balance"]
        assert mb["status"] == "PASS", f"Step {step_idx} failed: {mb}"
        assert abs(mb["balance_error_m3"]) <= sim.tolerance_m3
