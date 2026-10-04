from __future__ import annotations

import duckdb

from pipeline.config import Settings
from pipeline.quality.report import load_quality_summary, render_quality_report

EXPECTED_CHECK_COUNTS = {
    "actual_finish_before_start": 60,
    "job_missing_estimate": 2,
    "missing_ledger_job": 120,
    "unmapped_ledger_cost_code": 250,
    "duplicate_job_id": 1,
    "duplicate_ledger_posting": 3_619,
    "equipment_job_suffix_corrected": 25,
    "missing_current_estimate": 44,
    "equipment_non_data_row": 2,
    "schedule_percentage_scaled": 298,
}


def test_quality_issue_counts_are_stable(modeled_settings: Settings) -> None:
    summary = load_quality_summary(modeled_settings.database_path)

    assert summary.total_issues == 4_421
    assert dict(summary.severity_counts) == {
        "error": 432,
        "warning": 3_689,
        "info": 300,
    }
    assert {name: count for _, name, count in summary.check_counts} == EXPECTED_CHECK_COUNTS

    report = render_quality_report(summary)
    assert "Data-quality issues: 4,421" in report
    assert "duplicate_ledger_posting" in report


def test_quality_issues_retain_source_lineage(modeled_settings: Settings) -> None:
    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        null_lineage_count = connection.execute(
            """
            SELECT count(*)
            FROM dq_issues
            WHERE source_file IS NULL OR source_row IS NULL
            """
        ).fetchone()[0]
        assert null_lineage_count == 0
