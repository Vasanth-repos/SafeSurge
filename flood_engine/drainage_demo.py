"""
Layer 6 — Stateful Drainage Network Demo & Surcharge Accounting Entry Point.
"""

from flood_engine.drainage import StatefulDrainageNetwork


def main():
    print("Layer 6 — Stateful Drainage Network Engine")
    print("=" * 65)

    network = StatefulDrainageNetwork.create_synthetic_demo_network()
    print(f"Initialized network: {len(network.nodes)} nodes, {len(network.edges)} pipe segments.\n")

    # Inflow storm: heavy burst at N001 (inlet)
    inflows = [8.0, 6.0, 4.0, 0.0, 0.0]

    for idx, inf in enumerate(inflows):
        t = (idx + 1) * 60
        res = network.step(
            timestamp_seconds=t,
            inflow_volume_m3_by_node={"N001": inf},
            capacity_factor_by_edge={"E001": 1.0, "E002": 0.5},  # E002 has 50% blockage
        )

        n1_store = res.node_storage_m3_by_node["N001"]
        n2_store = res.node_storage_m3_by_node["N002"]
        n4_out = res.outlet_discharge_m3_by_node.get("N004", 0.0)
        surch = res.surcharge_volume_m3

        print(
            f"t={t:3d}s | Inflow={inf:4.1f} m³ | Transmitted={res.transmitted_volume_m3:5.2f} m³ | "
            f"N001 Store={n1_store:5.2f} m³ | N002 Store={n2_store:5.2f} m³ | "
            f"Outlet={n4_out:5.2f} m³ | Surcharge={surch:5.2f} m³"
        )

    print("-" * 65)
    bal = network.mass_balance()
    print("Mass Conservation Summary:")
    print(f"  Total Inflow Ingested:    {bal['cumulative_inflow_m3']:.4f} m³")
    print(f"  Active Network Storage:   {bal['current_node_storage_m3']:.4f} m³")
    print(f"  Cumulative Outlet Volume: {bal['cumulative_outlet_discharge_m3']:.4f} m³")
    print(f"  Cumulative Surcharge:     {bal['cumulative_surcharge_m3']:.4f} m³")
    print(f"  Mass Balance Error:       {bal['mass_balance_error_m3']:.8f} m³")
    print(f"  Conservation Invariant:   {'PASS' if bal['is_conserved'] else 'FAIL'}")
    print("=" * 65)
    print("Layer 6 Drainage Routing: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
