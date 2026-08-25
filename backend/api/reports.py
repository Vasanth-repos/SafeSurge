"""
API Endpoints — Prediction Reports & Export:
Generates and serves downloadable 3-Hour Flood Prediction Reports in .docx format.
"""

import os
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import FileResponse

from replay.scenarios import ScenarioRunner
from reporting.docx_generator import create_3hour_prediction_docx
from backend.api.snapshots import get_snapshot_service

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/download-docx")
def download_3hour_docx_report(
    scenario_id: str = Query("storm_01", description="Scenario ID to generate report for"),
):
    """Generates and downloads a comprehensive 3-hour flood prediction report in DOCX format."""
    try:
        service = get_snapshot_service()
        # Retrieve all snapshots for the scenario
        service.ensure_scenario_loaded(scenario_id)
        timestamps = service.get_all_timestamps(scenario_id)
        snapshots = [service.get_snapshot(scenario_id, t) for t in timestamps if service.get_snapshot(scenario_id, t) is not None]

        if not snapshots:
            # Fallback to runner
            runner = ScenarioRunner(config_path="config.yaml")
            yaml_path = f"config/scenarios/{scenario_id}.yaml" if os.path.exists(f"config/scenarios/{scenario_id}.yaml") else "config/scenarios/storm_01.yaml"
            snapshots = runner.run(yaml_path)

        output_path = os.path.join("outputs", "reports", f"flood_nowcasting_3hr_report_{scenario_id}.docx")
        create_3hour_prediction_docx(
            snapshots=snapshots,
            scenario_id=scenario_id,
            output_path=output_path,
        )

        return FileResponse(
            path=output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"flood_nowcasting_3hr_report_{scenario_id}.docx",
            headers={"Content-Disposition": f'attachment; filename="flood_nowcasting_3hr_report_{scenario_id}.docx"'},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to generate DOCX report: {str(e)}"},
        )
