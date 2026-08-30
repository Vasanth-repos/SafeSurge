"""
API Endpoints — Snapshots (Layers 20–25):
Direct immutable snapshot inspection by simulation_id and timestamp_seconds.
"""

from fastapi import APIRouter, HTTPException, status

from backend.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/snapshots", tags=["Snapshots"])
_snapshot_service = SnapshotService()


def get_snapshot_service() -> SnapshotService:
    return _snapshot_service


@router.get("/{simulation_id}/{timestamp_seconds}")
def get_exact_snapshot(
    simulation_id: str,
    timestamp_seconds: int,
):
    snap = _snapshot_service.get_snapshot(simulation_id, timestamp_seconds)
    if not snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SNAPSHOT_NOT_FOUND",
                "simulation_id": simulation_id,
                "timestamp_seconds": timestamp_seconds,
            },
        )
    return snap.to_dict()


@router.get("/{simulation_id}")
def get_simulation_timeline(
    simulation_id: str,
):
    timestamps = _snapshot_service.get_all_timestamps(simulation_id)
    if not timestamps:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SIMULATION_NOT_FOUND", "simulation_id": simulation_id},
        )
    return {
        "simulation_id": simulation_id,
        "timestamps_seconds": timestamps,
        "count": len(timestamps),
    }
