from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import pipeline.api.app as api_app
from pipeline.api.schemas import JobAnswerFact, JobQuestionResponse
from pipeline.config import Settings


def test_job_question_endpoint_uses_selected_job_context(monkeypatch) -> None:
    detail = SimpleNamespace(summary=SimpleNamespace(job_id="B2100"))
    equipment = SimpleNamespace()
    captured: dict[str, object] = {}

    monkeypatch.setattr(api_app, "load_job_detail", lambda settings, job_id: detail)
    monkeypatch.setattr(
        api_app,
        "load_equipment_dashboard",
        lambda settings, filters: equipment,
    )

    def fake_answerer(job_detail, job_equipment, question):
        captured.update(
            detail=job_detail,
            equipment=job_equipment,
            question=question,
        )
        return JobQuestionResponse(
            answer="Forecast remaining is the primary driver.",
            supporting_facts=[
                JobAnswerFact(
                    statement="The base forecast is above the current cost budget.",
                    source_section="FINANCIAL",
                )
            ],
            caveat=None,
        )

    client = TestClient(api_app.create_app(Settings.from_root(), job_answerer=fake_answerer))
    response = client.post(
        "/api/jobs/B2100/ask",
        json={"question": "What is driving the projected overrun?"},
    )

    assert response.status_code == 200
    assert response.json()["supporting_facts"][0]["source_section"] == "FINANCIAL"
    assert captured == {
        "detail": detail,
        "equipment": equipment,
        "question": "What is driving the projected overrun?",
    }
