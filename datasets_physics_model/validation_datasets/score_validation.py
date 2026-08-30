import json
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score

try:
    from sklearn.metrics import root_mean_squared_error
except ImportError:
    from sklearn.metrics import mean_squared_error
    def root_mean_squared_error(y_true, y_pred):
        return mean_squared_error(y_true, y_pred) ** 0.5

model = joblib.load("/home/claude/colab_notebook/aura_flood_surrogate_model.joblib")
FEATURES = joblib.load("/home/claude/colab_notebook/aura_flood_model_features.joblib")

val_df = pd.read_csv("validation_data.csv")

def risk_class(depth_cm):
    if depth_cm < 5: return "SAFE"
    elif depth_cm < 15: return "WATCH"
    elif depth_cm < 25: return "HIGH"
    else: return "UNSAFE"

report_rows = []
for tag, group in val_df.groupby("scenario_tag"):
    X = group[FEATURES]
    y_true = group["flood_depth_cm"]
    y_pred = model.predict(X)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = root_mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred) if y_true.nunique() > 1 else float("nan")

    true_risk = y_true.apply(risk_class)
    pred_risk = pd.Series(y_pred).apply(risk_class)
    risk_acc = (true_risk.values == pred_risk.values).mean()

    report_rows.append({
        "scenario_tag": tag,
        "n_rows": len(group),
        "mae_cm": round(mae, 3),
        "rmse_cm": round(rmse, 3),
        "r2": round(r2, 4) if not np.isnan(r2) else None,
        "risk_class_accuracy": round(risk_acc, 4),
        "true_depth_max_cm": round(y_true.max(), 2),
        "pred_depth_max_cm": round(float(np.max(y_pred)), 2),
    })

report_df = pd.DataFrame(report_rows).sort_values("scenario_tag")
report_df.to_csv("validation_report.csv", index=False)

overall_X = val_df[FEATURES]
overall_y = val_df["flood_depth_cm"]
overall_pred = model.predict(overall_X)
overall = {
    "overall_mae_cm": round(mean_absolute_error(overall_y, overall_pred), 3),
    "overall_rmse_cm": round(root_mean_squared_error(overall_y, overall_pred), 3),
    "overall_r2": round(r2_score(overall_y, overall_pred), 4),
    "overall_risk_accuracy": round(
        (overall_y.apply(risk_class).values == pd.Series(overall_pred).apply(risk_class).values).mean(), 4
    ),
    "n_validation_rows": len(val_df),
    "n_validation_scenarios": val_df["scenario_id"].nunique(),
}

with open("validation_report.json", "w") as f:
    json.dump({"overall": overall, "by_scenario_type": report_rows}, f, indent=2)

print("=== VALIDATION REPORT ===")
print(json.dumps(overall, indent=2))
print()
print(report_df.to_string(index=False))
