from __future__ import annotations

import json
import os
from pathlib import Path

from google import genai
from google.genai import types

from pipeline.api.schemas import EquipmentDashboard, JobDetail, JobQuestionResponse

DEFAULT_JOB_QA_MODEL = "gemini-3.5-flash-lite"
JOB_QA_PROMPT = Path(__file__).parent / "prompts" / "job-question-v1.txt"


class JobQuestionError(RuntimeError):
    """Raised when a grounded job question cannot be answered by the provider."""


class JobQuestionConfigurationError(JobQuestionError):
    """Raised when the job-question provider is not configured."""


def build_job_context(detail: JobDetail, equipment: EquipmentDashboard) -> str:
    """Serialize the governed job packet into clearly labeled source sections."""
    context = {
        "job_id": detail.summary.job_id,
        "FINANCIAL": {
            "summary": detail.summary.model_dump(mode="json"),
            "scenarios": [item.model_dump(mode="json") for item in detail.scenarios],
            "monthly_costs": [item.model_dump(mode="json") for item in detail.monthly_costs],
        },
        "COST_CODES": [item.model_dump(mode="json") for item in detail.cost_codes],
        "SCHEDULE": {
            "summary": detail.schedule_summary.model_dump(mode="json"),
            "attention_activities": [
                item.model_dump(mode="json") for item in detail.schedule_activities
            ],
        },
        "EQUIPMENT": {
            "summary": equipment.kpis.model_dump(mode="json"),
            "assignments": [item.model_dump(mode="json") for item in equipment.assignments],
        },
        "CORRESPONDENCE": {
            "exposure_buckets": [item.model_dump(mode="json") for item in detail.exposure_buckets],
            "events": [item.model_dump(mode="json") for item in detail.correspondence_events],
        },
        "SUBCONTRACTORS": [item.model_dump(mode="json") for item in detail.subcontractors],
    }
    return json.dumps(context, indent=2, ensure_ascii=False)


class GeminiJobQuestionAnswerer:
    def __init__(self, model: str | None = None) -> None:
        google_key = os.environ.get("GOOGLE_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if google_key and gemini_key:
            raise JobQuestionConfigurationError(
                "both GOOGLE_API_KEY and GEMINI_API_KEY are set; keep only GEMINI_API_KEY"
            )
        if not (google_key or gemini_key):
            raise JobQuestionConfigurationError(
                "GEMINI_API_KEY is not set; add it to the API server environment"
            )

        retry_options = types.HttpRetryOptions(
            attempts=2,
            initial_delay=1.0,
            max_delay=4.0,
            exp_base=2.0,
            jitter=1.0,
            http_status_codes=[408, 500, 502, 503, 504],
        )
        self._client = genai.Client(
            http_options=types.HttpOptions(
                timeout=120_000,
                retry_options=retry_options,
            )
        )
        self._model = (
            model
            or os.environ.get("GEMINI_QA_MODEL")
            or os.environ.get("GEMINI_MODEL")
            or DEFAULT_JOB_QA_MODEL
        )
        self._system_instruction = JOB_QA_PROMPT.read_text(encoding="utf-8")

    def answer(
        self,
        *,
        detail: JobDetail,
        equipment: EquipmentDashboard,
        question: str,
    ) -> JobQuestionResponse:
        context = build_job_context(detail, equipment)
        user_prompt = (
            f"Selected job: {detail.summary.job_id}\n"
            f"Question: {question.strip()}\n\n"
            "GOVERNED JOB CONTEXT\n"
            f"{context}\n"
            "END GOVERNED JOB CONTEXT"
        )
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_instruction,
                    temperature=0,
                    candidate_count=1,
                    max_output_tokens=1_200,
                    response_mime_type="application/json",
                    response_json_schema=JobQuestionResponse.model_json_schema(),
                ),
            )
            return JobQuestionResponse.model_validate(response.parsed)
        except Exception as exc:
            raise JobQuestionError(f"Gemini could not answer the job question: {exc}") from exc

    def close(self) -> None:
        self._client.close()


def answer_job_question(
    detail: JobDetail,
    equipment: EquipmentDashboard,
    question: str,
) -> JobQuestionResponse:
    answerer = GeminiJobQuestionAnswerer()
    try:
        return answerer.answer(detail=detail, equipment=equipment, question=question)
    finally:
        answerer.close()
