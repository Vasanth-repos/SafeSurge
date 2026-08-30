"""
Layer 6 (Stateful) — Drainage Network Unit and Integration Tests:
Verifies node storage limits, pipe capacity constraints, degradation factors,
proportional branching, explicit surcharge generation, outlet discharge,
synchronous transmission, and strict mass conservation.
"""

import math

import pytest

from flood_engine.drainage import (
    DrainageEdge,
    DrainageNode,
    StatefulDrainageNetwork,
)


def test_drainage_node_and_edge_creation():
    """Verifies node and edge registration in network graph."""
    net = StatefulDrainageNetwork()
    n1 = DrainageNode(node_id="N1", latitude=13.0, longitude=80.0, node_type="inlet", storage_capacity_m3=5.0)
    n2 = DrainageNode(node_id="N2", latitude=13.1, longitude=80.1, node_type="outlet", storage_capacity_m3=10.0)
    net.add_node(n1)
    net.add_node(n2)

    e1 = DrainageEdge(edge_id="E1", from_node="N1", to_node="N2", capacity_m3_s=0.05)
    net.add_edge(e1)

    assert len(net.nodes) == 2
    assert len(net.edges) == 1
    assert net.outgoing_edges("N1")[0].edge_id == "E1"


def test_capacity_degradation_factors():
    """Verifies pipe capacity degradation factor throttling."""
    net = StatefulDrainageNetwork()
    net.add_node(DrainageNode("N1", 13.0, 80.0, storage_capacity_m3=20.0))
    net.add_node(DrainageNode("N2", 13.1, 80.1, node_type="outlet", storage_capacity_m3=20.0))
    net.add_edge(DrainageEdge("E1", "N1", "N2", capacity_m3_s=0.10))  # Max vol in 60s = 6.0 m³

    # At 50% capacity (factor=0.5), cap_vol = 3.0 m³
    res = net.step(60, inflow_volume_m3_by_node={"N1": 10.0}, capacity_factor_by_edge={"E1": 0.5})

    assert math.isclose(res.edge_flows["E1"].transmitted_volume_m3, 3.0, rel_tol=1e-4)
    # Remaining 7.0 m³ stored in N1
    assert math.isclose(res.node_storage_m3_by_node["N1"], 7.0, rel_tol=1e-4)


def test_proportional_branching_and_redistribution():
    """Verifies proportional allocation of available volume across outgoing branches."""
    net = StatefulDrainageNetwork()
    net.add_node(DrainageNode("N1", 13.0, 80.0, storage_capacity_m3=50.0))
    net.add_node(DrainageNode("N2", 13.1, 80.1, storage_capacity_m3=50.0))
    net.add_node(DrainageNode("N3", 13.2, 80.2, storage_capacity_m3=50.0))

    # E1 capacity = 0.04 m³/s (2.4 m³ in 60s), E2 capacity = 0.02 m³/s (1.2 m³ in 60s)
    net.add_edge(DrainageEdge("E1", "N1", "N2", capacity_m3_s=0.04))
    net.add_edge(DrainageEdge("E2", "N1", "N3", capacity_m3_s=0.02))

    # Inflow = 1.8 m³ (<= total cap 3.6 m³). Should split 2:1 -> E1=1.2 m³, E2=0.6 m³
    res = net.step(60, inflow_volume_m3_by_node={"N1": 1.8})

    assert math.isclose(res.edge_flows["E1"].transmitted_volume_m3, 1.2, rel_tol=1e-4)
    assert math.isclose(res.edge_flows["E2"].transmitted_volume_m3, 0.6, rel_tol=1e-4)


def test_node_storage_and_surcharge_generation():
    """Verifies that water exceeding node storage capacity generates explicit surcharge."""
    net = StatefulDrainageNetwork()
    # N1 has storage capacity 3.0 m³ and outgoing blocked edge
    net.add_node(DrainageNode("N1", 13.0, 80.0, storage_capacity_m3=3.0))
    net.add_node(DrainageNode("N2", 13.1, 80.1, node_type="outlet", storage_capacity_m3=10.0))
    net.add_edge(DrainageEdge("E1", "N1", "N2", capacity_m3_s=0.05))

    # Fully block E1 (factor=0.0) and inject 10.0 m³
    res = net.step(60, inflow_volume_m3_by_node={"N1": 10.0}, capacity_factor_by_edge={"E1": 0.0})

    assert math.isclose(res.node_storage_m3_by_node["N1"], 3.0)  # Capped at storage_capacity_m3
    assert math.isclose(res.surcharge_volume_m3_by_node["N1"], 7.0)  # Excess 7.0 becomes surcharge
    assert math.isclose(res.surcharge_volume_m3, 7.0)


