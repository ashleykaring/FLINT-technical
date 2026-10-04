from __future__ import annotations

import duckdb

from pipeline.config import Settings
from pipeline.model.runner import build_model

EXPECTED_COUNTS = {
    "dim_job": 43,
    "dim_cost_code": 21,
    "dim_subcontractor": 61,
    "fact_cost_transaction": 355_477,
    "fact_budget": 618,
    "fact_schedule_activity": 1_193,
    "fact_equipment_usage": 215,
    "mart_job_financial": 42,
    "mart_cost_vs_progress": 42,
    "mart_equipment_economics": 4,
    "mart_subcontractor_exposure": 60,
    "mart_cost_code_exposure": 21,
    "mart_portfolio_risk": 42,
    "model_reconciliation": 5,
}


def test_model_is_complete_and_idempotent(modeled_settings: Settings) -> None:
    results = build_model(modeled_settings)
    assert {result.table_name: result.row_count for result in results} == EXPECTED_COUNTS

    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        for table_name, expected_count in EXPECTED_COUNTS.items():
            actual_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            assert actual_count == expected_count

        run_statuses = connection.execute(
            "SELECT status, count(*) FROM meta_model_runs GROUP BY status"
        ).fetchall()
        assert run_statuses == [("completed", 2)]


def test_model_keys_and_relationships_are_valid(modeled_settings: Settings) -> None:
    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        key_definitions = (
            ("dim_job", "job_key"),
            ("dim_cost_code", "cost_code_key"),
            ("dim_subcontractor", "subcontractor_key"),
            ("fact_cost_transaction", "cost_transaction_key"),
            ("fact_budget", "budget_key"),
            ("fact_schedule_activity", "schedule_activity_key"),
            ("fact_equipment_usage", "equipment_usage_key"),
        )
        for table_name, key_name in key_definitions:
            total, unique, nulls = connection.execute(
                f"""
                SELECT
                    count(*),
                    count(DISTINCT "{key_name}"),
                    count(*) FILTER (WHERE "{key_name}" IS NULL)
                FROM "{table_name}"
                """
            ).fetchone()
            assert (total, nulls) == (unique, 0)

        orphan_count = connection.execute(
            """
            SELECT count(*)
            FROM fact_cost_transaction AS facts
            LEFT JOIN dim_job AS jobs USING (job_key)
            LEFT JOIN dim_cost_code AS codes USING (cost_code_key)
            LEFT JOIN dim_subcontractor AS subcontractors USING (subcontractor_key)
            WHERE jobs.job_key IS NULL
               OR codes.cost_code_key IS NULL
               OR subcontractors.subcontractor_key IS NULL
            """
        ).fetchone()[0]
        assert orphan_count == 0


def test_source_rows_and_dollars_reconcile(modeled_settings: Settings) -> None:
    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        failed_checks = connection.execute(
            "SELECT count(*) FROM model_reconciliation WHERE NOT passed"
        ).fetchone()[0]
        assert failed_checks == 0

        source_rows, duplicate_rows, source_amount, duplicate_amount = connection.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (WHERE is_exact_duplicate),
                sum(amount),
                coalesce(sum(amount) FILTER (WHERE is_exact_duplicate), 0)
            FROM stg_job_cost_ledger
            """
        ).fetchone()
        modeled_rows, modeled_amount = connection.execute(
            "SELECT count(*), sum(amount) FROM fact_cost_transaction"
        ).fetchone()

        assert source_rows - duplicate_rows == modeled_rows
        assert source_amount - duplicate_amount == modeled_amount


def test_quarantined_records_and_metric_formulas_are_explicit(
    modeled_settings: Settings,
) -> None:
    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        unknown_job_rows = connection.execute(
            """
            SELECT count(*)
            FROM fact_cost_transaction
            WHERE job_key = 'UNKNOWN_JOB'
            """
        ).fetchone()[0]
        unmapped_cost_rows = connection.execute(
            """
            SELECT count(*)
            FROM fact_cost_transaction
            WHERE cost_code_key = 'UNMAPPED_COST_CODE'
            """
        ).fetchone()[0]
        fallback_budget_rows = connection.execute(
            "SELECT count(*) FROM fact_budget WHERE used_original_estimate_fallback"
        ).fetchone()[0]

        assert unknown_job_rows > 0
        assert unmapped_cost_rows > 0
        assert fallback_budget_rows == 44

        invalid_metric_rows = connection.execute(
            """
            SELECT count(*)
            FROM mart_job_financial
            WHERE abs(
                projected_final_cost - adjusted_actual_cost - forecast_remaining
            ) > 0.01
               OR abs(
                   projected_margin - contract_value_proxy + projected_final_cost
               ) > 0.01
            """
        ).fetchone()[0]
        assert invalid_metric_rows == 0
