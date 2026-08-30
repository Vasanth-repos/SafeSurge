"""
Training Pipeline for Physics-Guided Machine Learning (PGML) Nowcasting Engine.
Compiles simulation states across scenarios and fits the surrogate model.
"""

import math
import os

import numpy as np

from ml.features import (
    FEATURE_NAMES,
    build_feature_vector,
    extract_cell_static_features,
)
from ml.model import PhysicsGuidedFloodNowcaster

MODEL_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "pgml_nowcaster.joblib")


def generate_training_dataset() -> tuple[np.ndarray, np.ndarray]:
    """
    Compile synthetic training dataset across storm timesteps and scenarios.
    Ground-truth labels come from the coupled 2D hydrodynamic simulation engine.
    """
    X_list = []
    y_list = []

    # Scenarios:
    # 1. Nominal storm (peak at t=80m)
    # 2. Severe convective storm (higher peak)
    # 3. Drainage degradation scenario (E001 capacity drops to 0.3)
    scenarios = [
        {"name": "nominal", "peak_rain": 45.0, "drain_factor": 1.0, "max_depth_mult": 1.0},
        {"name": "severe", "peak_rain": 75.0, "drain_factor": 1.0, "max_depth_mult": 1.45},
        {"name": "clogged", "peak_rain": 45.0, "drain_factor": 0.3, "max_depth_mult": 1.3},
    ]

    for sc in scenarios:
        for t_min in range(0, 181, 5):
            int_factor = math.sin(min(math.pi, (t_min / 180.0) * math.pi))
            rain_rate = sc["peak_rain"] * int_factor
            cumulative_rain = sc["peak_rain"] * 1.5 * (1.0 - math.cos((t_min / 180.0) * math.pi)) / 2.0

            for r in range(10):
                for c in range(10):
                    sf = extract_cell_static_features(r, c)
                    feat_vec = build_feature_vector(
                        sf,
                        lead_time_min=float(t_min),
                        rain_rate_mm_hr=rain_rate,
                        cumulative_rain_mm=cumulative_rain,
                        drain_capacity_factor=sc["drain_factor"],
                    )

                    # Coupled physical target calculation (matching flood_engine simulation)
                    x = c * 10.0 + 5.0
                    y = r * 10.0 + 5.0
                    elev = sf["elevation_m"]

                    base_sheet = (2.2 + 1.1 * math.sin(x / 18.0) * math.cos(y / 18.0)) * int_factor
                    slope_drain = max(0.0, (20.0 - elev) * 0.9) * int_factor
                    valley_ch = max(0.0, 6.0 - 0.7 * sf["valley_dist_m"]) * int_factor
                    lowland = 16.0 * sf["lowland_sink_proximity"] * int_factor
                    south_can = max(0.0, (y - 40.0) / 50.0) * 6.5 * int_factor
                    
                    # Drainage blockage surcharge back-up
                    clog_surcharge = 0.0
                    if sc["drain_factor"] < 0.8 and r >= 5 and c >= 6:
                        clog_surcharge = 7.5 * int_factor

                    depth = max(0.0, (base_sheet + slope_drain + valley_ch + lowland + south_can + clog_surcharge) * sc["max_depth_mult"])

                    X_list.append(feat_vec)
                    y_list.append(depth)

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)


def train_and_save_model(artifact_path: str = MODEL_ARTIFACT_PATH) -> PhysicsGuidedFloodNowcaster:
    """Train the PGML model and save artifact to disk."""
    print("Generating hydrological training dataset...")
    X, y = generate_training_dataset()
    print(f"Dataset generated: {X.shape[0]} samples, {X.shape[1]} features.")

    # Train / Test Split
    indices = np.arange(len(X))
    np.random.seed(42)
    np.random.shuffle(indices)
    split = int(0.85 * len(X))
    train_idx, test_idx = indices[:split], indices[split:]

    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    nowcaster = PhysicsGuidedFloodNowcaster(n_estimators=100, max_depth=5, learning_rate=0.08)
    print("Fitting Physics-Guided Flood Nowcaster...")
    nowcaster.fit(X_train, y_train, feature_names=FEATURE_NAMES)

    # Evaluation
    preds_test = nowcaster.predict(X_test)
    rmse = float(np.sqrt(np.mean((preds_test - y_test) ** 2)))
    mae = float(np.mean(np.abs(preds_test - y_test)))
    r2 = float(1.0 - np.sum((y_test - preds_test) ** 2) / np.sum((y_test - np.mean(y_test)) ** 2))

    print("Evaluation Results on Test Split:")
    print(f"  - Test RMSE: {rmse:.3f} cm")
    print(f"  - Test MAE:  {mae:.3f} cm")
    print(f"  - Test R^2:  {r2:.4f}")

    nowcaster.save(artifact_path)
    print(f"Model saved successfully to: {artifact_path}")
    return nowcaster


if __name__ == "__main__":
    train_and_save_model()
