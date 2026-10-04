from __future__ import annotations

from pathlib import Path

import duckdb

from pipeline.config import Settings
from pipeline.ingest.runner import ingest_all

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_COUNTS = {
    "raw_jobs": 43,
    "raw_estimate_csv": 618,
    "raw_job_cost_ledger": 359_096,
    "raw_schedule_activities": 1_193,
    "raw_estimate_api_projects": 40,
    "raw_estimate_api_line_items": 618,
    "raw_equipment": 217,
    "raw_correspondence": 1_200,
}


def test_ingestion_is_complete_and_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "flint-test.duckdb"
    settings = Settings.from_root(PROJECT_ROOT, database_path)

    first_results = ingest_all(settings)
    second_results = ingest_all(settings)

    assert {result.table_name: result.row_count for result in first_results} == EXPECTED_COUNTS
    assert {result.table_name: result.row_count for result in second_results} == EXPECTED_COUNTS

    with duckdb.connect(str(database_path), read_only=True) as connection:
        for table_name, expected_count in EXPECTED_COUNTS.items():
            actual_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            assert actual_count == expected_count

        run_statuses = connection.execute(
            "SELECT status, count(*) FROM meta_ingestion_runs GROUP BY status"
        ).fetchall()
        assert run_statuses == [("completed", 2)]

        source_run_count = connection.execute(
            "SELECT count(DISTINCT ingestion_run_id) FROM meta_ingestion_sources"
        ).fetchone()[0]
        assert source_run_count == 2

        lineage_null_count = connection.execute(
            """
            SELECT count(*)
            FROM raw_correspondence
            WHERE _source_file IS NULL
               OR _source_row IS NULL
               OR _ingestion_run_id IS NULL
               OR _ingested_at IS NULL
               OR _record_hash IS NULL
            """
        ).fetchone()[0]
        assert lineage_null_count == 0
