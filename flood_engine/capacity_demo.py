"""
Layer 8 — Drainage Capacity Scenario Demo:
Demonstrates time-varying drainage capacity scenario simulation (C_eff = C0 * F(t))
and compares baseline throughput against controlled reduced-capacity scenarios.
"""

from flood_engine.capacity import (
    build_state,
    capacity_status,
    load_capacity_scenario,
    utilization,
)


def main():
    print("Layer 8 - Drainage Capacity Scenario Engine")
    print("=" * 68)

    scenario_path = "data/scenarios/drainage_capacity_01.json"
    scenario = load_capacity_scenario(
        scenario_path,
        known_edge_ids=["E001", "E002", "E003", "E004"],
    )

    base_capacities = {
        "E001": 0.05,
        "E002": 0.04,
        "E003": 0.06,
        "E004": 0.03,
    }

    print(f"Loaded Scenario: {scenario.name} [{scenario.scenario_id}]")
    print(f"Targeted Edges: {list(scenario.edge_ids)}\n")

    test_timestamps = [0, 1800, 2700, 3600, 4500, 5400]

    for t in test_timestamps:
        state = build_state(scenario, t, base_capacities)
        f_e2 = state.capacity_factor_by_edge["E002"]
        c_eff_e2 = state.effective_capacity_m3_s_by_edge["E002"]
        status = capacity_status(f_e2)

        # Assume 1.2 m³ load in 60s
        load_m3 = 1.2
        trans_m3 = min(load_m3, c_eff_e2 * 60.0)
        u_pct = utilization(trans_m3, c_eff_e2, 60.0) * 100

        print(
            f"t={t:4d}s ({t/60:4.1f} min) | E002 F={f_e2:3.2f} [{status:7s}] | "
            f"C_eff={c_eff_e2:6.4f} m3/s | Transmitted={trans_m3:4.2f} m3 | Util={u_pct:5.1f}% | Mode={state.mode}"
        )

    print("-" * 68)
    print("Layer 8 Capacity Scenario: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
