from __future__ import annotations

import duckdb

from pipeline.config import Settings
from pipeline.transform.runner import transform_all

EXPECTED_COUNTS = {
    "ref_cost_code_map": 21,
    "stg_jobs": 42,
    "stg_estimates": 618,
    "stg_job_cost_ledger": 359_096,
    "stg_schedule_activities": 1_193,
    "stg_equipment": 215,
    "stg_correspondence": 1_200,
    "dq_issues": 4_421,
}


def test_transform_is_complete_and_idempotent(modeled_settings: Settings) -> None:
    results = transform_all(modeled_settings)
    assert {result.table_name: result.row_count for result in results} == EXPECTED_COUNTS

    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        for table_name, expected_count in EXPECTED_COUNTS.items():
            actual_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            assert actual_count == expected_count

        run_statuses = connection.execute(
            "SELECT status, count(*) FROM meta_transformation_runs GROUP BY status"
        ).fetchall()
        assert run_statuses == [("completed", 2)]


def test_known_cleaning_rules(modeled_settings: Settings) -> None:
    with duckdb.connect(str(modeled_settings.database_path), read_only=True) as connection:
        assertions = {
            "SELECT count(*) FROM stg_jobs WHERE is_duplicate_source": 1,
            "SELECT count(*) FROM stg_estimates WHERE is_current_estimate_missing": 44,
            "SELECT count(*) FROM stg_job_cost_ledger WHERE is_exact_duplicate": 3_619,
            "SELECT count(*) FROM stg_job_cost_ledger WHERE is_missing_job_id": 120,
            "SELECT count(*) FROM stg_job_cost_ledger WHERE is_unmapped_cost_code": 250,
            "SELECT count(*) FROM stg_schedule_activities WHERE is_percentage_scaled": 298,
            """
                SELECT count(*) FROM stg_schedule_activities
                WHERE is_actual_finish_before_start
            """: 60,
            "SELECT count(*) FROM stg_equipment WHERE is_job_suffix_corrected": 25,
            "SELECT count(*) FROM stg_equipment WHERE is_unknown_job": 0,
        }
        for query, expected_count in assertions.items():
            assert connection.execute(query).fetchone()[0] == expected_count

        mapping = connection.execute(
            """
            SELECT erp_cost_code, estimate_cost_code
            FROM ref_cost_code_map
            WHERE erp_cost_code IN ('02-200', '02-300', '99-999')
            ORDER BY erp_cost_code
            """
        ).fetchall()
        assert mapping == [
            ("02-200", "2200"),
            ("02-300", "2100"),
            ("99-999", None),
        ]
