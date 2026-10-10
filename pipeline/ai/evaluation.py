from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import duckdb

from pipeline.ai.annotations import default_annotation_paths
from pipeline.ai.schema import CorrespondenceExtraction
from pipeline.ai.storage import create_ai_tables, extraction_json_from_latest
from pipeline.config import Settings

EVALUATED_FIELDS = (
    "job_reference",
    "job_id",
    "subcontractor_reference",
    "subcontractor_id",
    "scope",
    "event_type",
    "amount",
    "financial_impact_type",
    "amount_status",
    "booking_status",
    "schedule_impact_days",
    "schedule_impact_type",
    "approval_status",
    "referenced_date",
    "date_context",
    "evidence_text",
)

SEMANTIC_FIELDS = tuple(
    field
    for field in EVALUATED_FIELDS
    if field not in {"job_reference", "subcontractor_reference", "evidence_text"}
)


class EvaluationError(RuntimeError):
    """Raised when saved extractions cannot be evaluated."""


@dataclass(frozen=True)
class FieldScore:
    field_name: str
    matches: int
    comparisons: int

    @property
    def accuracy(self) -> float | None:
        return None if self.comparisons == 0 else self.matches / self.comparisons


@dataclass(frozen=True)
class EvaluationResult:
    gold_documents: int
    evaluated_documents: int
    exact_documents: int
    semantic_exact_documents: int
    gold_events: int
    predicted_events: int
    event_count_matches: int
    grounded_evidence: int
    evidence_comparisons: int
    missing_documents: tuple[str, ...]
    field_scores: tuple[FieldScore, ...]


def _read_completed_gold(settings: Settings) -> list[dict[str, Any]]:
    labels_path = default_annotation_paths(settings).labels
    records = []
    with labels_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("review_status") == "complete":
                records.append(record)
    return records


def evaluate_extractions(settings: Settings) -> EvaluationResult:
    if not settings.database_path.is_file():
        raise EvaluationError(f"DuckDB database does not exist: {settings.database_path}")

    gold_documents = _read_completed_gold(settings)
    field_matches: dict[str, int] = defaultdict(int)
    field_comparisons: dict[str, int] = defaultdict(int)
    evaluated_documents = 0
    exact_documents = 0
    semantic_exact_documents = 0
    gold_event_count = 0
    predicted_event_count = 0
    event_count_matches = 0
    grounded_evidence = 0
    evidence_comparisons = 0
    missing_documents = []

    connection = duckdb.connect(str(settings.database_path))
    create_ai_tables(connection)
    try:
        for gold in gold_documents:
            gold_events = gold["events"]
            gold_event_count += len(gold_events)
            saved_json = extraction_json_from_latest(connection, gold["doc_id"])
            if saved_json is None:
                missing_documents.append(gold["doc_id"])
                continue

            predicted = CorrespondenceExtraction.model_validate_json(saved_json)
            evaluated_documents += 1
            predicted_event_count += len(predicted.events)
            if len(gold_events) == len(predicted.events):
                event_count_matches += 1

            document_is_exact = len(gold_events) == len(predicted.events)
            document_is_semantically_exact = len(gold_events) == len(predicted.events)
            for gold_event, predicted_event in zip(gold_events, predicted.events, strict=False):
                predicted_values = predicted_event.model_dump(mode="json")
                evidence_comparisons += 1
                if predicted_event.evidence_text in gold["text"]:
                    grounded_evidence += 1
                for field in EVALUATED_FIELDS:
                    field_comparisons[field] += 1
                    if gold_event[field] == predicted_values[field]:
                        field_matches[field] += 1
                    else:
                        document_is_exact = False
                        if field in SEMANTIC_FIELDS:
                            document_is_semantically_exact = False
            if document_is_exact:
                exact_documents += 1
            if document_is_semantically_exact:
                semantic_exact_documents += 1
    finally:
        connection.close()

    scores = tuple(
        FieldScore(field, field_matches[field], field_comparisons[field])
        for field in EVALUATED_FIELDS
    )
    return EvaluationResult(
        gold_documents=len(gold_documents),
        evaluated_documents=evaluated_documents,
        exact_documents=exact_documents,
        semantic_exact_documents=semantic_exact_documents,
        gold_events=gold_event_count,
        predicted_events=predicted_event_count,
        event_count_matches=event_count_matches,
        grounded_evidence=grounded_evidence,
        evidence_comparisons=evidence_comparisons,
        missing_documents=tuple(missing_documents),
        field_scores=scores,
    )


def render_evaluation(result: EvaluationResult) -> str:
    lines = [
        "Correspondence extraction evaluation",
        "",
        f"Gold documents:       {result.gold_documents}",
        f"Evaluated documents:  {result.evaluated_documents}",
        f"Exact documents:      {result.exact_documents}",
        f"Semantic exact docs:  {result.semantic_exact_documents}",
        f"Event-count matches:  {result.event_count_matches}",
        f"Gold events:           {result.gold_events}",
        f"Predicted events:      {result.predicted_events}",
        (f"Grounded evidence:    {result.grounded_evidence}/{result.evidence_comparisons}"),
    ]
    if result.missing_documents:
        lines.append(f"Missing extractions:   {', '.join(result.missing_documents)}")

    lines.extend(("", f"{'Field':<30} {'Match':>7} {'Total':>7} {'Accuracy':>10}"))
    lines.append(f"{'-' * 30} {'-' * 7} {'-' * 7} {'-' * 10}")
    for score in result.field_scores:
        accuracy = "n/a" if score.accuracy is None else f"{score.accuracy:.1%}"
        lines.append(
            f"{score.field_name:<30} {score.matches:>7} {score.comparisons:>7} {accuracy:>10}"
        )
    return "\n".join(lines)
