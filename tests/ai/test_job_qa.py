from __future__ import annotations

from types import SimpleNamespace

import pytest

from pipeline.ai.job_qa import (
    GeminiJobQuestionAnswerer,
    JobQuestionConfigurationError,
    build_job_context,
)


class StubModel:
    def __init__(self, **values: object) -> None:
        self.values = values
        for key, value in values.items():
            setattr(self, key, value)

    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "json"
        return self.values


def test_job_context_has_labeled_governed_sections() -> None:
    detail = SimpleNamespace(
        summary=StubModel(job_id="B2100", projected_final_cost=12_000_000),
        scenarios=[StubModel(scenario="Base forecast")],
        monthly_costs=[],
        cost_codes=[StubModel(cost_code="03-100")],
        schedule_summary=StubModel(activity_count=10),
        schedule_activities=[],
        exposure_buckets=[],
        correspondence_events=[StubModel(doc_id="CO-1")],
        subcontractors=[],
    )
    equipment = SimpleNamespace(
        kpis=StubModel(total_equipment_cost=125_000),
        assignments=[StubModel(equipment_type="Crane")],
    )

    context = build_job_context(detail, equipment)

    assert '"job_id": "B2100"' in context
    assert '"FINANCIAL"' in context
    assert '"EQUIPMENT"' in context
    assert '"CORRESPONDENCE"' in context
    assert '"projected_final_cost": 12000000' in context


def test_job_question_requires_server_side_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(JobQuestionConfigurationError, match="GEMINI_API_KEY is not set"):
        GeminiJobQuestionAnswerer()
