from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pipeline.ai.config import ExtractionSettings
from pipeline.ai.modeling import CorrespondenceModelResult, build_correspondence_model
from pipeline.ai.providers.base import ExtractionProvider
from pipeline.ai.runner import ExtractionRunResult, extract_correspondence
from pipeline.analysis.runner import AnalysisBuildResult, build_analysis
from pipeline.config import Settings
from pipeline.ingest.runner import SourceLoadResult, ingest_all
from pipeline.model.runner import ModelBuildResult, build_model
from pipeline.transform.runner import TransformationResult, transform_all


class RefreshError(RuntimeError):
    """Raised when an end-to-end refresh cannot reach a publishable analysis state."""


@dataclass(frozen=True)
class RefreshResult:
    ingestion: tuple[SourceLoadResult, ...]
    transformation: tuple[TransformationResult, ...]
    model: tuple[ModelBuildResult, ...]
    extraction: ExtractionRunResult
    correspondence_model: tuple[CorrespondenceModelResult, ...]
    analysis: tuple[AnalysisBuildResult, ...]


def refresh_all(
    settings: Settings,
    extraction_settings: ExtractionSettings,
    *,
    batch_size: int = 100,
    request_interval_seconds: float = 15.0,
    request_budget: int = 20,
    provider: ExtractionProvider | None = None,
    progress: Callable[[str], None] | None = None,
) -> RefreshResult:
    """Rebuild every governed layer and extract only uncached correspondence."""
    announce = progress or (lambda _: None)
    announce("[1/6] Ingesting source extracts")
    ingestion = tuple(ingest_all(settings))
    announce("[2/6] Transforming and validating source data")
    transformation = tuple(transform_all(settings))
    announce("[3/6] Building dimensions, facts, and base marts")
    model = tuple(build_model(settings))
    announce("[4/6] Extracting new or changed correspondence")
    extraction = extract_correspondence(
        extraction_settings,
        all_documents=True,
        batch_size=batch_size,
        request_interval_seconds=request_interval_seconds,
        request_budget=request_budget,
        provider=provider,
    )
    if extraction.failed_count or extraction.skipped_count:
        raise RefreshError(
            "correspondence extraction did not complete: "
            f"{extraction.failed_count} failed, {extraction.skipped_count} skipped"
        )
    announce("[5/6] Building the governed correspondence model")
    correspondence_model = tuple(build_correspondence_model(settings))
    announce("[6/6] Building analysis marts and reconciliations")
    analysis = tuple(build_analysis(settings))
    return RefreshResult(
        ingestion=ingestion,
        transformation=transformation,
        model=model,
        extraction=extraction,
        correspondence_model=correspondence_model,
        analysis=analysis,
    )
