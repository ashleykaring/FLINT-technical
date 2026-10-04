from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from pipeline.config import Settings
from pipeline.quality.checks import create_quality_issues

SQL_FILES = (
    "stg_cost_code_map.sql",
    "stg_jobs.sql",
    "stg_estimates.sql",
    "stg_job_cost_ledger.sql",
    "stg_schedule_activities.sql",
    "stg_equipment.sql",
    "stg_correspondence.sql",
)

REQUIRED_RAW_TABLES = (
    "raw_jobs",
    "raw_estimate_api_line_items",
    "raw_job_cost_ledger",
    "raw_schedule_activities",
    "raw_equipment",
    "raw_correspondence",
)

OUTPUT_TABLES = (
    "ref_cost_code_map",
    "stg_jobs",
    "stg_estimates",
    "stg_job_cost_ledger",
    "stg_schedule_activities",
    "stg_equipment",
    "stg_correspondence",
    "dq_issues",
)


@dataclass(frozen=True)
class TransformationResult:
    table_name: str
    row_count: int


class TransformationError(RuntimeError):
    """Raised when staging tables cannot be built atomically."""


def _create_metadata_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_transformation_runs (
            transformation_run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status VARCHAR NOT NULL,
            error_message VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_transformation_tables (
            transformation_run_id VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            PRIMARY KEY (transformation_run_id, table_name)
        )
        """
    )


def _validate_raw_tables(connection: duckdb.DuckDBPyConnection) -> None:
    existing = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    missing = [table for table in REQUIRED_RAW_TABLES if table not in existing]
    if missing:
        raise TransformationError(
            "missing raw tables; run `flint ingest` first: " + ", ".join(missing)
        )


def _render_sql(sql_path: Path, settings: Settings) -> str:
    sql = sql_path.read_text(encoding="utf-8")
    mapping_path = settings.project_root / "data" / "reference" / "cost_code_map.csv"
    safe_mapping_path = str(mapping_path).replace("'", "''")
    return sql.replace("{{cost_code_map_path}}", safe_mapping_path)


def _validate_cost_code_map(connection: duckdb.DuckDBPyConnection) -> None:
    duplicate_codes = connection.execute(
        """
        SELECT count(*) - count(DISTINCT erp_cost_code)
        FROM ref_cost_code_map
        """
    ).fetchone()[0]
    if duplicate_codes:
        raise TransformationError("cost-code map contains duplicate ERP codes")

    missing_ledger_codes = connection.execute(
        """
        SELECT count(*)
        FROM (
            SELECT DISTINCT trim(cost_code) AS erp_cost_code
            FROM raw_job_cost_ledger
        ) AS ledger_codes
        LEFT JOIN ref_cost_code_map USING (erp_cost_code)
        WHERE ref_cost_code_map.erp_cost_code IS NULL
        """
    ).fetchone()[0]
    if missing_ledger_codes:
        raise TransformationError(f"cost-code map is missing {missing_ledger_codes} ledger codes")

    invalid_targets = connection.execute(
        """
        SELECT count(*)
        FROM ref_cost_code_map AS mapping
        WHERE mapping.mapping_status = 'mapped'
          AND NOT EXISTS (
              SELECT 1
              FROM raw_estimate_api_line_items AS estimates
              WHERE estimates.cost_code = mapping.estimate_cost_code
          )
        """
    ).fetchone()[0]
    if invalid_targets:
        raise TransformationError(
            f"cost-code map contains {invalid_targets} unknown estimating codes"
        )


def transform_all(settings: Settings) -> list[TransformationResult]:
    if not settings.database_path.is_file():
        raise TransformationError(
            f"DuckDB database does not exist; run `flint ingest` first: {settings.database_path}"
        )

    sql_dir = Path(__file__).resolve().parent / "sql"
    mapping_path = settings.project_root / "data" / "reference" / "cost_code_map.csv"
    if not mapping_path.is_file():
        raise TransformationError(f"cost-code mapping does not exist: {mapping_path}")

    run_id = str(uuid4())
    connection = duckdb.connect(str(settings.database_path))
    _create_metadata_tables(connection)
    connection.execute(
        """
        INSERT INTO meta_transformation_runs
        (transformation_run_id, started_at, status)
        VALUES (?, ?, 'running')
        """,
        [run_id, datetime.now(UTC)],
    )

    try:
        _validate_raw_tables(connection)
        connection.execute("BEGIN TRANSACTION")
        for filename in SQL_FILES:
            connection.execute(_render_sql(sql_dir / filename, settings))
            if filename == "stg_cost_code_map.sql":
                _validate_cost_code_map(connection)

        create_quality_issues(connection)

        results = []
        for table_name in OUTPUT_TABLES:
            row_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            result = TransformationResult(table_name, row_count)
            results.append(result)
            connection.execute(
                "INSERT INTO meta_transformation_tables VALUES (?, ?, ?)",
                [run_id, table_name, row_count],
            )

        connection.execute(
            """
            UPDATE meta_transformation_runs
            SET status = 'completed', completed_at = ?
            WHERE transformation_run_id = ?
            """,
            [datetime.now(UTC), run_id],
        )
        connection.execute("COMMIT")
    except Exception as exc:
        connection.execute("ROLLBACK")
        connection.execute(
            """
            UPDATE meta_transformation_runs
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE transformation_run_id = ?
            """,
            [datetime.now(UTC), str(exc), run_id],
        )
        if isinstance(exc, TransformationError):
            raise
        raise TransformationError(f"unexpected transformation failure: {exc}") from exc
    finally:
        connection.close()

    return results
