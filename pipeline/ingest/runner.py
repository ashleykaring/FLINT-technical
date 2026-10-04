from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from pipeline.config import Settings
from pipeline.ingest.contracts import (
    ALL_SOURCE_FILENAMES,
    CORRESPONDENCE,
    CSV_CONTRACTS,
    EQUIPMENT,
    ESTIMATE_API_FILENAME,
)
from pipeline.ingest.loaders import (
    SourceContractError,
    load_correspondence,
    load_csv_source,
    load_equipment,
    load_estimates_api,
    validate_estimate_equivalence,
)


@dataclass(frozen=True)
class SourceLoadResult:
    source_name: str
    source_file: str
    table_name: str
    row_count: int


class IngestionError(RuntimeError):
    """Raised when a complete ingestion run cannot be committed."""


def _validate_source_files(raw_data_dir: Path) -> None:
    missing = [
        filename for filename in ALL_SOURCE_FILENAMES if not (raw_data_dir / filename).is_file()
    ]
    if missing:
        raise IngestionError(
            f"missing required source files in {raw_data_dir}: {', '.join(missing)}"
        )


def _create_metadata_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_ingestion_runs (
            ingestion_run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status VARCHAR NOT NULL,
            database_path VARCHAR NOT NULL,
            error_message VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_ingestion_sources (
            ingestion_run_id VARCHAR NOT NULL,
            source_name VARCHAR NOT NULL,
            source_file VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ingestion_run_id, table_name)
        )
        """
    )


def _record_source(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    result: SourceLoadResult,
) -> None:
    connection.execute(
        """
        INSERT INTO meta_ingestion_sources
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            result.source_name,
            result.source_file,
            result.table_name,
            result.row_count,
            datetime.now(UTC),
        ],
    )


def ingest_all(settings: Settings) -> list[SourceLoadResult]:
    """Atomically replace all raw tables from the supplied static extracts."""

    _validate_source_files(settings.raw_data_dir)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid4())
    started_at = datetime.now(UTC)
    connection = duckdb.connect(str(settings.database_path))
    _create_metadata_tables(connection)
    connection.execute(
        """
        INSERT INTO meta_ingestion_runs
        (ingestion_run_id, started_at, status, database_path)
        VALUES (?, ?, 'running', ?)
        """,
        [run_id, started_at, str(settings.database_path)],
    )

    results: list[SourceLoadResult] = []
    try:
        connection.execute("BEGIN TRANSACTION")

        for contract in CSV_CONTRACTS:
            source_path = settings.raw_data_dir / contract.filename
            row_count = load_csv_source(connection, source_path, contract, run_id)
            result = SourceLoadResult(
                source_name=contract.name,
                source_file=contract.filename,
                table_name=contract.table_name,
                row_count=row_count,
            )
            results.append(result)
            _record_source(connection, run_id, result)

        estimate_path = settings.raw_data_dir / ESTIMATE_API_FILENAME
        project_count, line_count = load_estimates_api(connection, estimate_path, run_id)
        for table_name, row_count in (
            ("raw_estimate_api_projects", project_count),
            ("raw_estimate_api_line_items", line_count),
        ):
            result = SourceLoadResult(
                source_name="estimates_budget_api",
                source_file=ESTIMATE_API_FILENAME,
                table_name=table_name,
                row_count=row_count,
            )
            results.append(result)
            _record_source(connection, run_id, result)

        validate_estimate_equivalence(connection)

        equipment_path = settings.raw_data_dir / EQUIPMENT.filename
        equipment_count = load_equipment(connection, equipment_path, EQUIPMENT, run_id)
        equipment_result = SourceLoadResult(
            source_name=EQUIPMENT.name,
            source_file=EQUIPMENT.filename,
            table_name=EQUIPMENT.table_name,
            row_count=equipment_count,
        )
        results.append(equipment_result)
        _record_source(connection, run_id, equipment_result)

        correspondence_path = settings.raw_data_dir / CORRESPONDENCE.filename
        correspondence_count = load_correspondence(
            connection,
            correspondence_path,
            CORRESPONDENCE,
            run_id,
        )
        correspondence_result = SourceLoadResult(
            source_name=CORRESPONDENCE.name,
            source_file=CORRESPONDENCE.filename,
            table_name=CORRESPONDENCE.table_name,
            row_count=correspondence_count,
        )
        results.append(correspondence_result)
        _record_source(connection, run_id, correspondence_result)

        connection.execute(
            """
            UPDATE meta_ingestion_runs
            SET status = 'completed', completed_at = ?
            WHERE ingestion_run_id = ?
            """,
            [datetime.now(UTC), run_id],
        )
        connection.execute("COMMIT")
    except Exception as exc:
        connection.execute("ROLLBACK")
        connection.execute(
            """
            UPDATE meta_ingestion_runs
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE ingestion_run_id = ?
            """,
            [datetime.now(UTC), str(exc), run_id],
        )
        if isinstance(exc, (IngestionError, SourceContractError)):
            raise IngestionError(str(exc)) from exc
        raise IngestionError(f"unexpected ingestion failure: {exc}") from exc
    finally:
        connection.close()

    return results
