"""
Sensor reading ingestion and status query API endpoints.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from backend.models.schemas import SensorReadingRequest, SensorStatusResponse

router = APIRouter(prefix="/api/sensors", tags=["Sensors"])


def get_sim_service():
    from backend.app import sim_service
    return sim_service


@router.post("/reading")
def ingest_sensor_reading(payload: SensorReadingRequest, sim=Depends(get_sim_service)):
    """
    Ingests live telemetry from an ultrasonic or float sensor node.
    """
    if payload.sensor_id not in sim.sensors:
        raise HTTPException(status_code=404, detail=f"Sensor ID {payload.sensor_id} not found")

    sensor_dict = {
        payload.sensor_id: {
            "water_level_cm": payload.water_level_cm,
            "float_state": payload.float_state,
            "battery": payload.battery,
            "signal_quality": payload.signal_quality,
            "heartbeat": payload.heartbeat,
        }
    }
    res = sim.step(rainfall_input=0.0, sensor_readings=sensor_dict)
    sensor = sim.sensors[payload.sensor_id]
    return {
        "status": "success",
        "sensor_id": payload.sensor_id,
        "health": sensor.status,
        "quality_flag": sensor.last_quality_flag,
        "current_bias_cm": round(sensor.current_bias, 2),
    }


@router.get("", response_model=List[SensorStatusResponse])
def get_all_sensors(sim=Depends(get_sim_service)):
    """
    Lists all deployed sensors and their real-time telemetry/health.
    """
    return sim.get_sensors_state()


@router.get("/{sensor_id}/status", response_model=SensorStatusResponse)
def get_sensor_status(sensor_id: int, sim=Depends(get_sim_service)):
    """
    Gets status and recent reading details for a specific sensor.
    """
    if sensor_id not in sim.sensors:
        raise HTTPException(status_code=404, detail=f"Sensor ID {sensor_id} not found")

    s = sim.sensors[sensor_id]
    return {
        "sensor_id": s.sensor_id,
        "name": s.name,
        "cell_id": s.cell_id,
        "status": s.status,
        "sensor_type": s.sensor_type,
        "last_reading_cm": round(s.last_reading_cm, 1) if s.last_reading_cm is not None else None,
        "last_valid_reading_cm": round(s.last_valid_reading_cm, 1) if s.last_valid_reading_cm is not None else None,
        "last_quality_flag": s.last_quality_flag,
        "battery": s.battery,
        "signal_quality": s.signal_quality,
        "current_bias_cm": round(s.current_bias, 2),
        "float_state": s.float_state,
    }
