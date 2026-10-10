from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from pipeline.ai.config import ExtractionSettings
from pipeline.ai.providers.base import BatchProviderResult, ExtractionUsage, ProviderResult
from pipeline.ai.schema import BatchCorrespondenceExtraction, CorrespondenceExtraction


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini credentials or configuration are missing."""


class GeminiResponseError(RuntimeError):
    """Raised when Gemini does not return a valid structured response."""


class GeminiProvider:
    def __init__(self, settings: ExtractionSettings) -> None:
        google_key = os.environ.get("GOOGLE_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if google_key and gemini_key:
            raise GeminiConfigurationError(
                "both GOOGLE_API_KEY and GEMINI_API_KEY are set; keep only GEMINI_API_KEY"
            )
        if not (google_key or gemini_key):
            raise GeminiConfigurationError(
                "GEMINI_API_KEY is not set; add it to the current shell environment"
            )

        retry_options = types.HttpRetryOptions(
            attempts=settings.retry_attempts,
            initial_delay=1.0,
            max_delay=8.0,
            exp_base=2.0,
            jitter=1.0,
            # A 429 may be a daily quota error lasting hours. Do not retry it
            # automatically and unexpectedly consume the request budget.
            http_status_codes=[408, 500, 502, 503, 504],
        )
        http_options = types.HttpOptions(
            timeout=settings.timeout_ms,
            retry_options=retry_options,
        )
        self._client = genai.Client(http_options=http_options)
        self._model = settings.model

    def extract(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
    ) -> ProviderResult:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0,
                candidate_count=1,
                response_mime_type="application/json",
                response_json_schema=CorrespondenceExtraction.model_json_schema(),
            ),
        )

        try:
            extraction = CorrespondenceExtraction.model_validate(response.parsed)
        except Exception as exc:
            raise GeminiResponseError(f"Gemini returned invalid structured output: {exc}") from exc

        usage_metadata = response.usage_metadata
        usage = ExtractionUsage(
            prompt_tokens=getattr(usage_metadata, "prompt_token_count", None),
            output_tokens=getattr(usage_metadata, "candidates_token_count", None),
            thoughts_tokens=getattr(usage_metadata, "thoughts_token_count", None),
            total_tokens=getattr(usage_metadata, "total_token_count", None),
        )
        raw_text = response.text or json.dumps(extraction.model_dump(mode="json"))
        return ProviderResult(
            extraction=extraction,
            raw_text=raw_text,
            response_id=getattr(response, "response_id", None),
            model_version=getattr(response, "model_version", None),
            usage=usage,
        )

    def extract_batch(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
    ) -> BatchProviderResult:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0,
                candidate_count=1,
                response_mime_type="application/json",
                response_json_schema=BatchCorrespondenceExtraction.model_json_schema(),
            ),
        )

        try:
            extraction = BatchCorrespondenceExtraction.model_validate(response.parsed)
        except Exception as exc:
            raise GeminiResponseError(
                f"Gemini returned invalid structured batch output: {exc}"
            ) from exc

        usage_metadata = response.usage_metadata
        usage = ExtractionUsage(
            prompt_tokens=getattr(usage_metadata, "prompt_token_count", None),
            output_tokens=getattr(usage_metadata, "candidates_token_count", None),
            thoughts_tokens=getattr(usage_metadata, "thoughts_token_count", None),
            total_tokens=getattr(usage_metadata, "total_token_count", None),
        )
        raw_text = response.text or json.dumps(extraction.model_dump(mode="json"))
        return BatchProviderResult(
            extraction=extraction,
            raw_text=raw_text,
            response_id=getattr(response, "response_id", None),
            model_version=getattr(response, "model_version", None),
            usage=usage,
        )

    def close(self) -> None:
        self._client.close()
