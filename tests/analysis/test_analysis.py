from __future__ import annotations

import duckdb

from pipeline.analysis.runner import build_analysis
from pipeline.config import Settings


def test_analysis_marts_are_reconciled_and_idempotent(analysis_settings: Settings) -> None:
    first = build_analysis(analysis_settings)
    second = build_analysis(analysis_settings)

    expected_counts = {
        "ref_correspondence_scope_cost_code": 22,
        "mart_correspondence_exposure": 5,
        "mart_job_correspondence_exposure": 42,
        "mart_job_risk_adjusted": 42,
        "mart_job_dashboard": 42,
        "mart_correspondence_cost_code_exposure": 4,
        "mart_subcontractor_combined_exposure": 60,
        "mart_monthly_cost_trend": 15_965,
        "analysis_dq_issues": 0,
        "model_analysis_reconciliation": 8,
    }
    assert {result.table_name: result.row_count for result in first} == expected_counts
    assert {result.table_name: result.row_count for result in second} == expected_counts

    with duckdb.connect(str(analysis_settings.database_path), read_only=True) as connection:
        mapped_codes = connection.execute(
            """
            SELECT doc_id, cost_code_key
            FROM mart_correspondence_exposure
            WHERE scope IS NOT NULL
            ORDER BY doc_id
            """
        ).fetchall()
        assert mapped_codes == [
            ("CO-1", "2200"),
            ("CO-2", "2200"),
            ("CO-3", "31000"),
            ("RFI-1", "33000"),
        ]

        b2100 = connection.execute(
            """
            SELECT
                confirmed_unbooked_cost,
                unbooked_contract_value,
                potential_cost,
                confirmed_margin_adjustment,
                potential_downside_cost
            FROM mart_job_correspondence_exposure
            WHERE job_id = 'B2100'
            """
        ).fetchone()
        assert b2100 == (100, 40, 300, -60, 300)

        invalid_formulas = connection.execute(
            """
            SELECT count(*)
            FROM mart_job_risk_adjusted
            WHERE abs(
                confirmed_adjusted_margin
                - base_projected_margin
                - unbooked_contract_value
                + confirmed_unbooked_cost
            ) > 0.01
               OR abs(
                   downside_scenario_margin
                   - confirmed_adjusted_margin
                   + potential_downside_cost
               ) > 0.01
            """
        ).fetchone()[0]
        assert invalid_formulas == 0

        failed_checks = connection.execute(
            "SELECT count(*) FROM model_analysis_reconciliation WHERE NOT passed"
        ).fetchone()[0]
        assert failed_checks == 0

        run_statuses = connection.execute(
            "SELECT status, count(*) FROM meta_analysis_runs GROUP BY status"
        ).fetchall()
        assert run_statuses == [("completed", 3)]
