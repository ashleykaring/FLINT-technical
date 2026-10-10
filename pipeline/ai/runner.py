from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb

from pipeline.ai.annotations import default_annotation_paths
from pipeline.ai.config import ExtractionSettings
from pipeline.ai.normalization import normalize_extraction
from pipeline.ai.prompting import build_batch_prompt
from pipeline.ai.providers.base import ExtractionProvider, ExtractionUsage, ProviderResult
from pipeline.ai.providers.gemini import GeminiProvider
from pipeline.ai.schema import CorrespondenceExtraction
from pipeline.ai.storage import create_ai_tables, load_cached_extraction, save_extraction


class ExtractionError(RuntimeError):
    """Raised when correspondence extraction cannot be started or validated."""


@dataclass(frozen=True)
class DocumentExtractionResult:
    doc_id: str
    status: str
    event_count: int
    cache_key: str
    error_message: str | None = None


@dataclass(frozen=True)
class ExtractionRunResult:
    run_id: str
    provider: str
    model: str
    documents: tuple[DocumentExtractionResult, ...]
    api_request_count: int
    batch_size: int
    dry_run: bool = False

    @property
    def processed_count(self) -> int:
        return sum(document.status == "processed" for document in self.documents)

    @property
    def cached_count(self) -> int:
        return sum(document.status == "cached" for document in self.documents)

    @property
    def failed_count(self) -> int:
        return sum(document.status == "failed" for document in self.documents)

    @property
    def planned_count(self) -> int:
        return sum(document.status == "planned" for document in self.documents)

    @property
    def skipped_count(self) -> int:
        return sum(document.status == "skipped" for document in self.documents)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExtractionError(f"invalid JSON on {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ExtractionError(f"expected an object on {path}:{line_number}")
            records.append(record)
    return records


def _load_source_documents(settings: ExtractionSettings) -> dict[str, dict[str, str]]:
    source_path = settings.project.raw_data_dir / "project_correspondence.jsonl"
    documents: dict[str, dict[str, str]] = {}
    for record in _read_jsonl(source_path):
        doc_id = str(record.get("doc_id", "")).strip()
        doc_type = str(record.get("doc_type", "")).strip().upper()
        text = str(record.get("text", "")).strip()
        if doc_id and doc_id not in documents:
            documents[doc_id] = {"doc_id": doc_id, "doc_type": doc_type, "text": text}
    return documents


def _completed_gold_ids(settings: ExtractionSettings) -> list[str]:
    labels_path = default_annotation_paths(settings.project).labels
    return [
        str(record["doc_id"])
        for record in _read_jsonl(labels_path)
        if record.get("review_status") == "complete"
    ]


def _select_documents(
    settings: ExtractionSettings,
    *,
    document_ids: list[str] | None,
    gold_complete: bool,
    all_documents: bool,
    limit: int | None,
) -> list[dict[str, str]]:
    selection_count = sum((bool(document_ids), gold_complete, all_documents))
    if selection_count != 1:
        raise ExtractionError("select exactly one of --doc-id, --gold-complete, or --all")
    if limit is not None and limit < 1:
        raise ExtractionError("limit must be positive")

    source_documents = _load_source_documents(settings)
    if all_documents:
        selected_ids = list(source_documents)
    elif gold_complete:
        selected_ids = _completed_gold_ids(settings)
    else:
        selected_ids = document_ids or []
    if limit is not None:
        selected_ids = selected_ids[:limit]
    missing = [doc_id for doc_id in selected_ids if doc_id not in source_documents]
    if missing:
        raise ExtractionError("unknown correspondence document IDs: " + ", ".join(missing))
    return [source_documents[doc_id] for doc_id in selected_ids]


def _load_entity_ids(settings: ExtractionSettings) -> tuple[set[str], set[str]]:
    jobs: set[str] = set()
    subcontractors: set[str] = set()
    path = default_annotation_paths(settings.project).entities
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row["entity_type"] == "job":
                jobs.add(row["canonical_id"])
            elif row["entity_type"] == "subcontractor":
                subcontractors.add(row["canonical_id"])
    return jobs, subcontractors


def _validate_grounding(
    document: dict[str, str],
    extraction: CorrespondenceExtraction,
    job_ids: set[str],
    subcontractor_ids: set[str],
) -> None:
    if extraction.doc_id != document["doc_id"]:
        raise ExtractionError(
            f"response doc_id {extraction.doc_id!r} does not match {document['doc_id']!r}"
        )
    text = document["text"]
    for event in extraction.events:
        for field in ("job_reference", "subcontractor_reference", "scope", "evidence_text"):
            value = getattr(event, field)
            if value is not None and value not in text:
                raise ExtractionError(
                    f"{document['doc_id']} event {event.event_index} "
                    f"{field} is not an exact source span"
                )
        if event.job_id is not None and event.job_id not in job_ids:
            raise ExtractionError(
                f"{document['doc_id']} event {event.event_index} has unknown job {event.job_id}"
            )
        if event.subcontractor_id is not None and event.subcontractor_id not in subcontractor_ids:
            raise ExtractionError(
                f"{document['doc_id']} event {event.event_index} has unknown subcontractor "
                f"{event.subcontractor_id}"
            )


def _source_hash(document: dict[str, str]) -> str:
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_failure(
    connection: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    document: dict[str, str],
    cache_key: str,
    error: Exception,
) -> DocumentExtractionResult:
    connection.execute(
        """
        INSERT INTO ai_extraction_failures VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid4()),
            run_id,
            document["doc_id"],
            cache_key,
            datetime.now(UTC),
            type(error).__name__,
            str(error),
        ],
    )
    return DocumentExtractionResult(
        document["doc_id"],
        "failed",
        0,
        cache_key,
        str(error),
    )


def extract_correspondence(
    settings: ExtractionSettings,
    *,
    document_ids: list[str] | None = None,
    gold_complete: bool = False,
    all_documents: bool = False,
    limit: int | None = None,
    batch_size: int = 100,
    request_interval_seconds: float = 15.0,
    request_budget: int = 20,
    dry_run: bool = False,
    force: bool = False,
    provider: ExtractionProvider | None = None,
) -> ExtractionRunResult:
    if not settings.project.database_path.is_file():
        raise ExtractionError(
            f"DuckDB database does not exist; run `flint build` first: "
            f"{settings.project.database_path}"
        )

    documents = _select_documents(
        settings,
        document_ids=document_ids,
        gold_complete=gold_complete,
        all_documents=all_documents,
        limit=limit,
    )
    if not documents:
        raise ExtractionError("no correspondence documents were selected")
    if not 1 <= batch_size <= 100:
        raise ExtractionError("batch size must be between 1 and 100")
    if request_interval_seconds < 0:
        raise ExtractionError("request interval cannot be negative")
    if request_budget < 1:
        raise ExtractionError("request budget must be positive")

    job_ids, subcontractor_ids = _load_entity_ids(settings)
    run_id = str(uuid4())
    connection = duckdb.connect(str(settings.project.database_path))
    create_ai_tables(connection)

    fingerprint_bundle = build_batch_prompt(settings, documents)
    pending: list[tuple[dict[str, str], str]] = []
    results: list[DocumentExtractionResult] = []
    for document in documents:
        cache_key = fingerprint_bundle.document_fingerprints[document["doc_id"]]
        cached = None if force else load_cached_extraction(connection, cache_key)
        if cached is None:
            pending.append((document, cache_key))
        else:
            results.append(
                DocumentExtractionResult(
                    document["doc_id"],
                    "cached",
                    len(cached.events),
                    cache_key,
                )
            )

    batches = [pending[index : index + batch_size] for index in range(0, len(pending), batch_size)]
    if len(batches) > request_budget:
        connection.close()
        raise ExtractionError(
            f"{len(pending)} uncached documents at batch size {batch_size} require "
            f"{len(batches)} API requests, exceeding the request budget of {request_budget}"
        )

    if dry_run:
        results.extend(
            DocumentExtractionResult(document["doc_id"], "planned", 0, cache_key)
            for document, cache_key in pending
        )
        result_order = {document["doc_id"]: index for index, document in enumerate(documents)}
        results.sort(key=lambda result: result_order[result.doc_id])
        connection.close()
        return ExtractionRunResult(
            "dry-run",
            settings.provider,
            settings.model,
            tuple(results),
            len(batches),
            batch_size,
            True,
        )

    connection.execute(
        """
        INSERT INTO meta_ai_extraction_runs (
            extraction_run_id, provider, model, prompt_version, schema_version,
            started_at, status, requested_documents
        ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
        """,
        [
            run_id,
            settings.provider,
            settings.model,
            settings.prompt_version,
            settings.schema_version,
            datetime.now(UTC),
            len(documents),
        ],
    )

    active_provider = provider
    api_request_count = 0
    last_request_started: float | None = None
    stop_error: Exception | None = None
    try:
        for batch in batches:
            if stop_error is not None:
                results.extend(
                    DocumentExtractionResult(
                        document["doc_id"],
                        "skipped",
                        0,
                        cache_key,
                        "not attempted after an earlier batch request failed",
                    )
                    for document, cache_key in batch
                )
                continue

            batch_documents = [document for document, _ in batch]
            batch_prompt = build_batch_prompt(settings, batch_documents)
            try:
                if active_provider is None:
                    active_provider = GeminiProvider(settings)

                if last_request_started is not None and request_interval_seconds:
                    elapsed = time.monotonic() - last_request_started
                    remaining = request_interval_seconds - elapsed
                    if remaining > 0:
                        time.sleep(remaining)
                last_request_started = time.monotonic()
                api_request_count += 1

                provider_result = active_provider.extract_batch(
                    system_instruction=batch_prompt.system_instruction,
                    user_prompt=batch_prompt.user_prompt,
                )

                expected_ids = [document["doc_id"] for document in batch_documents]
                actual_ids = [
                    extraction.doc_id for extraction in provider_result.extraction.documents
                ]
                if actual_ids != expected_ids:
                    raise ExtractionError(
                        "batch response document IDs/order do not match input: "
                        f"expected {expected_ids}, received {actual_ids}"
                    )

                usage_recorded = False
                for (document, cache_key), extraction in zip(
                    batch,
                    provider_result.extraction.documents,
                    strict=True,
                ):
                    try:
                        extraction = normalize_extraction(
                            extraction,
                            source_text=document["text"],
                        )
                        _validate_grounding(document, extraction, job_ids, subcontractor_ids)
                        usage = provider_result.usage if not usage_recorded else ExtractionUsage()
                        document_result = ProviderResult(
                            extraction=extraction,
                            raw_text=extraction.model_dump_json(indent=2),
                            response_id=provider_result.response_id,
                            model_version=provider_result.model_version,
                            usage=usage,
                        )
                        save_extraction(
                            connection,
                            document=document,
                            source_hash=_source_hash(document),
                            prompt_fingerprint=cache_key,
                            settings=settings,
                            result=document_result,
                        )
                        usage_recorded = True
                        results.append(
                            DocumentExtractionResult(
                                document["doc_id"],
                                "processed",
                                len(extraction.events),
                                cache_key,
                            )
                        )
                    except Exception as exc:
                        results.append(
                            _record_failure(
                                connection,
                                run_id=run_id,
                                document=document,
                                cache_key=cache_key,
                                error=exc,
                            )
                        )
            except Exception as exc:
                for document, cache_key in batch:
                    results.append(
                        _record_failure(
                            connection,
                            run_id=run_id,
                            document=document,
                            cache_key=cache_key,
                            error=exc,
                        )
                    )
                stop_error = exc

        processed_count = sum(result.status == "processed" for result in results)
        cached_count = sum(result.status == "cached" for result in results)
        failed_count = sum(result.status == "failed" for result in results)
        status = "completed" if failed_count == 0 else "completed_with_errors"
        connection.execute(
            """
            UPDATE meta_ai_extraction_runs
            SET completed_at = ?, status = ?, processed_documents = ?,
                cached_documents = ?, failed_documents = ?
            WHERE extraction_run_id = ?
            """,
            [
                datetime.now(UTC),
                status,
                processed_count,
                cached_count,
                failed_count,
                run_id,
            ],
        )
    except Exception as exc:
        connection.execute(
            """
            UPDATE meta_ai_extraction_runs
            SET completed_at = ?, status = 'failed', error_message = ?
            WHERE extraction_run_id = ?
            """,
            [datetime.now(UTC), str(exc), run_id],
        )
        raise
    finally:
        if active_provider is not None:
            active_provider.close()
        connection.close()

    result_order = {document["doc_id"]: index for index, document in enumerate(documents)}
    results.sort(key=lambda result: result_order[result.doc_id])
    return ExtractionRunResult(
        run_id,
        settings.provider,
        settings.model,
        tuple(results),
        api_request_count,
        batch_size,
    )


def render_extraction_result(result: ExtractionRunResult) -> str:
    lines = [
        (
            "Correspondence extraction plan (no API calls made)"
            if result.dry_run
            else f"Correspondence extraction run: {result.run_id}"
        ),
        f"Provider/model: {result.provider} / {result.model}",
        (
            f"Planned API requests: {result.api_request_count}"
            if result.dry_run
            else f"API requests:   {result.api_request_count}"
        ),
        f"Batch size:     {result.batch_size}",
        "",
        f"{'Document':<16} {'Status':<10} {'Events':>6}",
        f"{'-' * 16} {'-' * 10} {'-' * 6}",
    ]
    visible_documents = list(result.documents)
    omitted_count = 0
    if len(visible_documents) > 50:
        failures = [document for document in visible_documents if document.status == "failed"]
        visible_documents = failures[:20]
        omitted_count = len(result.documents) - len(visible_documents)
    for document in visible_documents:
        lines.append(f"{document.doc_id:<16} {document.status:<10} {document.event_count:>6}")
        if document.error_message:
            lines.append(f"  Error: {document.error_message}")
    if omitted_count:
        lines.append(f"... {omitted_count} document rows omitted; see summary below")
    lines.extend(
        (
            "",
            f"Processed: {result.processed_count}",
            f"Cached:    {result.cached_count}",
            f"Planned:   {result.planned_count}",
            f"Skipped:   {result.skipped_count}",
            f"Failed:    {result.failed_count}",
        )
    )
    return "\n".join(lines)
