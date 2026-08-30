"""
Scenario 5: Emergency Route Avoidance Validation
Artificially causes a road segment to flood to UNSAFE level, asserting the
emergency routing engine diverts around it via a safe alternative path.
"""

from backend.services.simulation_service import SimulationService


def test_emergency_routing_flood_avoidance():
    sim = SimulationService()
    sim.reset()

    # Route from J1 (top-left) to J16 (bottom-right)
    origin = "J1"
    destination = "J16"

    # Step 1: In dry state, check baseline route exists
    base_route = sim.compute_safe_route(origin=origin, destination=destination, mode="emergency")
    assert base_route["success"] is True
    initial_path = base_route["path_nodes"]
    assert len(initial_path) > 0

    # Pick a road in the initial path to artificially flood to UNSAFE (> 30 cm)
    # E.g. RD-01 connects J1 to J2
    target_road = sim.roads.roads["RD-01"]
    for cid in target_road.associated_cell_ids:
        sim.fused_depths_cm[cid] = 45.0  # 45 cm flood depth -> UNSAFE

    # Update road risks with the flooded cells
    sim.roads.update_all_risks(sim.fused_depths_cm, sim.cell_confidences)
    assert target_road.risk_level == "UNSAFE"

    # Step 2: Compute route again in emergency mode
    diverted_route = sim.compute_safe_route(origin=origin, destination=destination, mode="emergency")
    assert diverted_route["success"] is True
    new_path = diverted_route["path_nodes"]

    # Verify that the direct edge between J1 and J2 (RD-01) is strictly avoided
    is_rd01_in_path = False
    for i in range(len(new_path) - 1):
        if (new_path[i] == "J1" and new_path[i + 1] == "J2") or (new_path[i] == "J2" and new_path[i + 1] == "J1"):
            is_rd01_in_path = True
            break

    assert not is_rd01_in_path, f"Emergency route failed to avoid UNSAFE road RD-01! Path: {new_path}"
