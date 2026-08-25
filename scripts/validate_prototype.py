import sys
import os
from pathlib import Path

# Add project root to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from prototype_validation.runner import PrototypeValidationRunner
from prototype_validation.models import CheckStatus, ValidationReport
from prototype_validation.report import export_validation_reports


def main():
    parser = argparse.ArgumentParser(description="End-to-End Prototype Validation & Health Check")
    parser.add_argument("--scenario", default="config/scenarios/e2e_validation.yaml", help="Path to scenario YAML")
    parser.add_argument("--fault-suite", action="store_true", help="Execute 7-fault resilience suite")
    parser.add_argument("--recovery-suite", action="store_true", help="Execute recovery verification suite")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON to stdout")

    args = parser.parse_args()

    runner = PrototypeValidationRunner()

    if args.fault_suite:
        print("Executing 7-Fault Resilience Suite...")
        results = runner.validate_fault_suite()
        for r in results:
            print(f"[{r.status.value}] {r.check_id:<25} {r.name}: {r.message}")
        all_pass = all(r.status == CheckStatus.PASS for r in results)
        sys.exit(0 if all_pass else 2)

    if args.recovery_suite:
        print("Executing Subsystem Recovery Suite...")
        results = runner.validate_recovery_suite()
        for r in results:
            print(f"[{r.status.value}] {r.check_id:<25} {r.name}: {r.message}")
        all_pass = all(r.status == CheckStatus.PASS for r in results)
        sys.exit(0 if all_pass else 2)

    # Master E2E Validation Run
    report = runner.validate_normal_scenario(args.scenario)
    json_path, txt_path = export_validation_reports(report)

    if args.json:
        import json
        print(json.dumps(report.to_dict(), indent=2))
    else:
        with open(txt_path, "r", encoding="utf-8") as f:
            print(f.read())
        print(f"Reports written to:\n  - {json_path}\n  - {txt_path}\n")

    if report.status == CheckStatus.PASS:
        sys.exit(0)
    elif report.status == CheckStatus.WARN:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
