from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from pipeline.config import Settings

SQL_FILES = (
    "ref_correspondence_scope_cost_code.sql",
    "mart_correspondence_exposure.sql",
    "mart_job_correspondence_exposure.sql",
    "mart_job_risk_adjusted.sql",
    "mart_job_dashboard.sql",
    "mart_correspondence_cost_code_exposure.sql",
    "mart_subcontractor_combined_exposure.sql",
    "mart_monthly_cost_trend.sql",
    "analysis_dq_issues.sql",
    "model_analysis_reconciliation.sql",
)

REQUIRED_TABLES = (
    "dim_job",
    "dim_cost_code",
    "dim_subcontractor",
    "fact_cost_transaction",
    "mart_job_financial",
    "mart_portfolio_risk",
    "mart_subcontractor_exposure",
    "fact_correspondence_event_current",
)

OUTPUT_TABLES = (
    "ref_correspondence_scope_cost_code",
    "mart_correspondence_exposure",
    "mart_job_correspondence_exposure",
    "mart_job_risk_adjusted",
    "mart_job_dashboard",
    "mart_correspondence_cost_code_exposure",
    "mart_subcontractor_combined_exposure",
    "mart_monthly_cost_trend",
    "analysis_dq_issues",
    "model_analysis_reconciliation",
)


@dataclass(frozen=True)
class AnalysisBuildResult:
    table_name: str
    row_count: int


class AnalysisBuildError(RuntimeError):
    """Raised when the question-aligned analytical layer cannot be built."""


def _create_metadata_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_analysis_runs (
            analysis_run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status VARCHAR NOT NULL,
            error_message VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_analysis_tables (
            analysis_run_id VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            PRIMARY KEY (analysis_run_id, table_name)
        )
        """
    )


def _validate_inputs(connection: duckdb.DuckDBPyConnection, mapping_path: Path) -> None:
    if not mapping_path.is_file():
        raise AnalysisBuildError(f"scope-to-cost-code map does not exist: {mapping_path}")

    existing = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    missing = [table for table in REQUIRED_TABLES if table not in existing]
    if missing:
        raise AnalysisBuildError(
            "missing analytical inputs; run `flint model` and "
            "`flint model-correspondence` first: " + ", ".join(missing)
        )


def _render_sql(sql_path: Path, mapping_path: Path) -> str:
    sql = sql_path.read_text(encoding="utf-8")
    safe_path = str(mapping_path).replace("'", "''")
    return sql.replace("{{correspondence_scope_cost_code_map_path}}", safe_path)


def _validate_scope_map(connection: duckdb.DuckDBPyConnection) -> None:
    incomplete = connection.execute(
        """
        SELECT count(*)
        FROM ref_correspondence_scope_cost_code
        WHERE scope_key IS NULL
           OR division IS NULL
           OR estimate_cost_code IS NULL
           OR resolution_basis IS NULL
        """
    ).fetchone()[0]
    if incomplete:
        raise AnalysisBuildError(f"scope-to-cost-code map contains {incomplete} incomplete rows")

    duplicate_keys = connection.execute(
        """
        SELECT count(*)
        FROM (
            SELECT scope_key, division
            FROM ref_correspondence_scope_cost_code
            GROUP BY scope_key, division
            HAVING count(*) > 1
        )
        """
    ).fetchone()[0]
    if duplicate_keys:
        raise AnalysisBuildError(
            f"scope-to-cost-code map contains {duplicate_keys} duplicate scope/division keys"
        )

    invalid_divisions = connection.execute(
        """
        SELECT count(*)
        FROM ref_correspondence_scope_cost_code
        WHERE division NOT IN ('ALL', 'Building', 'Civil')
        """
    ).fetchone()[0]
    if invalid_divisions:
        raise AnalysisBuildError(
            f"scope-to-cost-code map contains {invalid_divisions} invalid divisions"
        )

    unknown_targets = connection.execute(
        """
        SELECT count(*)
        FROM ref_correspondence_scope_cost_code AS mapping
        LEFT JOIN dim_cost_code AS codes
            ON codes.cost_code_key = mapping.estimate_cost_code
        WHERE codes.cost_code_key IS NULL
        """
    ).fetchone()[0]
    if unknown_targets:
        raise AnalysisBuildError(
            f"scope-to-cost-code map contains {unknown_targets} unknown cost-code targets"
        )


def _validate_output(connection: duckdb.DuckDBPyConnection) -> None:
    failed_checks = connection.execute(
        "SELECT count(*) FROM model_analysis_reconciliation WHERE NOT passed"
    ).fetchone()[0]
    if failed_checks:
        raise AnalysisBuildError(f"{failed_checks} analysis reconciliation checks failed")


def build_analysis(settings: Settings) -> list[AnalysisBuildResult]:
    if not settings.database_path.is_file():
        raise AnalysisBuildError(
            f"DuckDB database does not exist; run `flint build` first: {settings.database_path}"
        )

    mapping_path = (
        settings.project_root / "data" / "reference" / "correspondence_scope_cost_code_map.csv"
    )
    sql_dir = Path(__file__).resolve().parent / "sql"
    run_id = str(uuid4())
    connection = duckdb.connect(str(settings.database_path))
    _create_metadata_tables(connection)
    connection.execute(
        """
        INSERT INTO meta_analysis_runs (analysis_run_id, started_at, status)
        VALUES (?, ?, 'running')
        """,
        [run_id, datetime.now(UTC)],
    )

    transaction_open = False
    try:
        _validate_inputs(connection, mapping_path)
        connection.execute("BEGIN TRANSACTION")
        transaction_open = True
        for filename in SQL_FILES:
            connection.execute(_render_sql(sql_dir / filename, mapping_path))
            if filename == "ref_correspondence_scope_cost_code.sql":
                _validate_scope_map(connection)

        _validate_output(connection)

        results = []
        for table_name in OUTPUT_TABLES:
            row_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            result = AnalysisBuildResult(table_name, row_count)
            results.append(result)
            connection.execute(
                "INSERT INTO meta_analysis_tables VALUES (?, ?, ?)",
                [run_id, table_name, row_count],
            )

        connection.execute(
            """
            UPDATE meta_analysis_runs
            SET status = 'completed', completed_at = ?
            WHERE analysis_run_id = ?
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
            UPDATE meta_analysis_runs
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE analysis_run_id = ?
            """,
            [datetime.now(UTC), str(exc), run_id],
        )
        if isinstance(exc, AnalysisBuildError):
            raise
        raise AnalysisBuildError(f"unexpected analysis-build failure: {exc}") from exc
    finally:
        connection.close()

    return results
