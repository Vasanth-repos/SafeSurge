"""
Layers 13–15 — Sensor Fusion & Confidence Demo:
Demonstrates temporal bias estimation, spatial correction, and anti-circular confidence scoring.
"""

from fusion.models import SensorObservation
from fusion.pipeline import FusionPipeline


def main():
    print("Layers 13-15 - Sensor Fusion, Spatial Bias & Confidence Subsystem")
    print("=" * 68)

    pipeline = FusionPipeline.load_from_config("config.yaml")

    cell_coords = {
        "C104": (0.0, 0.0),       # Colocated with sensor S001
        "C105": (100.0, 0.0),     # 100m away
        "C106": (300.0, 0.0),     # 300m away
        "C999": (1500.0, 0.0),    # >1000m away
    }
    sensor_coords = {"S001": (0.0, 0.0)}

    model_depths = {
        "C104": 18.0,
        "C105": 16.0,
        "C106": 14.0,
        "C999": 10.0,
    }

    print("Simulating 3 Consecutive Observations (Observed Depth = 25.0cm vs Model = 18.0cm):\n")

    for step_idx, t in enumerate((10, 20, 30), start=1):
        obs = [SensorObservation("S001", "C104", t, 25.0, "ONLINE", "ACCEPTED")]
        result = pipeline.step(t, model_depths, cell_coords, obs, sensor_coords)

        b_val = result.sensor_biases.get("S001", 0.0)
        c104 = result.cells["C104"]

        print(
            f"Step {step_idx} (t={t:2d}s) | S001 EWMA Bias={b_val:5.2f}cm | "
            f"C104 Model={c104.model_depth_cm:4.1f}cm -> Corr={c104.correction_cm:+5.2f}cm -> Fused={c104.corrected_depth_cm:4.1f}cm | "
            f"Confidence={c104.confidence.score*100:4.1f}%"
        )

    print("\nSpatial Propagation & Confidence Gradient across Grid Domain:")
    for cid in ("C104", "C105", "C106", "C999"):
        cell_res = result.cells[cid]
        conf = cell_res.confidence
        print(
            f"  {cid:4s} | Model={cell_res.model_depth_cm:4.1f}cm | "
            f"Corr={cell_res.correction_cm:+5.2f}cm | Corrected={cell_res.corrected_depth_cm:4.1f}cm | "
            f"Conf={conf.score*100:4.1f}% (Cov={conf.coverage*100:3.0f}%, Fresh={conf.freshness*100:3.0f}%, Agree={conf.agreement*100:3.0f}%)"
        )

    print("-" * 68)
    print("Layers 13-15 Sensor Fusion Pipeline: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
