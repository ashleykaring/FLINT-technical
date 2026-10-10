from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from pydantic import ValidationError

from pipeline.ai.config import ExtractionSettings
from pipeline.ai.evaluation import evaluate_extractions
from pipeline.ai.normalization import normalize_extraction
from pipeline.ai.prompting import build_batch_prompt, build_prompt
from pipeline.ai.providers import gemini as gemini_module
from pipeline.ai.providers.base import BatchProviderResult, ExtractionUsage
from pipeline.ai.providers.gemini import GeminiConfigurationError, GeminiProvider
from pipeline.ai.runner import extract_correspondence
from pipeline.ai.schema import (
    BatchCorrespondenceExtraction,
    CorrespondenceExtraction,
    ExtractionEvent,
)
from pipeline.config import Settings


class FakeProvider:
    def __init__(
        self,
        extraction: CorrespondenceExtraction | list[CorrespondenceExtraction],
    ) -> None:
        self.extractions = extraction if isinstance(extraction, list) else [extraction]
        self.call_count = 0
        self.closed = False

    def extract_batch(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
    ) -> BatchProviderResult:
        assert "Never infer" in system_instruction
        assert "DOC-1" in user_prompt
        self.call_count += 1
        extraction = BatchCorrespondenceExtraction(documents=self.extractions)
        return BatchProviderResult(
            extraction=extraction,
            raw_text=extraction.model_dump_json(),
            response_id="response-1",
            model_version="test-model-version",
            usage=ExtractionUsage(100, 50, 0, 150),
        )

    def close(self) -> None:
        self.closed = True


def _test_project(tmp_path: Path) -> tuple[Settings, dict[str, object]]:
    raw_dir = tmp_path / "data" / "raw"
    annotation_dir = tmp_path / "data" / "annotations"
    raw_dir.mkdir(parents=True)
    annotation_dir.mkdir(parents=True)
    document = {
        "doc_id": "DOC-1",
        "doc_type": "CO",
        "text": (
            "Proposed CO for Test Project / B2100: Sub-001 premium time $100 "
            "to recover 2 days. Pending approval."
        ),
    }
    (raw_dir / "project_correspondence.jsonl").write_text(
        json.dumps(document) + "\n",
        encoding="utf-8",
    )

    with (annotation_dir / "entity_reference.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=(
                "entity_type",
                "canonical_id",
                "observed_aliases",
                "division",
                "contract_type",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "entity_type": "job",
                "canonical_id": "B2100",
                "observed_aliases": "Test Project",
            }
        )
        writer.writerow(
            {
                "entity_type": "subcontractor",
                "canonical_id": "SUB001",
                "observed_aliases": "Sub-001",
            }
        )

    event = {
        "event_index": 1,
        "job_reference": "Test Project / B2100",
        "job_id": "B2100",
        "subcontractor_reference": "Sub-001",
        "subcontractor_id": "SUB001",
        "scope": "premium time",
        "event_type": "change_order",
        "amount": 100,
        "financial_impact_type": "cost",
        "amount_status": "estimated",
        "booking_status": "unknown",
        "schedule_impact_days": 2,
        "schedule_impact_type": "recovery",
        "approval_status": "pending",
        "referenced_date": None,
        "date_context": None,
        "evidence_text": document["text"],
    }
    gold = {**document, "review_status": "complete", "events": [event]}
    (annotation_dir / "correspondence_gold.jsonl").write_text(
        json.dumps(gold) + "\n",
        encoding="utf-8",
    )
    (annotation_dir / "correspondence_sample.jsonl").write_text(
        json.dumps(document) + "\n",
        encoding="utf-8",
    )

    database_path = tmp_path / "warehouse" / "test.duckdb"
    database_path.parent.mkdir()
    duckdb.connect(str(database_path)).close()
    return Settings.from_root(tmp_path, database_path), event


def test_structured_schema_rejects_invalid_categories() -> None:
    with pytest.raises(ValidationError):
        ExtractionEvent.model_validate(
            {
                "event_index": 1,
                "job_reference": None,
                "job_id": None,
                "subcontractor_reference": None,
                "subcontractor_id": None,
                "scope": None,
                "event_type": "made_up_type",
                "amount": None,
                "financial_impact_type": "unknown",
                "amount_status": "unknown",
                "booking_status": "unknown",
                "schedule_impact_days": None,
                "schedule_impact_type": "unknown",
                "approval_status": "unknown",
                "referenced_date": None,
                "date_context": None,
                "evidence_text": "evidence",
            }
        )


def test_prompt_is_versioned_and_does_not_include_gold_answers(tmp_path: Path) -> None:
    project, _ = _test_project(tmp_path)
    settings = ExtractionSettings.from_project(project, model="test-model")
    document = json.loads(
        (project.raw_data_dir / "project_correspondence.jsonl").read_text(encoding="utf-8")
    )

    first = build_prompt(settings, document)
    second = build_prompt(settings, document)

    assert first.fingerprint == second.fingerprint
    assert '"review_status"' not in first.user_prompt
    assert '"allowed_entities"' in first.user_prompt
    assert settings.prompt_version == "correspondence-v3"
    assert settings.schema_version == "correspondence-event-v2"

    batch = build_batch_prompt(settings, [document])
    assert batch.document_fingerprints["DOC-1"] == first.fingerprint
    assert '"documents"' in batch.user_prompt


