from __future__ import annotations

from typing import Literal, TypedDict, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReviewStatus = Literal["todo", "complete", "needs_review"]
EventType = Literal[
    "change_order",
    "potential_cost",
    "budget_variance",
    "schedule_risk",
    "backcharge",
    "other",
]
FinancialImpactType = Literal[
    "cost",
    "contract_value",
    "budget_variance",
    "backcharge",
    "none",
    "unknown",
]
AmountStatus = Literal[
    "quoted",
    "estimated",
    "authorized",
    "approved",
    "disputed",
    "no_impact",
    "unknown",
]
BookingStatus = Literal["booked", "not_booked", "unknown"]
ScheduleImpactType = Literal[
    "delay",
    "recovery",
    "available_float",
    "none",
    "unknown",
]
ApprovalStatus = Literal[
    "proposed",
    "pending",
    "authorized",
    "approved",
    "rejected",
    "not_applicable",
    "unknown",
]


class ExtractionEvent(BaseModel):
    """Structured model output for one distinct correspondence event."""

    model_config = ConfigDict(extra="forbid")

    event_index: int = Field(ge=1, description="One-based event order within the document.")
    job_reference: str | None = Field(description="Exact job wording copied from the source.")
    job_id: str | None = Field(description="Canonical allowed job ID, or null.")
    subcontractor_reference: str | None = Field(
        description="Exact subcontractor wording copied from the source."
    )
    subcontractor_id: str | None = Field(description="Canonical allowed subcontractor ID, or null.")
    scope: str | None = Field(description="Work scope copied from the source, or null.")
    event_type: EventType
    amount: float | None = Field(
        ge=0,
        description="Nonnegative dollar magnitude; zero only for explicit no-impact language.",
    )
    financial_impact_type: FinancialImpactType
    amount_status: AmountStatus
    booking_status: BookingStatus
    schedule_impact_days: int | None = Field(
        ge=0,
        description="Nonnegative schedule-day magnitude, or null.",
    )
    schedule_impact_type: ScheduleImpactType
    approval_status: ApprovalStatus
    referenced_date: str | None = Field(description="Explicit ISO date YYYY-MM-DD, or null.")
    date_context: str | None = Field(description="Meaning of the referenced date, or null.")
    evidence_text: str = Field(
        min_length=1,
        description="Exact source span supporting this complete event.",
    )

    @field_validator("referenced_date")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from datetime import date

        date.fromisoformat(value)
        return value


class CorrespondenceExtraction(BaseModel):
    """Structured extraction response for one source document."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(description="Document ID copied exactly from the input.")
    events: list[ExtractionEvent]

    @model_validator(mode="after")
    def validate_event_order(self) -> CorrespondenceExtraction:
        indexes = [event.event_index for event in self.events]
        expected = list(range(1, len(self.events) + 1))
        if indexes != expected:
            raise ValueError("event indexes must be sequential starting at 1")
        return self


class BatchCorrespondenceExtraction(BaseModel):
    """Structured extraction response for one or more source documents."""

    model_config = ConfigDict(extra="forbid")

    documents: list[CorrespondenceExtraction] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_documents(self) -> BatchCorrespondenceExtraction:
        doc_ids = [document.doc_id for document in self.documents]
        if len(doc_ids) != len(set(doc_ids)):
            raise ValueError("batch response document IDs must be unique")
        return self


class CorrespondenceEvent(TypedDict):
    """Human-reviewed contract for one distinct correspondence event."""

    event_index: int
    job_reference: str | None
    job_id: str | None
    subcontractor_reference: str | None
    subcontractor_id: str | None
    scope: str | None
    event_type: EventType
    amount: int | float | None
    financial_impact_type: FinancialImpactType
    amount_status: AmountStatus
    booking_status: BookingStatus
    schedule_impact_days: int | None
    schedule_impact_type: ScheduleImpactType
    approval_status: ApprovalStatus
    referenced_date: str | None
    date_context: str | None
    evidence_text: str


class LabeledCorrespondence(TypedDict):
    """A source document plus zero or more manually labeled events."""

    doc_id: str
    doc_type: str
    text: str
    review_status: ReviewStatus
    events: list[CorrespondenceEvent]


REVIEW_STATUSES = frozenset(("todo", "complete", "needs_review"))
EVENT_TYPES = frozenset(get_args(EventType))
FINANCIAL_IMPACT_TYPES = frozenset(get_args(FinancialImpactType))
AMOUNT_STATUSES = frozenset(get_args(AmountStatus))
BOOKING_STATUSES = frozenset(get_args(BookingStatus))
SCHEDULE_IMPACT_TYPES = frozenset(get_args(ScheduleImpactType))
APPROVAL_STATUSES = frozenset(get_args(ApprovalStatus))

DOCUMENT_FIELDS = frozenset(("doc_id", "doc_type", "text", "review_status", "events"))
EVENT_FIELDS = frozenset(ExtractionEvent.model_fields)
