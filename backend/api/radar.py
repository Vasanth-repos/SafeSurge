"""
REST API Router — Radar Rainfall Nowcasting:
Provides endpoints for Doppler radar sweeps, storm advection tracking vectors,
and 0-3 hour spatial nowcast horizons.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Query

from flood_engine.radar_nowcast import (
    RadarNowcastEngine,
    SyntheticRadarSimulator,
    TemporalStormTracker,
)

router = APIRouter(prefix="/api/radar", tags=["Radar Nowcast"])

# Singleton engine and simulator
_simulator = SyntheticRadarSimulator(grid_size=10)
_engine = RadarNowcastEngine()
_tracker = TemporalStormTracker()


@router.get("/nowcast")
def get_radar_nowcast(
    lead_time_minutes: int = Query(0, ge=0, le=180, description="Forecast lead time in minutes (0 to 180)"),
    elapsed_minutes: int = Query(60, ge=0, le=180, description="Current simulation time in minutes"),
) -> dict[str, Any]:
    """
    Returns the spatial radar nowcast grid and hydrometeorological parameters for the requested lead time.
    """
    curr_frame = _simulator.generate_sweep(elapsed_minutes=elapsed_minutes)
    prev_m = max(0, elapsed_minutes - 10)
    prev_frame = _simulator.generate_sweep(elapsed_minutes=prev_m)

    motion = _tracker.track(prev_frame, curr_frame)
    nowcast_results = _engine.generate_nowcast(
        current_frame=curr_frame,
        previous_frame=prev_frame,
        lead_times_minutes=[lead_time_minutes],
    )
    horizon = nowcast_results.get(lead_time_minutes)

    return {
        "status": "ONLINE",
        "radar_station": curr_frame.radar_station_id,
        "frequency_band": curr_frame.frequency_band,
        "elapsed_minutes": elapsed_minutes,
        "lead_time_minutes": lead_time_minutes,
        "timestamp_seconds": horizon.timestamp_seconds if horizon else curr_frame.timestamp_seconds,
        "motion_tracking": {
            "speed_kmh": motion.speed_kmh,
            "direction_degrees": motion.direction_degrees,
            "cardinal_direction": _degrees_to_cardinal(motion.direction_degrees),
            "growth_rate_dbz_hr": motion.growth_rate_dbz_per_hour,
            "storm_centroid": {"col": motion.centroid_x, "row": motion.centroid_y},
        },
        "nowcast": horizon.to_dict() if horizon else {},
    }


@router.get("/tracking")
def get_storm_tracking(
    elapsed_minutes: int = Query(60, ge=0, le=180),
) -> dict[str, Any]:
    """
    Returns the real-time storm centroid, velocity vector, and advection trajectory.
    """
    curr_frame = _simulator.generate_sweep(elapsed_minutes=elapsed_minutes)
    prev_frame = _simulator.generate_sweep(elapsed_minutes=max(0, elapsed_minutes - 10))
    motion = _tracker.track(prev_frame, curr_frame)

    return {
        "radar_station": curr_frame.radar_station_id,
        "elapsed_minutes": elapsed_minutes,
        "speed_kmh": motion.speed_kmh,
        "direction_degrees": motion.direction_degrees,
        "cardinal_direction": _degrees_to_cardinal(motion.direction_degrees),
        "growth_rate_dbz_hr": motion.growth_rate_dbz_per_hour,
        "centroid": {"x_km": motion.centroid_x, "y_km": motion.centroid_y},
        "mean_reflectivity_dbz": round(curr_frame.compute_mean_dbz(), 1),
        "peak_reflectivity_dbz": round(curr_frame.compute_peak_dbz(), 1),
    }


@router.get("/frames")
def get_recent_radar_frames(
    elapsed_minutes: int = Query(60, ge=0, le=180),
) -> dict[str, Any]:
    """
    Returns sequence of recent Doppler sweeps (T-15m, T-10m, T-5m, NOW) for temporal animation.
    """
    steps = [max(0, elapsed_minutes - 15), max(0, elapsed_minutes - 10), max(0, elapsed_minutes - 5), elapsed_minutes]
    frames = [_simulator.generate_sweep(m).to_dict() for m in steps]

    return {
        "station": "DWR-MET-01",
        "current_time_minutes": elapsed_minutes,
        "frames_count": len(frames),
        "frames": frames,
    }


def _degrees_to_cardinal(deg: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((deg + 11.25) / 22.5) % 16
    return dirs[idx]
