from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from pipeline.ai.config import PROMPT_VERSION, SCHEMA_VERSION
from pipeline.config import Settings

SQL_FILES = (
    "ref_correspondence_job_alias.sql",
    "ai_correspondence_extraction_current.sql",
    "fact_correspondence_event_current.sql",
    "correspondence_dq_issues.sql",
    "model_correspondence_reconciliation.sql",
)

REQUIRED_TABLES = (
    "ai_correspondence_extractions",
    "fact_correspondence_event",
    "stg_correspondence",
    "dim_job",
    "dim_subcontractor",
)

OUTPUT_TABLES = (
    "ref_correspondence_job_alias",
    "ai_correspondence_extraction_current",
    "fact_correspondence_event_current",
    "correspondence_dq_issues",
    "model_correspondence_reconciliation",
)


@dataclass(frozen=True)
class CorrespondenceModelResult:
    table_name: str
    row_count: int


class CorrespondenceModelError(RuntimeError):
    """Raised when the governed correspondence model cannot be built atomically."""


def _create_metadata_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_correspondence_model_runs (
            correspondence_model_run_id VARCHAR PRIMARY KEY,
            prompt_version VARCHAR NOT NULL,
            schema_version VARCHAR NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status VARCHAR NOT NULL,
            error_message VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_correspondence_model_tables (
            correspondence_model_run_id VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            PRIMARY KEY (correspondence_model_run_id, table_name)
        )
        """
    )


def _validate_inputs(connection: duckdb.DuckDBPyConnection, alias_path: Path) -> None:
    if not alias_path.is_file():
        raise CorrespondenceModelError(f"job alias map does not exist: {alias_path}")

    existing = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    missing = [table for table in REQUIRED_TABLES if table not in existing]
    if missing:
        raise CorrespondenceModelError(
            "missing correspondence inputs; complete extraction and base modeling first: "
            + ", ".join(missing)
        )


def _render_sql(sql_path: Path, alias_path: Path) -> str:
    replacements = {
        "{{correspondence_job_alias_map_path}}": str(alias_path).replace("'", "''"),
        "{{prompt_version}}": PROMPT_VERSION.replace("'", "''"),
        "{{schema_version}}": SCHEMA_VERSION.replace("'", "''"),
    }
    sql = sql_path.read_text(encoding="utf-8")
    for token, value in replacements.items():
        sql = sql.replace(token, value)
    return sql


def _validate_alias_map(connection: duckdb.DuckDBPyConnection) -> None:
    invalid_rows = connection.execute(
        """
        SELECT count(*)
        FROM ref_correspondence_job_alias
        WHERE job_alias_key IS NULL OR job_id IS NULL OR resolution_basis IS NULL
        """
    ).fetchone()[0]
    if invalid_rows:
        raise CorrespondenceModelError(f"job alias map contains {invalid_rows} incomplete rows")

    duplicate_aliases = connection.execute(
        """
        SELECT count(*) - count(DISTINCT job_alias_key)
        FROM ref_correspondence_job_alias
        """
    ).fetchone()[0]
    if duplicate_aliases:
        raise CorrespondenceModelError(
            f"job alias map contains {duplicate_aliases} duplicate normalized aliases"
        )

    unknown_targets = connection.execute(
        """
        SELECT count(*)
        FROM ref_correspondence_job_alias AS aliases
        LEFT JOIN dim_job AS jobs ON jobs.job_id = aliases.job_id
        WHERE jobs.job_id IS NULL
        """
    ).fetchone()[0]
    if unknown_targets:
        raise CorrespondenceModelError(
            f"job alias map contains {unknown_targets} IDs absent from dim_job"
        )


def _validate_output(connection: duckdb.DuckDBPyConnection) -> None:
    failed_checks = connection.execute(
        "SELECT count(*) FROM model_correspondence_reconciliation WHERE NOT passed"
    ).fetchone()[0]
    if failed_checks:
        raise CorrespondenceModelError(
            f"{failed_checks} correspondence reconciliation checks failed"
        )


def build_correspondence_model(settings: Settings) -> list[CorrespondenceModelResult]:
    if not settings.database_path.is_file():
        raise CorrespondenceModelError(
            f"DuckDB database does not exist; run `flint build` first: {settings.database_path}"
        )

    alias_path = settings.project_root / "data" / "reference" / "correspondence_job_alias_map.csv"
    sql_dir = Path(__file__).resolve().parent / "sql"
    run_id = str(uuid4())
    connection = duckdb.connect(str(settings.database_path))
    _create_metadata_tables(connection)
    connection.execute(
        """
        INSERT INTO meta_correspondence_model_runs (
            correspondence_model_run_id, prompt_version, schema_version, started_at, status
        ) VALUES (?, ?, ?, ?, 'running')
        """,
        [run_id, PROMPT_VERSION, SCHEMA_VERSION, datetime.now(UTC)],
    )

    transaction_open = False
    try:
        _validate_inputs(connection, alias_path)
        connection.execute("BEGIN TRANSACTION")
        transaction_open = True
        for filename in SQL_FILES:
            connection.execute(_render_sql(sql_dir / filename, alias_path))
            if filename == "ref_correspondence_job_alias.sql":
                _validate_alias_map(connection)

        _validate_output(connection)

        results = []
        for table_name in OUTPUT_TABLES:
            row_count = connection.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            result = CorrespondenceModelResult(table_name, row_count)
            results.append(result)
            connection.execute(
                "INSERT INTO meta_correspondence_model_tables VALUES (?, ?, ?)",
                [run_id, table_name, row_count],
            )

        connection.execute(
            """
            UPDATE meta_correspondence_model_runs
            SET status = 'completed', completed_at = ?
            WHERE correspondence_model_run_id = ?
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
            UPDATE meta_correspondence_model_runs
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE correspondence_model_run_id = ?
            """,
            [datetime.now(UTC), str(exc), run_id],
        )
        if isinstance(exc, CorrespondenceModelError):
            raise
        raise CorrespondenceModelError(f"unexpected correspondence-model failure: {exc}") from exc
    finally:
        connection.close()

    return results
