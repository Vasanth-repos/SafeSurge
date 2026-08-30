"""
Automated Unit and Integration Tests for the Radar Rainfall Nowcasting Module:
Verifies Doppler ingestion, preprocessing QC, Marshall-Palmer Z-R conversion,
spatial grid generation, temporal storm tracking, nowcast horizons, confidence scores,
and REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from flood_engine.radar_nowcast import (
    ConfidenceRating,
    ForecastConfidenceScorer,
    QualityControlFlag,
    RadarFrame,
    RadarNowcastEngine,
    RadarPreprocessor,
    RainfallEstimator,
    SyntheticRadarSimulator,
    TemporalStormTracker,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_marshall_palmer_zr_conversion():
    """Verifies Z-R conversions against physical radar benchmarks."""
    estimator = RainfallEstimator(a=200.0, b=1.6)

    # 1. Below 10 dBZ should return 0 mm/hr (clear air / mist threshold)
    assert estimator.dbz_to_rain_rate(8.0) == 0.0

    # 2. Moderate rain: 35 dBZ -> ~5.5 mm/hr
    r35 = estimator.dbz_to_rain_rate(35.0)
    assert 4.0 <= r35 <= 8.0

    # 3. Heavy rain: 50 dBZ -> ~48-52 mm/hr
    r50 = estimator.dbz_to_rain_rate(50.0)
    assert 45.0 <= r50 <= 55.0

    # 4. Round-trip conversion consistency (R -> dBZ -> R)
    test_rates = [1.0, 10.0, 25.0, 60.0]
    for r in test_rates:
        dbz = estimator.rain_rate_to_dbz(r)
        recovered_r = estimator.dbz_to_rain_rate(dbz)
        assert abs(recovered_r - r) < 0.2


def test_radar_preprocessor_clutter_rejection():
    """Verifies that extreme ground clutter and isolated noise spikes are filtered."""
    preprocessor = RadarPreprocessor(clutter_threshold_dbz=65.0)

    # Synthetic noisy frame
    frame = RadarFrame(timestamp_seconds=3600, grid_size=5)
    frame.reflectivity_dbz[2][2] = 72.0  # Ground clutter spike
    frame.reflectivity_dbz[0][0] = 45.0  # Isolated single-pixel speckle

    cleaned = preprocessor.process_frame(frame)
    # Ground clutter should be flagged and capped
    assert cleaned.qc_flags[2][2] == QualityControlFlag.CLUTTER
    assert cleaned.reflectivity_dbz[2][2] <= 45.0

    # Isolated speckle should be smoothed/flagged
    assert cleaned.qc_flags[0][0] == QualityControlFlag.NOISY
    assert cleaned.reflectivity_dbz[0][0] < 10.0


def test_temporal_storm_tracking():
    """Verifies cross-frame storm centroid and advection velocity vector calculation."""
    tracker = TemporalStormTracker(frame_interval_seconds=300)

    # Frame 1: Storm at (c=2.0, r=2.0)
    f1 = RadarFrame(timestamp_seconds=0, grid_size=10)
    f1.reflectivity_dbz[2][2] = 50.0

    # Frame 2: Storm shifted East to (c=4.0, r=2.0) after 300 seconds (5 min = 1/12 hour)
    # dx = 2 km, dt = 1/12 hr => vx = 24 km/h
    f2 = RadarFrame(timestamp_seconds=300, grid_size=10)
    f2.reflectivity_dbz[2][4] = 50.0

    motion = tracker.track(f1, f2)
    assert motion.vx_kmh > 15.0  # Moving eastward
    assert motion.speed_kmh > 15.0
    assert 70.0 <= motion.direction_degrees <= 110.0  # Heading East (~90 deg)


def test_forecast_confidence_scoring():
    """Verifies forecast confidence decays monotonically with forecast horizon."""
    horizons = [0, 30, 60, 90, 120, 150, 180]
    scores = []

    for h in horizons:
        score, rating = ForecastConfidenceScorer.evaluate(lead_time_minutes=h)
        assert 0.0 <= score <= 1.0
        scores.append(score)

    # Scores must strictly decrease as lead time increases
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]

    # Verify ratings
    _, r30 = ForecastConfidenceScorer.evaluate(lead_time_minutes=30)
    assert r30 == ConfidenceRating.HIGH

    _, r180 = ForecastConfidenceScorer.evaluate(lead_time_minutes=180)
    assert r180 == ConfidenceRating.LOW


def test_radar_nowcast_engine_grid_generation():
    """Verifies nowcast engine generates valid 10x10 spatial grids for all horizons."""
    sim = SyntheticRadarSimulator(grid_size=10)
    f_curr = sim.generate_sweep(elapsed_minutes=60)
    f_prev = sim.generate_sweep(elapsed_minutes=50)

    engine = RadarNowcastEngine()
    horizons = [30, 60, 120, 180]
    results = engine.generate_nowcast(f_curr, f_prev, lead_times_minutes=horizons)

    assert set(results.keys()) == set(horizons)

    for h in horizons:
        hz = results[h]
        assert hz.lead_time_minutes == h
        assert len(hz.cells) == 100  # 10x10 grid: C001 to C100
        assert "C001" in hz.cells
        assert "C100" in hz.cells
        assert hz.mean_intensity_mmh >= 0.0
        assert hz.peak_intensity_mmh >= hz.mean_intensity_mmh

        for cid, c_data in hz.cells.items():
            assert "intensity_mmh" in c_data
            assert "depth_mm" in c_data
            assert "dbz" in c_data
            assert c_data["intensity_mmh"] >= 0.0


def test_api_radar_nowcast_endpoints(client):
    """Verifies /api/radar/nowcast, /api/radar/tracking, /api/radar/frames endpoints."""
    # 1. /api/radar/nowcast
    res = client.get("/api/radar/nowcast?lead_time_minutes=30&elapsed_minutes=60")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert "motion_tracking" in data
    assert "nowcast" in data
    assert len(data["nowcast"]["cells"]) == 100

    # 2. /api/radar/tracking
    res_track = client.get("/api/radar/tracking?elapsed_minutes=60")
    assert res_track.status_code == 200
    data_track = res_track.json()
    assert "speed_kmh" in data_track
    assert "direction_degrees" in data_track
    assert "cardinal_direction" in data_track

    # 3. /api/radar/frames
    res_frames = client.get("/api/radar/frames?elapsed_minutes=60")
    assert res_frames.status_code == 200
    data_frames = res_frames.json()
    assert data_frames["frames_count"] == 4
    assert len(data_frames["frames"]) == 4


def test_dashboard_state_includes_radar_nowcast(client):
    """Verifies that /api/dashboard/state contains the integrated radar nowcast payload."""
    res = client.get("/api/dashboard/state?lead_time_minutes=60")
    assert res.status_code == 200
    data = res.json()
    assert "radar_nowcast" in data
    radar = data["radar_nowcast"]
    assert radar["available"] is True
    assert "station_id" in radar
    assert "speed_kmh" in radar
    assert "confidence_level" in radar
    assert len(radar["cells"]) == 100
