from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pipeline.ai.schema import BatchCorrespondenceExtraction, CorrespondenceExtraction


@dataclass(frozen=True)
class ExtractionUsage:
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    thoughts_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ProviderResult:
    extraction: CorrespondenceExtraction
    raw_text: str
    response_id: str | None = None
    model_version: str | None = None
    usage: ExtractionUsage = ExtractionUsage()


@dataclass(frozen=True)
class BatchProviderResult:
    extraction: BatchCorrespondenceExtraction
    raw_text: str
    response_id: str | None = None
    model_version: str | None = None
    usage: ExtractionUsage = ExtractionUsage()


class ExtractionProvider(Protocol):
    def extract_batch(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
    ) -> BatchProviderResult: ...

    def close(self) -> None: ...
