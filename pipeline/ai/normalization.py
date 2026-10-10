from __future__ import annotations

import re

from pipeline.ai.schema import CorrespondenceExtraction, ExtractionEvent

_GENERIC_SCHEDULE_IMPACT = re.compile(
    r"\bschedule\s+impact(?:\s*(?:is|of|:|-))?\s+\d+\s+(?:working\s+)?days?\b",
    re.IGNORECASE,
)
_EXPLICIT_SCHEDULE_DIRECTION = re.compile(
    r"(?:"
    r"\bdelay(?:ed|s|ing)?\b|"
    r"\bslip(?:ped|s|ping)?\b|"
    r"\bbehind\s+plan\b|"
    r"\b(?:add(?:ed|s|ing)?\s+(?:\d+\s+(?:working\s+)?days?\s+)?to\s+the\s+)?"
    r"critical\s+path\b|"
    r"\bpull(?:ed|ing)?\s+back\b|"
    r"\brecover(?:ed|ing|y)?\b|"
    r"\baccelerat(?:e|ed|es|ing|ion)\b|"
    r"\bmake[- ]?up\b|"
    r"\b(?:hold(?:ing|s)?|available)\b[^.\n]{0,40}\bfloat\b|"
    r"\bno\s+schedule\s+impact\b"
    r")",
    re.IGNORECASE,
)
_PENDING_APPROVAL = re.compile(
    r"(?:"
    r"\bpending(?:\s+[\w/-]+){0,3}\s+approval\b|"
    r"\brequest(?:ed|ing|s)?(?:\s+[\w/-]+){0,3}\s+approval\b|"
    r"\bapproval\s+(?:is\s+)?pending\b"
    r")",
    re.IGNORECASE,
)
_APPROVAL_NOT_APPLICABLE = re.compile(
    r"\b(?:approval\s+(?:is\s+)?not\s+(?:required|applicable)|no\s+approval\s+required)\b",
    re.IGNORECASE,
)


def _normalize_event(event: ExtractionEvent, source_text: str) -> ExtractionEvent:
    """Apply explicit, source-grounded rules that should not depend on model judgment."""

    evidence = event.evidence_text
    updates: dict[str, str] = {}
    if evidence not in source_text:
        # Correspondence records are short. Using the immutable source document is
        # safer than accepting a paraphrased citation or guessing at a fuzzy span.
        evidence = source_text
        updates["evidence_text"] = source_text

    if (
        event.schedule_impact_days is not None
        and _GENERIC_SCHEDULE_IMPACT.search(evidence)
        and not _EXPLICIT_SCHEDULE_DIRECTION.search(evidence)
    ):
        updates["schedule_impact_type"] = "unknown"

    has_pending_approval = _PENDING_APPROVAL.search(evidence) is not None
    if has_pending_approval and event.approval_status in {"unknown", "not_applicable"}:
        updates["approval_status"] = "pending"
    elif event.approval_status == "pending" and not has_pending_approval:
        updates["approval_status"] = "unknown"
    elif event.approval_status == "not_applicable" and not _APPROVAL_NOT_APPLICABLE.search(
        evidence
    ):
        updates["approval_status"] = "unknown"

    return event.model_copy(update=updates) if updates else event


def normalize_extraction(
    extraction: CorrespondenceExtraction,
    *,
    source_text: str,
) -> CorrespondenceExtraction:
    """Normalize deterministic semantics before grounding, persistence, and analysis."""

    events = [_normalize_event(event, source_text) for event in extraction.events]
    return extraction.model_copy(update={"events": events})
