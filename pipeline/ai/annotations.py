from __future__ import annotations

import csv
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pipeline.ai.schema import (
    AMOUNT_STATUSES,
    APPROVAL_STATUSES,
    BOOKING_STATUSES,
    DOCUMENT_FIELDS,
    EVENT_FIELDS,
    EVENT_TYPES,
    FINANCIAL_IMPACT_TYPES,
    REVIEW_STATUSES,
    SCHEDULE_IMPACT_TYPES,
)
from pipeline.config import Settings

DEFAULT_PER_TYPE = 15
DEFAULT_SEED = 20261004
VALID_DOC_TYPES = frozenset(("RFI", "CO", "LOG"))


class AnnotationError(RuntimeError):
    """Raised when annotation files cannot be prepared or parsed."""


@dataclass(frozen=True)
class AnnotationPaths:
    sample: Path
    labels: Path
    entities: Path


@dataclass(frozen=True)
class ValidationIssue:
    doc_id: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    sampled_count: int
    complete_count: int
    todo_count: int
    needs_review_count: int
    event_count: int
    issues: tuple[ValidationIssue, ...]


def default_annotation_paths(settings: Settings) -> AnnotationPaths:
    annotation_dir = settings.project_root / "data" / "annotations"
    return AnnotationPaths(
        sample=annotation_dir / "correspondence_sample.jsonl",
        labels=annotation_dir / "correspondence_gold.jsonl",
        entities=annotation_dir / "entity_reference.csv",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise AnnotationError(f"JSONL file does not exist: {path}")

    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AnnotationError(f"invalid JSON on {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise AnnotationError(f"expected an object on {path}:{line_number}")
            records.append(record)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path.write_text(content, encoding="utf-8")


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def _source_records(settings: Settings) -> list[dict[str, str]]:
    source_path = settings.raw_data_dir / "project_correspondence.jsonl"
    raw_records = _read_jsonl(source_path)
    records: list[dict[str, str]] = []
    seen_doc_ids: set[str] = set()
    for raw in raw_records:
        doc_id = str(raw.get("doc_id", "")).strip()
        doc_type = str(raw.get("doc_type", "")).strip().upper()
        text = str(raw.get("text", "")).strip()
        if not doc_id or doc_type not in VALID_DOC_TYPES or not text or doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)
        records.append({"doc_id": doc_id, "doc_type": doc_type, "text": text})
    return records


def _sample_records(
    records: list[dict[str, str]],
    per_type: int,
    seed: int,
) -> list[dict[str, str]]:
    if per_type < 1:
        raise AnnotationError("per-type sample size must be positive")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        grouped[record["doc_type"]].append(record)

    randomizer = random.Random(seed)
    sampled = []
    for doc_type in sorted(VALID_DOC_TYPES):
        population = sorted(grouped[doc_type], key=lambda item: item["doc_id"])
        if len(population) < per_type:
            raise AnnotationError(
                f"requested {per_type} {doc_type} records but only {len(population)} are available"
            )
        sampled.extend(randomizer.sample(population, per_type))
    return sorted(sampled, key=lambda item: (item["doc_type"], item["doc_id"]))


def _job_aliases(records: list[dict[str, str]], job_ids: set[str]) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    for record in records:
        text = record["text"]
        for job_id in job_ids:
            formatted_id = rf"{job_id[0]}-?{job_id[1:]}"
            pattern = re.compile(
                rf"([A-Z][A-Za-z0-9]*(?:\s+(?:[A-Z][A-Za-z0-9]*|[0-9]+)){{1,4}})"
                rf"\s*(?:/|\()\s*\(?{formatted_id}\b"
            )
            for match in pattern.finditer(text):
                alias = match.group(1).strip()
                if alias.startswith("On "):
                    alias = alias[3:]
                if alias != "Proposed CO":
                    aliases[job_id].add(alias)
    return aliases


def _write_entity_reference(settings: Settings, path: Path, records: list[dict[str, str]]) -> None:
    jobs_path = settings.raw_data_dir / "jobs_reference.csv"
    ledger_path = settings.raw_data_dir / "job_cost_ledger.csv"

    jobs: dict[str, dict[str, str]] = {}
    with jobs_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            job_id = _normalize_identifier(row.get("job_id", ""))
            if job_id and job_id not in jobs:
                jobs[job_id] = row

    aliases = _job_aliases(records, set(jobs))
    subcontractor_variants: dict[str, set[str]] = defaultdict(set)
    with ledger_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            raw_value = (row.get("subcontractor") or "").strip()
            subcontractor_id = _normalize_identifier(raw_value)
            if subcontractor_id:
                subcontractor_variants[subcontractor_id].add(raw_value)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        fieldnames = (
            "entity_type",
            "canonical_id",
            "observed_aliases",
            "division",
            "contract_type",
        )
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        for job_id, row in sorted(jobs.items()):
            writer.writerow(
                {
                    "entity_type": "job",
                    "canonical_id": job_id,
                    "observed_aliases": " | ".join(sorted(aliases[job_id])),
                    "division": row.get("division", ""),
                    "contract_type": row.get("contract_type", ""),
                }
            )
        for subcontractor_id, variants in sorted(subcontractor_variants.items()):
            writer.writerow(
                {
                    "entity_type": "subcontractor",
                    "canonical_id": subcontractor_id,
                    "observed_aliases": " | ".join(sorted(variants)),
                    "division": "",
                    "contract_type": "",
                }
            )


def prepare_annotations(
    settings: Settings,
    *,
    per_type: int = DEFAULT_PER_TYPE,
    seed: int = DEFAULT_SEED,
    force: bool = False,
) -> AnnotationPaths:
    paths = default_annotation_paths(settings)
    protected_paths = (paths.sample, paths.labels, paths.entities)
    existing = [path for path in protected_paths if path.exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise AnnotationError(f"annotation outputs already exist; refusing to overwrite: {names}")

    records = _source_records(settings)
    sampled = _sample_records(records, per_type, seed)
    labels = [
        {
            **record,
            "review_status": "todo",
            "events": [],
        }
        for record in sampled
    ]
    _write_jsonl(paths.sample, sampled)
    _write_jsonl(paths.labels, labels)
    _write_entity_reference(settings, paths.entities, records)
    return paths


def _add_issue(
    issues: list[ValidationIssue],
    doc_id: str,
    path: str,
    message: str,
) -> None:
    issues.append(ValidationIssue(doc_id or "<missing>", path, message))


def _validate_enum(
    issues: list[ValidationIssue],
    doc_id: str,
    path: str,
    value: object,
    allowed: frozenset[str],
) -> None:
    if value not in allowed:
        _add_issue(issues, doc_id, path, f"must be one of: {', '.join(sorted(allowed))}")


def _load_entity_ids(path: Path) -> tuple[set[str], set[str]]:
    jobs: set[str] = set()
    subcontractors: set[str] = set()
    if not path.is_file():
        raise AnnotationError(f"entity reference does not exist: {path}")
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row["entity_type"] == "job":
                jobs.add(row["canonical_id"])
            elif row["entity_type"] == "subcontractor":
                subcontractors.add(row["canonical_id"])
    return jobs, subcontractors


def _validate_event(
    event: object,
    *,
    doc_id: str,
    event_position: int,
    text: str,
    job_ids: set[str],
    subcontractor_ids: set[str],
    issues: list[ValidationIssue],
) -> None:
    prefix = f"events[{event_position}]"
    if not isinstance(event, dict):
        _add_issue(issues, doc_id, prefix, "must be an object")
        return

    missing = EVENT_FIELDS - event.keys()
    extra = event.keys() - EVENT_FIELDS
    if missing:
        _add_issue(issues, doc_id, prefix, f"missing fields: {', '.join(sorted(missing))}")
    if extra:
        _add_issue(issues, doc_id, prefix, f"unexpected fields: {', '.join(sorted(extra))}")
    if missing:
        return

    if event["event_index"] != event_position + 1:
        _add_issue(issues, doc_id, f"{prefix}.event_index", "must be sequential starting at 1")
    _validate_enum(issues, doc_id, f"{prefix}.event_type", event["event_type"], EVENT_TYPES)
    _validate_enum(
        issues,
        doc_id,
        f"{prefix}.financial_impact_type",
        event["financial_impact_type"],
        FINANCIAL_IMPACT_TYPES,
    )
    _validate_enum(
        issues, doc_id, f"{prefix}.amount_status", event["amount_status"], AMOUNT_STATUSES
    )
    _validate_enum(
        issues, doc_id, f"{prefix}.booking_status", event["booking_status"], BOOKING_STATUSES
    )
    _validate_enum(
        issues,
        doc_id,
        f"{prefix}.schedule_impact_type",
        event["schedule_impact_type"],
        SCHEDULE_IMPACT_TYPES,
    )
    _validate_enum(
        issues,
        doc_id,
        f"{prefix}.approval_status",
        event["approval_status"],
        APPROVAL_STATUSES,
    )

    amount = event["amount"]
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float))):
        _add_issue(issues, doc_id, f"{prefix}.amount", "must be a number or null")
    elif amount is not None and amount < 0:
        _add_issue(issues, doc_id, f"{prefix}.amount", "must be nonnegative")
    days = event["schedule_impact_days"]
    if days is not None and (isinstance(days, bool) or not isinstance(days, int) or days < 0):
        _add_issue(
            issues,
            doc_id,
            f"{prefix}.schedule_impact_days",
            "must be a nonnegative integer or null",
        )

    job_id = event["job_id"]
    if job_id is not None and job_id not in job_ids:
        _add_issue(issues, doc_id, f"{prefix}.job_id", "is not in entity_reference.csv")
    subcontractor_id = event["subcontractor_id"]
    if subcontractor_id is not None and subcontractor_id not in subcontractor_ids:
        _add_issue(
            issues,
            doc_id,
            f"{prefix}.subcontractor_id",
            "is not in entity_reference.csv",
        )

    for field in ("job_reference", "subcontractor_reference", "evidence_text"):
        value = event[field]
        if field == "evidence_text" and (not isinstance(value, str) or not value.strip()):
            _add_issue(issues, doc_id, f"{prefix}.{field}", "must be nonempty")
        elif value is not None and (not isinstance(value, str) or value not in text):
            _add_issue(issues, doc_id, f"{prefix}.{field}", "must be an exact source-text span")

    referenced_date = event["referenced_date"]
    if referenced_date is not None:
        try:
            date.fromisoformat(referenced_date)
        except (TypeError, ValueError):
            _add_issue(
                issues,
                doc_id,
                f"{prefix}.referenced_date",
                "must be an ISO date (YYYY-MM-DD) or null",
            )


