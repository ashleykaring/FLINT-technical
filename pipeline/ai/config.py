from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import Settings

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
PROMPT_VERSION = "correspondence-v3"
SCHEMA_VERSION = "correspondence-event-v2"


@dataclass(frozen=True)
class ExtractionSettings:
    project: Settings
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    timeout_ms: int
    retry_attempts: int
    raw_response_dir: Path

    @classmethod
    def from_project(
        cls,
        project: Settings,
        *,
        model: str | None = None,
    ) -> ExtractionSettings:
        selected_model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        return cls(
            project=project,
            provider="gemini",
            model=selected_model,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            timeout_ms=300_000,
            # One attempt keeps a transient provider failure from silently
            # consuming several requests from a small daily quota.
            retry_attempts=1,
            raw_response_dir=project.project_root / "artifacts" / "llm" / "raw_responses",
        )
