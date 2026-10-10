from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from pipeline.ai.config import ExtractionSettings
from pipeline.ai.providers.base import ProviderResult
from pipeline.ai.schema import CorrespondenceExtraction


def create_ai_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_ai_extraction_runs (
            extraction_run_id VARCHAR PRIMARY KEY,
            provider VARCHAR NOT NULL,
            model VARCHAR NOT NULL,
            prompt_version VARCHAR NOT NULL,
            schema_version VARCHAR NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status VARCHAR NOT NULL,
            requested_documents INTEGER NOT NULL,
            processed_documents INTEGER NOT NULL DEFAULT 0,
            cached_documents INTEGER NOT NULL DEFAULT 0,
            failed_documents INTEGER NOT NULL DEFAULT 0,
            error_message VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_correspondence_extractions (
            cache_key VARCHAR PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            doc_type VARCHAR NOT NULL,
            source_hash VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            model VARCHAR NOT NULL,
            prompt_version VARCHAR NOT NULL,
            schema_version VARCHAR NOT NULL,
            prompt_fingerprint VARCHAR NOT NULL,
            extracted_at TIMESTAMPTZ NOT NULL,
            response_id VARCHAR,
            model_version VARCHAR,
            prompt_token_count INTEGER,
            output_token_count INTEGER,
            thoughts_token_count INTEGER,
            total_token_count INTEGER,
            raw_response_path VARCHAR NOT NULL,
            extraction_json JSON NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_correspondence_event (
            correspondence_event_key VARCHAR PRIMARY KEY,
            cache_key VARCHAR NOT NULL,
            doc_id VARCHAR NOT NULL,
            event_index INTEGER NOT NULL,
            job_reference VARCHAR,
            job_id VARCHAR,
            subcontractor_reference VARCHAR,
            subcontractor_id VARCHAR,
            scope VARCHAR,
            event_type VARCHAR NOT NULL,
            amount DECIMAL(18, 2),
            financial_impact_type VARCHAR NOT NULL,
            amount_status VARCHAR NOT NULL,
            booking_status VARCHAR NOT NULL,
            schedule_impact_days INTEGER,
            schedule_impact_type VARCHAR NOT NULL,
            approval_status VARCHAR NOT NULL,
            referenced_date DATE,
            date_context VARCHAR,
            evidence_text VARCHAR NOT NULL,
            FOREIGN KEY (cache_key) REFERENCES ai_correspondence_extractions(cache_key)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_extraction_failures (
            failure_id VARCHAR PRIMARY KEY,
            extraction_run_id VARCHAR NOT NULL,
            doc_id VARCHAR NOT NULL,
            cache_key VARCHAR,
            attempted_at TIMESTAMPTZ NOT NULL,
            error_type VARCHAR NOT NULL,
            error_message VARCHAR NOT NULL
        )
        """
    )


def load_cached_extraction(
    connection: duckdb.DuckDBPyConnection,
    cache_key: str,
) -> CorrespondenceExtraction | None:
    row = connection.execute(
        """
        SELECT cast(extraction_json AS VARCHAR)
        FROM ai_correspondence_extractions
        WHERE cache_key = ?
        """,
        [cache_key],
    ).fetchone()
    if row is None:
        return None
    return CorrespondenceExtraction.model_validate_json(row[0])


def save_extraction(
    connection: duckdb.DuckDBPyConnection,
    *,
    document: dict[str, str],
    source_hash: str,
    prompt_fingerprint: str,
    settings: ExtractionSettings,
    result: ProviderResult,
) -> Path:
    cache_key = prompt_fingerprint
    settings.raw_response_dir.mkdir(parents=True, exist_ok=True)
    raw_path = settings.raw_response_dir / f"{cache_key}.json"
    raw_path.write_text(result.raw_text, encoding="utf-8")
    relative_raw_path = raw_path.relative_to(settings.project.project_root)
    extracted_at = datetime.now(UTC)
    extraction_json = result.extraction.model_dump_json()

    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(
            "DELETE FROM fact_correspondence_event WHERE cache_key = ?",
            [cache_key],
        )
        connection.execute(
            "DELETE FROM ai_correspondence_extractions WHERE cache_key = ?",
            [cache_key],
        )
        connection.execute(
            """
            INSERT INTO ai_correspondence_extractions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                cache_key,
                document["doc_id"],
                document["doc_type"],
                source_hash,
                settings.provider,
                settings.model,
                settings.prompt_version,
                settings.schema_version,
                prompt_fingerprint,
                extracted_at,
                result.response_id,
                result.model_version,
                result.usage.prompt_tokens,
                result.usage.output_tokens,
                result.usage.thoughts_tokens,
                result.usage.total_tokens,
                str(relative_raw_path),
                extraction_json,
            ],
        )
        for event in result.extraction.events:
            event_data = event.model_dump(mode="json")
            connection.execute(
                """
                INSERT INTO fact_correspondence_event VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    f"{cache_key}:{event.event_index}",
                    cache_key,
                    document["doc_id"],
                    event.event_index,
                    event.job_reference,
                    event.job_id,
                    event.subcontractor_reference,
                    event.subcontractor_id,
                    event.scope,
                    event.event_type,
                    event.amount,
                    event.financial_impact_type,
                    event.amount_status,
                    event.booking_status,
                    event.schedule_impact_days,
                    event.schedule_impact_type,
                    event.approval_status,
                    event_data["referenced_date"],
                    event.date_context,
                    event.evidence_text,
                ],
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return raw_path


def extraction_json_from_latest(
    connection: duckdb.DuckDBPyConnection,
    doc_id: str,
) -> str | None:
    row = connection.execute(
        """
        SELECT cast(extraction_json AS VARCHAR)
        FROM ai_correspondence_extractions
        WHERE doc_id = ?
        ORDER BY extracted_at DESC
        LIMIT 1
        """,
        [doc_id],
    ).fetchone()
    return None if row is None else row[0]


def dump_extraction(extraction: CorrespondenceExtraction) -> str:
    return json.dumps(extraction.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
