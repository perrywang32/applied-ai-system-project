"""
Tests for the end-to-end harness (experiments/run_harness.py).

Verifies that the harness runs the full system, that every defined case passes
its criteria, that the summary is internally consistent, and that the output is
deterministic (identical across runs).
"""

from experiments.run_harness import run


def test_harness_runs_and_all_cases_pass():
    _report, summary = run()
    assert summary["total"] == 6
    assert summary["passed"] == 6
    assert summary["failed"] == 0


def test_harness_summary_is_consistent():
    _report, summary = run()
    assert summary["passed"] + summary["failed"] == summary["total"]
    assert 0.0 <= summary["average_confidence"] <= 1.0
    assert summary["fallback_cases"] >= 1  # the fallback case must activate fallback


def test_harness_output_is_deterministic():
    report_a, summary_a = run()
    report_b, summary_b = run()
    assert report_a == report_b
    assert summary_a == summary_b


def test_report_contains_required_sections():
    report, _summary = run()
    for needed in ["Input profile:", "Top recommendations:", "Confidence:",
                   "Warnings:", "Fallback used:", "Evaluation metrics:",
                   "Result:", "SUMMARY"]:
        assert needed in report
