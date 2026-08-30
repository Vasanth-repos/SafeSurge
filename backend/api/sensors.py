"""
API Endpoints — Sensor Telemetry Ingestion & Health:
Ingests physical/simulated sensor packets, applies Layer 11-12 validation, and reports device health.
"""

from fastapi import APIRouter, Depends

from backend.dependencies import get_simulation_manager
from backend.schemas import SensorReadingRequest
from backend.services.simulation_manager import SimulationManager
from sensors.models import MeasurementStatus, SensorEnvelope

router = APIRouter(prefix="/api/sensors", tags=["Sensors"])


@router.post("/reading")
def ingest_sensor_reading(
    reading: SensorReadingRequest,
    manager: SimulationManager = Depends(get_simulation_manager),
):
    float_trig = reading.float_state.upper() in ("WATER_PRESENT", "TRUE", "1")
    env = SensorEnvelope(
        sensor_id=reading.sensor_id,
        boot_id=reading.boot_id,
        sequence=reading.sequence,
        measured_at_seconds=reading.timestamp_seconds,
        received_at_seconds=reading.timestamp_seconds,
        distance_samples_cm=(reading.distance_cm, reading.distance_cm, reading.distance_cm),
        float_triggered=float_trig,
    )

    res = manager.sensor_validator.validate(env)
    return {
        "sensor_id": res.sensor_id,
        "accepted": (res.measurement_status == MeasurementStatus.ACCEPTED),
        "measurement_status": res.measurement_status.value,
        "rejection_reason": res.rejection_reason.value,
        "sensor_state": res.sensor_state.value,
        "water_level_cm": res.water_level_cm,
        "timestamp_seconds": res.measured_at_seconds,
    }


@router.get("/status")
def get_sensors_status(
    manager: SimulationManager = Depends(get_simulation_manager),
):
    now_t = 0
    return {
        "sensors": [
            {
                "sensor_id": sid,
                "location_id": cfg.location_id,
                "enabled": cfg.enabled,
                "health": manager.sensor_validator.health_tracker.get_state(sid, now_t).value,
            }
            for sid, cfg in manager.sensor_registry._sensors.items()
        ]
    }
