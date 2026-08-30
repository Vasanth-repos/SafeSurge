"""
AURA-FLOOD — INDEPENDENT VALIDATION OF EXISTING XGBOOST MODEL
Executes independent validation against held-out scenario-level dataset.
IMPORTANT: This code DOES NOT retrain the model.
"""

import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # Non-interactive backend for headless environments
import joblib
import matplotlib.pyplot as plt
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

# ------------------------------------------------------------
# 1. Load NEW validation dataset
# ------------------------------------------------------------

possible_paths = [
    "/content/drive/MyDrive/drainage_ps data sets/validation_datasets/validation_data_scenario_level.csv",
    os.path.join("datasets_physics_model", "validation_datasets", "validation_data_scenario_level.csv"),
    os.path.join(os.path.dirname(__file__), "..", "datasets_physics_model", "validation_datasets", "validation_data_scenario_level.csv"),
    os.path.join("data", "validation_data_scenario_level.csv"),
]

validation_path = None
for p in possible_paths:
    if os.path.exists(p):
        validation_path = p
        break

if validation_path is None:
    raise FileNotFoundError(
        "Validation dataset not found in any of candidate locations:\n" + "\n".join(possible_paths)
    )

df_val_new = pd.read_csv(validation_path)

print("Dataset loaded successfully.")
print(f"Dataset Shape: {df_val_new.shape}")

# ------------------------------------------------------------
# 2. Inspect columns and missing values
# ------------------------------------------------------------

print("\n--- DATASET COLUMNS ---")
print(df_val_new.columns.tolist())

print("\n--- MISSING VALUES ---")
print(df_val_new.isnull().sum().to_dict())

# ------------------------------------------------------------
# 3. Define EXACT features used during model training
# ------------------------------------------------------------

feature_cols = [
    "rainfall_intensity_mm_per_hr",
    "duration_hr",
    "timestep_min",
    "drainage_degradation_factor",
]

# Check that all required features exist
missing_features = [col for col in feature_cols if col not in df_val_new.columns]

if missing_features:
    raise ValueError(f"Missing required model features: {missing_features}")

# ------------------------------------------------------------
# 4. Check target column
# ------------------------------------------------------------

target_col = "max_water_depth_at_sensor_mm"

if target_col not in df_val_new.columns:
    raise ValueError(
        f"Target column '{target_col}' was not found.\n"
        f"Available columns are:\n{df_val_new.columns.tolist()}"
    )

# ------------------------------------------------------------
# 5. Remove rows with missing values
# ------------------------------------------------------------

df_eval = df_val_new[feature_cols + [target_col]].dropna().copy()

print("\n--- EVALUATION DATA ---")
print(f"Rows available for evaluation: {len(df_eval)}")

# ------------------------------------------------------------
# 6. Prepare features and actual target
# ------------------------------------------------------------

X_new = df_eval[feature_cols].copy()
y_new_actual = df_eval[target_col].copy()

print("\n--- MODEL INPUT FEATURES ---")
print(X_new.head())

print("\n--- ACTUAL FLOOD DEPTH (mm) ---")
print(y_new_actual.head())

# ------------------------------------------------------------
# 7. IMPORTANT: Use EXISTING trained model
# ------------------------------------------------------------

# Load model from disk if not in globals
if "xgb_regressor" not in globals():
    model_candidates = [
        os.path.join("ml", "artifacts", "aura_flood_xgb.joblib"),
        os.path.join("datasets_physics_model", "aura_flood_xgb.joblib"),
        os.path.join(os.path.dirname(__file__), "artifacts", "aura_flood_xgb.joblib"),
    ]
    xgb_regressor = None
    for mp in model_candidates:
        if os.path.exists(mp):
            xgb_regressor = joblib.load(mp)
            print(f"Loaded existing model from: {mp}")
            break

    if xgb_regressor is None:
        raise NameError(
            "xgb_regressor was not found in globals or on disk. "
            "Load the already-trained model before running this cell."
        )

print("\nExisting XGBoost model found.")
print("Generating predictions on NEW unseen validation data...")

y_new_pred = xgb_regressor.predict(X_new)

print("Predictions generated successfully.")

# ------------------------------------------------------------
# 8. Calculate evaluation metrics
# ------------------------------------------------------------

mae_mm = mean_absolute_error(y_new_actual, y_new_pred)
rmse_mm = np.sqrt(mean_squared_error(y_new_actual, y_new_pred))
r2 = r2_score(y_new_actual, y_new_pred)

mean_bias_mm = float(np.mean(y_new_pred - y_new_actual))
max_abs_error_mm = float(np.max(np.abs(y_new_pred - y_new_actual)))

# Convert mm -> cm
mae_cm = mae_mm / 10.0
rmse_cm = rmse_mm / 10.0
mean_bias_cm = mean_bias_mm / 10.0
max_abs_error_cm = max_abs_error_mm / 10.0

# ------------------------------------------------------------
# 9. Print results
# ------------------------------------------------------------