def test_normalization_removes_unstated_schedule_direction() -> None:
    event = ExtractionEvent(
        event_index=1,
        job_reference="B2100",
        job_id="B2100",
        subcontractor_reference=None,
        subcontractor_id=None,
        scope="concrete",
        event_type="change_order",
        amount=100,
        financial_impact_type="contract_value",
        amount_status="quoted",
        booking_status="unknown",
        schedule_impact_days=7,
        schedule_impact_type="delay",
        approval_status="unknown",
        referenced_date=None,
        date_context=None,
        evidence_text="Add $100 to contract value. Schedule impact 7 days.",
    )
    extraction = CorrespondenceExtraction(doc_id="DOC-1", events=[event])

    normalized = normalize_extraction(extraction, source_text=event.evidence_text)

    assert normalized.events[0].schedule_impact_type == "unknown"


def test_normalization_preserves_explicit_schedule_direction() -> None:
    event = ExtractionEvent(
        event_index=1,
        job_reference="B2100",
        job_id="B2100",
        subcontractor_reference=None,
        subcontractor_id=None,
        scope="concrete",
        event_type="change_order",
        amount=100,
        financial_impact_type="contract_value",
        amount_status="quoted",
        booking_status="unknown",
        schedule_impact_days=7,
        schedule_impact_type="delay",
        approval_status="unknown",
        referenced_date=None,
        date_context=None,
        evidence_text="Schedule impact is a delay of 7 days.",
    )
    extraction = CorrespondenceExtraction(doc_id="DOC-1", events=[event])

    normalized = normalize_extraction(extraction, source_text=event.evidence_text)

    assert normalized.events[0].schedule_impact_type == "delay"


@pytest.mark.parametrize(
    ("evidence", "model_status", "expected_status"),
    [
        ("Requesting substitution approval.", "unknown", "pending"),
        ("Pending PE approval.", "unknown", "pending"),
        ("The issue cannot proceed until resolved.", "pending", "unknown"),
        ("No approval language is present.", "not_applicable", "unknown"),
        ("No approval required.", "not_applicable", "not_applicable"),
    ],
)
def test_normalization_requires_explicit_approval_language(
    evidence: str,
    model_status: str,
    expected_status: str,
) -> None:
    event = ExtractionEvent(
        event_index=1,
        job_reference="B2100",
        job_id="B2100",
        subcontractor_reference=None,
        subcontractor_id=None,
        scope="concrete",
        event_type="schedule_risk",
        amount=None,
        financial_impact_type="unknown",
        amount_status="unknown",
        booking_status="unknown",
        schedule_impact_days=None,
        schedule_impact_type="unknown",
        approval_status=model_status,
        referenced_date=None,
        date_context=None,
        evidence_text=evidence,
    )
    extraction = CorrespondenceExtraction(doc_id="DOC-1", events=[event])

    normalized = normalize_extraction(extraction, source_text=evidence)

    assert normalized.events[0].approval_status == expected_status


def test_normalization_replaces_paraphrased_evidence_with_exact_source() -> None:
    source_text = (
        "Field note (C-2130): Safety stand-down cost 12 days on the CIP concrete. "
        "Sub-007 remobilizing Monday."
    )
    event = ExtractionEvent(
        event_index=1,
        job_reference="C-2130",
        job_id="C2130",
        subcontractor_reference="Sub-007",
        subcontractor_id="SUB007",
        scope="CIP concrete",
        event_type="schedule_risk",
        amount=None,
        financial_impact_type="unknown",
        amount_status="unknown",
        booking_status="unknown",
        schedule_impact_days=12,
        schedule_impact_type="delay",
        approval_status="unknown",
        referenced_date=None,
        date_context=None,
        evidence_text="Safety stand-down costs 12 days on the CIP concrete.",
    )
    extraction = CorrespondenceExtraction(doc_id="DOC-1", events=[event])

    normalized = normalize_extraction(extraction, source_text=source_text)

    assert normalized.events[0].evidence_text == source_text


