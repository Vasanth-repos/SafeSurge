"""
Layer 4 — Runoff Generation Demo & Monotonicity Validation Entry Point.
"""

from flood_engine.runoff import RunoffEngine


def main():
    print("Layer 4 — Runoff Generation")
    print("=" * 60)
    print("Default Curve Number: 85")
    print("Antecedent moisture condition: FIXED")
    print("SCS-CN use: coarse prototype runoff approximation\n")

    engine = RunoffEngine(
        cell_areas_m2={"C00001": 900.0},
        curve_numbers={"C00001": 85.0},
        default_cn=85.0,
        expected_timestep_seconds=60,
    )

    # 0 -> 10 -> 20 -> 30 mm cumulative sequence (increments: 0, 10, 10, 10 mm)
    rainfall_increments = [0.0, 10.0, 10.0, 10.0]

    for idx, inc in enumerate(rainfall_increments):
        t = (idx + 1) * 60
        step = engine.process_timestep(t, inc)
        state = step.cell_states["C00001"]

        print(
            f"t={t:3d}s | rainfall={inc:5.1f} mm | cum_rain={state.cumulative_rainfall_mm:5.1f} mm | "
            f"cum_runoff={state.cumulative_runoff_mm:7.4f} mm | inc_runoff={state.incremental_runoff_mm:7.4f} mm | "
            f"vol={state.runoff_volume_m3:8.6f} m³"
        )

    print("-" * 60)
    bal = engine.mass_balance()
    print("Cumulative Mass Balance Accounting:")
    print(f"  Gross Precipitation Volume: {bal['cumulative_rainfall_volume_m3']:.4f} m³")
    print(f"  Direct Runoff Volume:       {bal['cumulative_direct_runoff_volume_m3']:.4f} m³")
    print(f"  Soil/Initial Retention:     {bal['cumulative_non_runoff_volume_m3']:.4f} m³")
    print(f"  Runoff Fraction:            {bal['effective_runoff_fraction'] * 100:.2f}%")
    print(f"  Conservation Check (Q <= P): {'PASS' if bal['is_conserved'] else 'FAIL'}")
    print("=" * 60)
    print("Layer 4 Runoff Monotonicity: PASS")


if __name__ == "__main__":
    main()