print("\n" + "=" * 55)
print("      AURA-FLOOD NEW VALIDATION RESULTS")
print("=" * 55)

print(f"Number of validation samples : {len(y_new_actual)}")

print("\nError Metrics:")
print(f"MAE  : {mae_mm:.3f} mm  ({mae_cm:.3f} cm)")
print(f"RMSE : {rmse_mm:.3f} mm  ({rmse_cm:.3f} cm)")
print(f"R^2  : {r2:.3f}")

print("\nAdditional Metrics:")
print(f"Mean Bias          : {mean_bias_mm:.3f} mm  ({mean_bias_cm:.3f} cm)")
print(f"Maximum Abs. Error : {max_abs_error_mm:.3f} mm  ({max_abs_error_cm:.3f} cm)")

print("=" * 55)

# ------------------------------------------------------------
# 10. Create results table
# ------------------------------------------------------------

df_results = df_eval.copy()
df_results["predicted_depth_mm"] = y_new_pred
df_results["error_mm"] = y_new_pred - y_new_actual
df_results["absolute_error_mm"] = np.abs(df_results["error_mm"])
df_results["actual_depth_cm"] = df_results[target_col] / 10.0
df_results["predicted_depth_cm"] = df_results["predicted_depth_mm"] / 10.0
df_results["absolute_error_cm"] = df_results["absolute_error_mm"] / 10.0

# ------------------------------------------------------------
# 11. Display worst predictions
# ------------------------------------------------------------

print("\n--- TOP 5 WORST PREDICTIONS ---")
print(
    df_results.sort_values(by="absolute_error_mm", ascending=False)
    .head(5)[
        [
            "rainfall_intensity_mm_per_hr",
            "duration_hr",
            "drainage_degradation_factor",
            "actual_depth_cm",
            "predicted_depth_cm",
            "absolute_error_cm",
        ]
    ]
    .to_string(index=False)
)

# ------------------------------------------------------------
# 12. Actual vs Predicted plot
# ------------------------------------------------------------

os.makedirs(os.path.join("outputs", "reports"), exist_ok=True)
plot_out = os.path.join("outputs", "reports", "aura_flood_validation_plot.png")

plt.figure(figsize=(7, 6))
plt.scatter(y_new_actual, y_new_pred, alpha=0.6, label="Predictions", color="#10b981")

min_value = min(y_new_actual.min(), y_new_pred.min())
max_value = max(y_new_actual.max(), y_new_pred.max())

plt.plot(
    [min_value, max_value],
    [min_value, max_value],
    linestyle="--",
    linewidth=2,
    color="#ef4444",
    label="Ideal 1:1",
)

plt.xlabel("Actual Flood Depth (mm)")
plt.ylabel("Predicted Flood Depth (mm)")
plt.title("AURA-FLOOD: Actual vs Predicted\nIndependent Validation Dataset")
plt.legend()
plt.grid(True, linestyle=":", alpha=0.6)
plt.savefig(plot_out, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nScatter plot saved to: {plot_out}")

# ------------------------------------------------------------
# 13. Compare with previous validation results
# ------------------------------------------------------------

previous_mae_cm = 8.270
previous_rmse_cm = 13.570
previous_r2 = 0.980

print("\n" + "=" * 55)
print("       PREVIOUS vs NEW VALIDATION")
print("=" * 55)

print(f"{'Metric':<15}{'Previous':>15}{'New':>15}")
print("-" * 45)
print(f"{'MAE (cm)':<15}{previous_mae_cm:>15.3f}{mae_cm:>15.3f}")
print(f"{'RMSE (cm)':<15}{previous_rmse_cm:>15.3f}{rmse_cm:>15.3f}")
print(f"{'R^2':<15}{previous_r2:>15.3f}{r2:>15.3f}")
print("=" * 55)

# ------------------------------------------------------------
# 14. Simple generalization check
# ------------------------------------------------------------

print("\n--- GENERALIZATION CHECK ---")

mae_change = mae_cm - previous_mae_cm
rmse_change = rmse_cm - previous_rmse_cm
r2_change = r2 - previous_r2

r2_label = "R^2"
print(f"MAE change : {mae_change:+.3f} cm")
print(f"RMSE change: {rmse_change:+.3f} cm")
print(f"{r2_label} change  : {r2_change:+.3f}")

if mae_cm <= previous_mae_cm * 1.25 and r2 >= 0.90:
    print("\n[PASS] PRELIMINARY VERDICT: GO")
    print(
        "The model shows reasonably consistent performance "
        "on the new validation dataset."
    )
elif mae_cm <= previous_mae_cm * 1.75 and r2 >= 0.70:
    print("\n[WARN] PRELIMINARY VERDICT: MODIFY")
    print(
        "The model shows some degradation on the new dataset "
        "and requires further investigation."
    )
else:
    print("\n[FAIL] PRELIMINARY VERDICT: RETRAIN / INVESTIGATE")
    print(
        "The model performance has degraded substantially "
        "on the new dataset."
    )
