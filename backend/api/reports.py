"""
API Endpoints — Prediction Reports & Export:
Generates and serves downloadable dynamic Flood Prediction & Advisory Reports in .docx format.
Adapts dynamically to the exact live simulation state, current lead time, injected faults, and routing.
"""

import os

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from backend.api.snapshots import get_snapshot_service
from replay.scenarios import ScenarioRunner
from reporting.docx_generator import create_3hour_prediction_docx

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/download-docx")
def download_3hour_docx_report(
    scenario_id: str = Query("storm_01", description="Scenario ID to generate report for"),
    lead_time_minutes: int = Query(0, ge=0, description="Current forecast lead time in minutes"),
    fault_spike: bool = Query(False, description="Simulate sensor surge anomaly"),
    fault_offline: bool = Query(False, description="Simulate sensor dropout"),
    fault_blockage: bool = Query(False, description="Simulate culvert drainage blockage"),
):
    """
    Generates and downloads a comprehensive, dynamic flood prediction report in DOCX format,
    tailored to the exact live scenario, forecast lead time, and active fault injection state.
    """
    try:
        service = get_snapshot_service()
        # Retrieve all snapshots for the scenario timeline
        service.ensure_scenario_loaded(scenario_id)
        timestamps = service.get_all_timestamps(scenario_id)
        snapshots = [service.get_snapshot(scenario_id, t) for t in timestamps if service.get_snapshot(scenario_id, t) is not None]

        if not snapshots:
            # Fallback to runner
            runner = ScenarioRunner(config_path="config.yaml")
            yaml_path = f"config/scenarios/{scenario_id}.yaml" if os.path.exists(f"config/scenarios/{scenario_id}.yaml") else "config/scenarios/storm_01.yaml"
            snapshots = runner.run(yaml_path)

        # Retrieve dynamic live state matching the dashboard view
        live_state = service.get_dashboard_state(
            lead_time_minutes=lead_time_minutes,
            scenario_id=scenario_id,
            fault_spike=fault_spike,
            fault_offline=fault_offline,
            fault_blockage=fault_blockage,
        )

        active_faults_dict = {
            "spike": fault_spike,
            "offline": fault_offline,
            "blockage": fault_blockage,
        }

        # Construct specific output filename reflecting current state
        fault_tag = ""
        if fault_spike:
            fault_tag += "_surge"
        if fault_offline:
            fault_tag += "_drop"
        if fault_blockage:
            fault_tag += "_clog"

        doc_filename = f"SafeSurge_Advisory_{scenario_id}_t{lead_time_minutes}m{fault_tag}.docx"
        output_path = os.path.join("outputs", "reports", doc_filename)

        create_3hour_prediction_docx(
            snapshots=snapshots,
            scenario_id=scenario_id,
            output_path=output_path,
            lead_time_minutes=lead_time_minutes,
            live_state=live_state,
            active_faults=active_faults_dict,
        )

        return FileResponse(
            path=output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=doc_filename,
            headers={"Content-Disposition": f'attachment; filename="{doc_filename}"'},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to generate DOCX report: {e!s}"},
        )
