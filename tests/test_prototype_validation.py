"""
Layer 26 Unit & Integration Test Suite:
Verifies automated Prototype Health Check, invariant assertions, fault resilience,
and recovery suites.
"""

from prototype_validation.models import CheckStatus
from prototype_validation.runner import PrototypeValidationRunner


def test_full_prototype_validation_report_pass():
    runner = PrototypeValidationRunner("config.yaml")
    report = runner.validate_normal_scenario("config/scenarios/e2e_validation.yaml")

    assert report.status == CheckStatus.PASS
    assert report.timestep_count == 181
    assert report.summary["failed_checks"] == 0
    assert report.summary["passed_checks"] >= 10


def test_fault_suite_resilience_pass():
    runner = PrototypeValidationRunner("config.yaml")
    fault_results = runner.validate_fault_suite()

    assert len(fault_results) == 7
    assert all(r.status == CheckStatus.PASS for r in fault_results)


def test_recovery_suite_pass():
    runner = PrototypeValidationRunner("config.yaml")
    recovery_results = runner.validate_recovery_suite()

    assert len(recovery_results) == 2
    assert all(r.status == CheckStatus.PASS for r in recovery_results)
