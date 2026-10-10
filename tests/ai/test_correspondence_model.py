from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from pipeline.ai.modeling import build_correspondence_model
from pipeline.ai.storage import create_ai_tables
from pipeline.config import Settings


def _event(
    *,
    job_reference: str,
    job_id: str | None,
    subcontractor_reference: str,
    scope: str,
    event_type: str,
    amount: int | None,
    schedule_days: int | None,
    evidence: str,
) -> dict[str, object]:
    return {
        "event_index": 1,
        "job_reference": job_reference,
        "job_id": job_id,
        "subcontractor_reference": subcontractor_reference,
        "subcontractor_id": "SUB012",
        "scope": scope,
        "event_type": event_type,
        "amount": amount,
        "financial_impact_type": "unknown" if amount is None else "cost",
        "amount_status": "unknown" if amount is None else "estimated",
        "booking_status": "unknown",
        "schedule_impact_days": schedule_days,
        "schedule_impact_type": "delay" if schedule_days is not None else "unknown",
        "approval_status": "unknown",
        "referenced_date": None,
        "date_context": None,
        "evidence_text": evidence,
    }


def _insert_extraction(
    connection: duckdb.DuckDBPyConnection,
    *,
    cache_key: str,
    doc_id: str,
    doc_type: str,
    prompt_version: str,
    schema_version: str,
    extracted_at: datetime,
    event: dict[str, object],
) -> None:
    extraction_json = json.dumps({"doc_id": doc_id, "events": [event]})
    connection.execute(
        """
        INSERT INTO ai_correspondence_extractions VALUES (
            ?, ?, ?, 'source-hash', 'gemini', 'test-model', ?, ?, ?, ?,
            NULL, 'test-model', 0, 0, 0, 0, 'raw.json', ?
        )
        """,
        [
            cache_key,
            doc_id,
            doc_type,
            prompt_version,
            schema_version,
            cache_key,
            extracted_at,
            extraction_json,
        ],
    )
    connection.execute(
        """
        INSERT INTO fact_correspondence_event VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            f"{cache_key}:1",
            cache_key,
            doc_id,
            event["event_index"],
            event["job_reference"],
            event["job_id"],
            event["subcontractor_reference"],
            event["subcontractor_id"],
            event["scope"],
            event["event_type"],
            event["amount"],
            event["financial_impact_type"],
            event["amount_status"],
            event["booking_status"],
            event["schedule_impact_days"],
            event["schedule_impact_type"],
            event["approval_status"],
            event["referenced_date"],
            event["date_context"],
            event["evidence_text"],
        ],
    )


def _correspondence_project(tmp_path: Path) -> Settings:
    reference_dir = tmp_path / "data" / "reference"
    reference_dir.mkdir(parents=True)
    (reference_dir / "correspondence_job_alias_map.csv").write_text(
        "job_alias,job_id,resolution_basis\n"
        "the Airport job,C2134,Reviewed shorthand for Airport Taxiway Extension\n",
        encoding="utf-8",
    )

    database_path = tmp_path / "warehouse" / "test.duckdb"
    database_path.parent.mkdir()
    settings = Settings.from_root(tmp_path, database_path)

    first_text = (
        "Field note (the Airport job): Safety stand-down cost 6 days on excavation. "
        "SUB-012 remobilizing Monday."
    )
    second_text = "RFI on B2100: SUB-012 estimates $100 added scope for underground utilities."
    first_event = _event(
        job_reference="the Airport job",
        job_id=None,
        subcontractor_reference="SUB-012",
        scope="excavation",
        event_type="other",
        amount=None,
        schedule_days=6,
        evidence=first_text,
    )
    second_event = _event(
        job_reference="B2100",
        job_id="B2100",
        subcontractor_reference="SUB-012",
        scope="underground utilities",
        event_type="potential_cost",
        amount=100,
        schedule_days=None,
        evidence=second_text,
    )

    with duckdb.connect(str(database_path)) as connection:
        create_ai_tables(connection)
        connection.execute("CREATE TABLE dim_job (job_key VARCHAR, job_id VARCHAR)")
        connection.execute(
            "INSERT INTO dim_job VALUES ('C2134', 'C2134'), ('B2100', 'B2100'), "
            "('UNKNOWN_JOB', NULL)"
        )
        connection.execute(
            "CREATE TABLE dim_subcontractor (subcontractor_key VARCHAR, subcontractor_id VARCHAR)"
        )
        connection.execute(
            "INSERT INTO dim_subcontractor VALUES "
            "('SUB012', 'SUB012'), ('UNKNOWN_SUBCONTRACTOR', NULL)"
        )
        connection.execute(
            """
            CREATE TABLE stg_correspondence (
                doc_id VARCHAR,
                text VARCHAR,
                is_valid BOOLEAN,
                _source_file VARCHAR,
                _source_row BIGINT
            )
            """
        )
        connection.execute(
            "INSERT INTO stg_correspondence VALUES "
            "('DOC-1', ?, true, 'project_correspondence.jsonl', 1), "
            "('DOC-2', ?, true, 'project_correspondence.jsonl', 2)",
            [first_text, second_text],
        )

        now = datetime.now(UTC)
        _insert_extraction(
            connection,
            cache_key="old-doc-1",
            doc_id="DOC-1",
            doc_type="LOG",
            prompt_version="correspondence-v2",
            schema_version="correspondence-event-v1",
            extracted_at=now - timedelta(days=1),
            event={**first_event, "event_type": "schedule_risk"},
        )
        _insert_extraction(
            connection,
            cache_key="current-doc-1",
            doc_id="DOC-1",
            doc_type="LOG",
            prompt_version="correspondence-v3",
            schema_version="correspondence-event-v2",
            extracted_at=now,
            event=first_event,
        )
        _insert_extraction(
            connection,
            cache_key="current-doc-2",
            doc_id="DOC-2",
            doc_type="RFI",
            prompt_version="correspondence-v3",
            schema_version="correspondence-event-v2",
            extracted_at=now,
            event=second_event,
        )

    return settings


def test_correspondence_model_is_current_clean_and_idempotent(tmp_path: Path) -> None:
    settings = _correspondence_project(tmp_path)

    first = build_correspondence_model(settings)
    second = build_correspondence_model(settings)

    expected_counts = {
        "ref_correspondence_job_alias": 1,
        "ai_correspondence_extraction_current": 2,
        "fact_correspondence_event_current": 2,
        "correspondence_dq_issues": 0,
        "model_correspondence_reconciliation": 8,
    }
    assert {result.table_name: result.row_count for result in first} == expected_counts
    assert {result.table_name: result.row_count for result in second} == expected_counts

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        airport = connection.execute(
            """
            SELECT job_id, job_resolution_method, extracted_event_type, event_type,
                   is_event_type_normalized
            FROM fact_correspondence_event_current
            WHERE doc_id = 'DOC-1'
            """
        ).fetchone()
        assert airport == ("C2134", "alias_map", "other", "schedule_risk", True)

        current_cache_keys = connection.execute(
            "SELECT cache_key FROM ai_correspondence_extraction_current ORDER BY doc_id"
        ).fetchall()
        assert current_cache_keys == [("current-doc-1",), ("current-doc-2",)]

        failed_checks = connection.execute(
            "SELECT count(*) FROM model_correspondence_reconciliation WHERE NOT passed"
        ).fetchone()[0]
        assert failed_checks == 0

        run_statuses = connection.execute(
            "SELECT status, count(*) FROM meta_correspondence_model_runs GROUP BY status"
        ).fetchall()
        assert run_statuses == [("completed", 2)]
