from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from pipeline.config import Settings

SQL_FILES = (
    "dim_job.sql",
    "dim_cost_code.sql",
    "dim_subcontractor.sql",
    "fact_cost_transaction.sql",
    "fact_budget.sql",
    "fact_schedule_activity.sql",
    "fact_equipment_usage.sql",
    "mart_job_financial.sql",
    "mart_cost_vs_progress.sql",
    "mart_equipment_economics.sql",
    "mart_subcontractor_exposure.sql",
    "mart_cost_code_exposure.sql",
    "mart_portfolio_risk.sql",
    "model_reconciliation.sql",
)

REQUIRED_STAGING_TABLES = (
    "stg_jobs",
    "stg_estimates",
    "stg_job_cost_ledger",
    "stg_schedule_activities",
    "stg_equipment",
    "stg_correspondence",
    "ref_cost_code_map",
    "dq_issues",
)

OUTPUT_TABLES = (
    "dim_job",
    "dim_cost_code",
    "dim_subcontractor",
    "fact_cost_transaction",
    "fact_budget",
    "fact_schedule_activity",
    "fact_equipment_usage",
    "mart_job_financial",
    "mart_cost_vs_progress",
    "mart_equipment_economics",
    "mart_subcontractor_exposure",
    "mart_cost_code_exposure",
    "mart_portfolio_risk",
    "model_reconciliation",
)


@dataclass(frozen=True)
class ModelBuildResult:
    table_name: str
    row_count: int


class ModelBuildError(RuntimeError):
    """Raised when the dimensional model cannot be built atomically."""


def _create_metadata_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_model_runs (
            model_run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status VARCHAR NOT NULL,
            error_message VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_model_tables (
            model_run_id VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            PRIMARY KEY (model_run_id, table_name)
        )
        """
    )


def _validate_required_tables(connection: duckdb.DuckDBPyConnection) -> None:
    existing = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    missing = [table for table in REQUIRED_STAGING_TABLES if table not in existing]
    if missing:
        raise ModelBuildError(
            "missing staging tables; run `flint transform` first: " + ", ".join(missing)
        )


def _validate_model_keys(connection: duckdb.DuckDBPyConnection) -> None:
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
        duplicate_count = connection.execute(
            f"""
            SELECT count(*) - count(DISTINCT "{key_name}")
            FROM "{table_name}"
            """
        ).fetchone()[0]
        if duplicate_count:
            raise ModelBuildError(
                f"{table_name}.{key_name} contains {duplicate_count} duplicate keys"
            )


def _validate_fact_relationships(connection: duckdb.DuckDBPyConnection) -> None:
    relationship_checks = (
        (
            "fact_cost_transaction.job_key",
            """
            SELECT count(*) FROM fact_cost_transaction AS fact
            LEFT JOIN dim_job AS dimension USING (job_key)
            WHERE dimension.job_key IS NULL
            """,
        ),
        (
            "fact_cost_transaction.cost_code_key",
            """
            SELECT count(*) FROM fact_cost_transaction AS fact
            LEFT JOIN dim_cost_code AS dimension USING (cost_code_key)
            WHERE dimension.cost_code_key IS NULL
            """,
        ),
        (
            "fact_cost_transaction.subcontractor_key",
            """
            SELECT count(*) FROM fact_cost_transaction AS fact
            LEFT JOIN dim_subcontractor AS dimension USING (subcontractor_key)
            WHERE dimension.subcontractor_key IS NULL
            """,
        ),
        (
            "fact_budget keys",
            """
            SELECT count(*)
            FROM fact_budget AS fact
            LEFT JOIN dim_job AS jobs USING (job_key)
            LEFT JOIN dim_cost_code AS codes USING (cost_code_key)
            WHERE jobs.job_key IS NULL OR codes.cost_code_key IS NULL
            """,
        ),
        (
            "fact_schedule_activity.job_key",
            """
            SELECT count(*) FROM fact_schedule_activity AS fact
            LEFT JOIN dim_job AS dimension USING (job_key)
            WHERE dimension.job_key IS NULL
            """,
        ),
        (
            "fact_equipment_usage.job_key",
            """
            SELECT count(*) FROM fact_equipment_usage AS fact
            LEFT JOIN dim_job AS dimension USING (job_key)
            WHERE dimension.job_key IS NULL
            """,
        ),
    )
    for relationship_name, query in relationship_checks:
        orphan_count = connection.execute(query).fetchone()[0]
        if orphan_count:
            raise ModelBuildError(f"{relationship_name} contains {orphan_count} orphaned fact rows")


def _validate_reconciliation(connection: duckdb.DuckDBPyConnection) -> None:
    failed_checks = connection.execute(
        "SELECT count(*) FROM model_reconciliation WHERE NOT passed"
    ).fetchone()[0]
    if failed_checks:
        raise ModelBuildError(f"{failed_checks} model reconciliation checks failed")


def build_model(settings: Settings) -> list[ModelBuildResult]:
    if not settings.database_path.is_file():
        raise ModelBuildError(
            f"DuckDB database does not exist; run `flint build` first: {settings.database_path}"
        )

    sql_dir = Path(__file__).resolve().parent / "sql"
    run_id = str(uuid4())
    connection = duckdb.connect(str(settings.database_path))
    _create_metadata_tables(connection)
    connection.execute(
        """
        INSERT INTO meta_model_runs (model_run_id, started_at, status)
        VALUES (?, ?, 'running')
        """,
        [run_id, datetime.now(UTC)],
    )

    transaction_open = False
    try:
        _validate_required_tables(connection)
        connection.execute("BEGIN TRANSACTION")
        transaction_open = True
        for filename in SQL_FILES:
            sql = (sql_dir / filename).read_text(encoding="utf-8")
            connection.execute(sql)

        _validate_model_keys(connection)
        _validate_fact_relationships(connection)
        _validate_reconciliation(connection)

        results = []
        for table_name in OUTPUT_TABLES:
            row_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            result = ModelBuildResult(table_name, row_count)
            results.append(result)
            connection.execute(
                "INSERT INTO meta_model_tables VALUES (?, ?, ?)",
                [run_id, table_name, row_count],
            )

        connection.execute(
            """
            UPDATE meta_model_runs
            SET status = 'completed', completed_at = ?
            WHERE model_run_id = ?
            """,
            [datetime.now(UTC), run_id],
        )
        connection.execute("COMMIT")
        transaction_open = False
    except Exception as exc:
        if transaction_open:
            connection.execute("ROLLBACK")
        connection.execute(
            """
            UPDATE meta_model_runs
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE model_run_id = ?
            """,
            [datetime.now(UTC), str(exc), run_id],
        )
        if isinstance(exc, ModelBuildError):
            raise
        raise ModelBuildError(f"unexpected model-build failure: {exc}") from exc
    finally:
        connection.close()

    return results
