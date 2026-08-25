"""
Layer 26 — Validation Report Formatter & Exporter:
Generates machine-readable JSON reports and formatted human-readable ASCII summary files.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from prototype_validation.models import ValidationReport, CheckStatus


def export_validation_reports(
    report: ValidationReport,
    output_dir: str = "outputs/validation",
) -> Tuple[str, str]:
    """
    Exports both validation_report.json and validation_report.txt.
    Returns (json_path, txt_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "validation_report.json")
    txt_path = os.path.join(output_dir, "validation_report.txt")

    # 1. Machine-readable JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    # 2. Human-readable ASCII Summary
    lines = [
        "=" * 60,
        "URBAN FLOOD NOWCASTING & RESPONSE SYSTEM",
        "LAYER 26 — END-TO-END PROTOTYPE VALIDATION REPORT",
        "=" * 60,
        f"Validation ID:   {report.validation_id}",
        f"Scenario ID:     {report.scenario_id}",
        f"Started At:      {report.started_at}",
        f"Completed At:    {report.completed_at}",
        f"Timestep Count:  {report.timestep_count}",
        f"Overall Status:  {report.status.value}",
        "-" * 60,
        "SUMMARY OF CHECKS:",
        f"  Total Checks:    {report.summary['total_checks']}",
        f"  Passed:          {report.summary['passed_checks']}",
        f"  Warnings:        {report.summary['warning_checks']}",
        f"  Failed:          {report.summary['failed_checks']}",
        "-" * 60,
        "CHECK DETAILS:",
    ]

    for check in report.checks:
        stat_tag = f"[{check.status.value}]"
        lines.append(f"  {stat_tag:<8} {check.check_id:<12} {check.name}")
        lines.append(f"           Message: {check.message}")

    lines.extend([
        "=" * 60,
        f"FINAL RESULT: {report.status.value}",
        "=" * 60,
    ])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return json_path, txt_path