def test_outlet_discharge_accounting():
    """Verifies that outlet nodes discharge water up to outlet capacity."""
    net = StatefulDrainageNetwork()
    net.add_node(DrainageNode("N_OUT", 13.0, 80.0, node_type="outlet", base_capacity_m3_s=0.05, storage_capacity_m3=10.0))

    # Ingest 5.0 m³ at outlet node. Max discharge in 60s = 0.05 * 60 = 3.0 m³
    res = net.step(60, inflow_volume_m3_by_node={"N_OUT": 5.0})

    assert math.isclose(res.outlet_discharge_m3_by_node["N_OUT"], 3.0, rel_tol=1e-4)
    # Remaining 2.0 m³ stored at outlet node
    assert math.isclose(res.node_storage_m3_by_node["N_OUT"], 2.0, rel_tol=1e-4)


def test_synchronous_pipe_transport():
    """Verifies that water transmitted from N1 -> N2 appears at N2 at the end of the step."""
    net = StatefulDrainageNetwork()
    net.add_node(DrainageNode("N1", 13.0, 80.0, storage_capacity_m3=10.0))
    net.add_node(DrainageNode("N2", 13.1, 80.1, storage_capacity_m3=10.0))
    net.add_node(DrainageNode("N3", 13.2, 80.2, node_type="outlet", storage_capacity_m3=10.0))

    net.add_edge(DrainageEdge("E1", "N1", "N2", capacity_m3_s=0.05))  # 3 m³ in 60s
    net.add_edge(DrainageEdge("E2", "N2", "N3", capacity_m3_s=0.05))

    # Step 1: Inflow at N1 only
    res1 = net.step(60, inflow_volume_m3_by_node={"N1": 3.0})
    # Water moved across E1 into N2
    assert math.isclose(res1.node_storage_m3_by_node["N2"], 3.0, rel_tol=1e-4)
    assert res1.node_storage_m3_by_node["N3"] == 0.0

    # Step 2: Inflow 0. Water moves from N2 -> N3
    res2 = net.step(120, inflow_volume_m3_by_node={"N1": 0.0})
    assert math.isclose(res2.node_storage_m3_by_node["N2"], 0.0, abs_tol=1e-4)


def test_monotonic_timestamp_and_t0_support():
    """Verifies support for t=0 initial step and strictly monotonic increments."""
    net = StatefulDrainageNetwork()
    net.add_node(DrainageNode("N1", 13.0, 80.0))

    # t=0 step succeeds
    net.step(0, inflow_volume_m3_by_node={"N1": 1.0})

    # Next step must be t=60
    net.step(60, inflow_volume_m3_by_node={"N1": 0.0})

    # Duplicate or non-matching spacing fails
    with pytest.raises(ValueError, match="strictly greater"):
        net.step(60, inflow_volume_m3_by_node={"N1": 0.0})


def test_mass_conservation_invariant_over_storm():
    """Verifies that Total Inflow = Current Storage + Cumulative Outlet + Cumulative Surcharge."""
    net = StatefulDrainageNetwork.create_synthetic_demo_network()

    inflows = [10.0, 8.0, 6.0, 4.0, 2.0, 0.0, 0.0]
    for idx, inf in enumerate(inflows):
        t = (idx + 1) * 60
        step = net.step(t, inflow_volume_m3_by_node={"N001": inf}, capacity_factor_by_edge={"E002": 0.6})
        assert abs(step.mass_balance_error_m3) <= 1e-5

    bal = net.mass_balance()
    assert bal["is_conserved"] is True
    assert abs(bal["mass_balance_error_m3"]) <= 1e-5


def test_network_reset_isolation():
    """Verifies that reset() cleanly clears all network states."""
    net = StatefulDrainageNetwork.create_synthetic_demo_network()
    net.step(60, inflow_volume_m3_by_node={"N001": 5.0})
    assert net.cumulative_inflow_m3 > 0.0

    net.reset()
    assert net.cumulative_inflow_m3 == 0.0
    assert net.cumulative_outlet_discharge_m3 == 0.0
    assert net.cumulative_surcharge_m3 == 0.0
    assert net.last_timestamp_seconds is None


def test_traverse_volume_path_and_bottlenecks():
    """Verifies diagnostic path traversal and bottleneck detection."""
    net = StatefulDrainageNetwork.create_synthetic_demo_network()
    diag = net.traverse_volume("N001", "N004", volume_m3=10.0, dt_seconds=60.0)

    assert diag["reachable"] is True
    assert diag["path"] == ["N001", "N002", "N003", "N004"]
    assert diag["delivered_volume_m3"] <= 10.0
    assert diag["limiting_edge"] == "E002"  # E002 has smallest capacity (0.04 m³/s -> 2.4 m³ in 60s)
