"""
Layers 13–15 — Full Sensor Fusion Pipeline Integration Tests:
Verifies the complete end-to-end integration:
Original Flood Model -> Validated Sensor -> Residual -> EWMA Bias -> Spatial Interpolation -> Confidence -> Dashboard Outputs.
"""

import pytest
from fusion.models import SensorObservation
from fusion.pipeline import FusionPipeline


def test_end_to_end_fusion_acceptance_scenario():
    """
    Executes the canonical acceptance scenario:
    Model depth at C104: 18.0 cm
    Sensor S1 observed depth: 25.0 cm (Residual = +7.0 cm)
    Alpha = 0.3, Minimum observations = 3

    Steps:
    t=10s: Residual = +7 cm -> warmup count = 1, bias = 0.0 cm
    t=20s: Residual = +7 cm -> warmup count = 2, bias = 0.0 cm
    t=30s: Residual = +7 cm -> warmup count = 3, bias = 0.3 * 7.0 = 2.1 cm
           Colocated cell C104 corrected depth = 18.0 + 2.1 = 20.1 cm
           Nearby cell (50m away) receives attenuated positive correction
           Remote cell (>1000m away) receives 0.0 cm correction
           Confidence score is evaluated transparently
    """
    pipeline = FusionPipeline(
        bias_alpha=0.3,
        minimum_bias_observations=3,
        max_residual_for_bias_update_cm=20.0,
        spatial_max_distance_m=1000.0,
        spatial_max_absolute_correction_cm=15.0,
    )

    cell_coords = {
        "C104": (0.0, 0.0),       # Colocated with S1
        "C105": (50.0, 0.0),      # Nearby (50m)
        "C999": (2000.0, 2000.0), # Far outside radius
    }
    sensor_coords = {"S1": (0.0, 0.0)}

    model_depths = {
        "C104": 18.0,
        "C105": 15.0,
        "C999": 10.0,
    }

    # Step 1: t=10s
    obs1 = [SensorObservation("S1", "C104", 10, 25.0, "ONLINE", "ACCEPTED")]
    res1 = pipeline.step(10, model_depths, cell_coords, obs1, sensor_coords)
    assert res1.sensor_biases["S1"] == pytest.approx(0.0)
    assert res1.cells["C104"].correction_cm == pytest.approx(0.0)
    assert res1.cells["C104"].corrected_depth_cm == pytest.approx(18.0)

    # Step 2: t=20s
    obs2 = [SensorObservation("S1", "C104", 20, 25.0, "ONLINE", "ACCEPTED")]
    res2 = pipeline.step(20, model_depths, cell_coords, obs2, sensor_coords)
    assert res2.sensor_biases["S1"] == pytest.approx(0.0)

    # Step 3: t=30s (Warmup complete -> bias = 2.1 cm)
    obs3 = [SensorObservation("S1", "C104", 30, 25.0, "ONLINE", "ACCEPTED")]
    res3 = pipeline.step(30, model_depths, cell_coords, obs3, sensor_coords)

    # 1. Bias estimation
    assert res3.sensor_biases["S1"] == pytest.approx(2.1)

    # 2. Colocated cell correction
    c104 = res3.cells["C104"]
    assert c104.model_depth_cm == pytest.approx(18.0)
    assert c104.correction_cm == pytest.approx(2.1)
    assert c104.corrected_depth_cm == pytest.approx(20.1)

    # 3. Spatial attenuation on nearby cell
    c105 = res3.cells["C105"]
    assert c105.model_depth_cm == pytest.approx(15.0)
    assert 0.0 < c105.correction_cm <= 2.1
    assert c105.corrected_depth_cm > 15.0

    # 4. Remote cell outside radius receives zero correction
    c999 = res3.cells["C999"]
    assert c999.correction_cm == pytest.approx(0.0)
    assert c999.corrected_depth_cm == pytest.approx(10.0)
    assert c999.confidence.score == pytest.approx(0.0)

    # 5. Serialization format verification
    d_dict = res3.to_dict()
    assert "cells" in d_dict
    assert "C104" in d_dict["cells"]
    assert d_dict["cells"]["C104"]["depth"]["corrected_cm"] == pytest.approx(20.1)