def test_runner_caches_structured_extraction_and_evaluates_it(tmp_path: Path) -> None:
    project, event = _test_project(tmp_path)
    settings = ExtractionSettings.from_project(project, model="test-model")
    extraction = CorrespondenceExtraction.model_validate({"doc_id": "DOC-1", "events": [event]})
    provider = FakeProvider(extraction)

    first = extract_correspondence(settings, document_ids=["DOC-1"], provider=provider)
    second = extract_correspondence(settings, document_ids=["DOC-1"], provider=provider)

    assert first.processed_count == 1
    assert second.cached_count == 1
    assert provider.call_count == 1
    assert provider.closed

    with duckdb.connect(str(project.database_path), read_only=True) as connection:
        assert (
            connection.execute("SELECT count(*) FROM ai_correspondence_extractions").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT count(*) FROM fact_correspondence_event").fetchone()[0] == 1
        )
        assert (
            connection.execute(
                "SELECT total_token_count FROM ai_correspondence_extractions"
            ).fetchone()[0]
            == 150
        )

    evaluation = evaluate_extractions(project)
    assert evaluation.evaluated_documents == 1
    assert evaluation.exact_documents == 1
    assert evaluation.semantic_exact_documents == 1
    assert evaluation.grounded_evidence == 1
    assert evaluation.evidence_comparisons == 1
    assert all(score.accuracy == 1 for score in evaluation.field_scores)


def test_runner_batches_all_documents_and_reuses_per_document_cache(tmp_path: Path) -> None:
    project, event = _test_project(tmp_path)
    source_path = project.raw_data_dir / "project_correspondence.jsonl"
    second_document = {
        "doc_id": "DOC-2",
        "doc_type": "CO",
        "text": (
            "Proposed CO for Test Project / B2100: Sub-001 premium time $200 "
            "to recover 3 days. Pending approval."
        ),
    }
    with source_path.open("a", encoding="utf-8") as source:
        source.write(json.dumps(second_document) + "\n")

    second_event = {
        **event,
        "amount": 200,
        "schedule_impact_days": 3,
        "evidence_text": second_document["text"],
    }
    extractions = [
        CorrespondenceExtraction.model_validate({"doc_id": "DOC-1", "events": [event]}),
        CorrespondenceExtraction.model_validate({"doc_id": "DOC-2", "events": [second_event]}),
    ]
    provider = FakeProvider(extractions)
    settings = ExtractionSettings.from_project(project, model="test-model")

    plan = extract_correspondence(
        settings,
        all_documents=True,
        batch_size=2,
        request_interval_seconds=0,
        dry_run=True,
        provider=provider,
    )
    first = extract_correspondence(
        settings,
        all_documents=True,
        batch_size=2,
        request_interval_seconds=0,
        provider=provider,
    )
    second = extract_correspondence(
        settings,
        all_documents=True,
        batch_size=2,
        request_interval_seconds=0,
        provider=provider,
    )

    assert plan.dry_run
    assert plan.planned_count == 2
    assert plan.api_request_count == 1
    assert first.processed_count == 2
    assert first.api_request_count == 1
    assert second.cached_count == 2
    assert second.api_request_count == 0
    assert provider.call_count == 1


def test_runner_stops_after_a_batch_request_failure(tmp_path: Path) -> None:
    project, _ = _test_project(tmp_path)
    source_path = project.raw_data_dir / "project_correspondence.jsonl"
    with source_path.open("a", encoding="utf-8") as source:
        source.write(
            json.dumps({"doc_id": "DOC-2", "doc_type": "LOG", "text": "No impact."}) + "\n"
        )

    class FailingProvider:
        def __init__(self) -> None:
            self.call_count = 0

        def extract_batch(self, *, system_instruction: str, user_prompt: str) -> object:
            self.call_count += 1
            raise RuntimeError("temporary provider failure")

        def close(self) -> None:
            pass

    provider = FailingProvider()
    settings = ExtractionSettings.from_project(project, model="test-model")
    result = extract_correspondence(
        settings,
        all_documents=True,
        batch_size=1,
        request_interval_seconds=0,
        provider=provider,
    )

    assert provider.call_count == 1
    assert result.api_request_count == 1
    assert result.failed_count == 1
    assert result.skipped_count == 1


def test_gemini_provider_requires_an_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _ = _test_project(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        GeminiProvider(ExtractionSettings.from_project(project))


def test_gemini_provider_configuration_builds_without_a_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _ = _test_project(tmp_path)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")

    provider = GeminiProvider(ExtractionSettings.from_project(project))
    provider.close()


def test_gemini_provider_uses_json_schema_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, event = _test_project(tmp_path)
    document_extraction = CorrespondenceExtraction.model_validate(
        {"doc_id": "DOC-1", "events": [event]}
    )
    extraction = BatchCorrespondenceExtraction(documents=[document_extraction])

    class FakeModels:
        config: object | None = None

        def generate_content(self, *, model: str, contents: str, config: object) -> object:
            self.config = config
            return SimpleNamespace(
                parsed=extraction.model_dump(mode="json"),
                usage_metadata=None,
                text=extraction.model_dump_json(),
                response_id="response-1",
                model_version=model,
            )

    class FakeClient:
        def __init__(self) -> None:
            self.models = FakeModels()

        def close(self) -> None:
            pass

    fake_client = FakeClient()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(gemini_module.genai, "Client", lambda **_: fake_client)

    provider = GeminiProvider(ExtractionSettings.from_project(project))
    result = provider.extract_batch(system_instruction="instructions", user_prompt="documents")

    assert result.extraction == extraction
    assert fake_client.models.config.response_schema is None
    assert fake_client.models.config.response_json_schema["additionalProperties"] is False