def validate_annotations(settings: Settings) -> ValidationResult:
    paths = default_annotation_paths(settings)
    sample = _read_jsonl(paths.sample)
    labels = _read_jsonl(paths.labels)
    job_ids, subcontractor_ids = _load_entity_ids(paths.entities)
    sample_by_id = {record.get("doc_id"): record for record in sample}
    issues: list[ValidationIssue] = []
    statuses = defaultdict(int)
    event_count = 0
    seen_doc_ids: set[str] = set()

    for record in labels:
        doc_id = record.get("doc_id", "")
        if not isinstance(doc_id, str):
            doc_id = ""
        if doc_id in seen_doc_ids:
            _add_issue(issues, doc_id, "doc_id", "is duplicated")
        seen_doc_ids.add(doc_id)

        missing = DOCUMENT_FIELDS - record.keys()
        extra = record.keys() - DOCUMENT_FIELDS
        if missing:
            _add_issue(issues, doc_id, "document", f"missing fields: {', '.join(sorted(missing))}")
        if extra:
            _add_issue(issues, doc_id, "document", f"unexpected fields: {', '.join(sorted(extra))}")
        if missing:
            continue

        source = sample_by_id.get(doc_id)
        if source is None:
            _add_issue(issues, doc_id, "doc_id", "is not in correspondence_sample.jsonl")
        else:
            for field in ("doc_type", "text"):
                if record[field] != source[field]:
                    _add_issue(issues, doc_id, field, "does not match the immutable sample")

        status = record["review_status"]
        _validate_enum(issues, doc_id, "review_status", status, REVIEW_STATUSES)
        if status in REVIEW_STATUSES:
            statuses[status] += 1

        events = record["events"]
        if not isinstance(events, list):
            _add_issue(issues, doc_id, "events", "must be a list")
            continue
        event_count += len(events)
        for position, event in enumerate(events):
            _validate_event(
                event,
                doc_id=doc_id,
                event_position=position,
                text=record["text"],
                job_ids=job_ids,
                subcontractor_ids=subcontractor_ids,
                issues=issues,
            )

    missing_labels = sample_by_id.keys() - seen_doc_ids
    for doc_id in sorted(missing_labels):
        _add_issue(issues, doc_id, "document", "sampled document is missing from the gold file")

    return ValidationResult(
        sampled_count=len(sample),
        complete_count=statuses["complete"],
        todo_count=statuses["todo"],
        needs_review_count=statuses["needs_review"],
        event_count=event_count,
        issues=tuple(issues),
    )


def render_validation_result(result: ValidationResult) -> str:
    lines = [
        "Correspondence annotation validation",
        "",
        f"Sampled documents: {result.sampled_count}",
        f"Complete:          {result.complete_count}",
        f"To do:             {result.todo_count}",
        f"Needs review:       {result.needs_review_count}",
        f"Labeled events:     {result.event_count}",
        f"Schema errors:      {len(result.issues)}",
    ]
    if result.issues:
        lines.extend(("", "Errors:"))
        lines.extend(f"- {issue.doc_id} {issue.path}: {issue.message}" for issue in result.issues)
    return "\n".join(lines)
