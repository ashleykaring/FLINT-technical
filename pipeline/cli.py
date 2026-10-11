from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from pipeline.ai.annotations import (
    AnnotationError,
    prepare_annotations,
    render_validation_result,
    validate_annotations,
)
from pipeline.ai.config import ExtractionSettings
from pipeline.ai.evaluation import EvaluationError, evaluate_extractions, render_evaluation
from pipeline.ai.modeling import CorrespondenceModelError, build_correspondence_model
from pipeline.ai.providers.gemini import GeminiConfigurationError
from pipeline.ai.runner import ExtractionError, extract_correspondence, render_extraction_result
from pipeline.analysis.runner import AnalysisBuildError, build_analysis
from pipeline.api.app import create_app
from pipeline.config import Settings
from pipeline.ingest.runner import IngestionError, ingest_all
from pipeline.model.runner import ModelBuildError, build_model
from pipeline.quality.report import load_quality_summary, render_quality_report
from pipeline.transform.runner import TransformationError, transform_all


def _add_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        help="Project root; defaults to the repository containing the package",
    )


def _add_path_arguments(parser: argparse.ArgumentParser) -> None:
    _add_root_argument(parser)
    parser.add_argument(
        "--database",
        type=Path,
        help="DuckDB path; relative paths are resolved from the project root",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flint",
        description="FLINT construction portfolio data pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Load all static extracts into DuckDB",
    )
    _add_path_arguments(ingest_parser)

    transform_parser = subparsers.add_parser(
        "transform",
        help="Build typed staging tables and data-quality issues",
    )
    _add_path_arguments(transform_parser)

    quality_parser = subparsers.add_parser(
        "quality",
        help="Print the latest data-quality report",
    )
    _add_path_arguments(quality_parser)

    model_parser = subparsers.add_parser(
        "model",
        help="Build dimensions, facts, analytical marts, and reconciliations",
    )
    _add_path_arguments(model_parser)

    correspondence_model_parser = subparsers.add_parser(
        "model-correspondence",
        help="Build the governed current correspondence fact and quality checks",
    )
    _add_path_arguments(correspondence_model_parser)

    analysis_parser = subparsers.add_parser(
        "analyze",
        help="Build question-aligned risk and exposure marts",
    )
    _add_path_arguments(analysis_parser)

    api_parser = subparsers.add_parser(
        "serve-api",
        help="Serve the read-only dashboard API",
    )
    _add_path_arguments(api_parser)
    api_parser.add_argument("--host", default="127.0.0.1", help="API bind address")
    api_parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")

    build_parser = subparsers.add_parser(
        "build",
        help="Run ingestion, transformation, modeling, and quality reporting",
    )
    _add_path_arguments(build_parser)

    prepare_labels_parser = subparsers.add_parser(
        "prepare-labels",
        help="Create a balanced correspondence annotation set",
    )
    _add_root_argument(prepare_labels_parser)
    prepare_labels_parser.add_argument(
        "--per-type",
        type=int,
        default=15,
        help="Documents to sample for each correspondence type (default: 15)",
    )
    prepare_labels_parser.add_argument(
        "--seed",
        type=int,
        default=20261004,
        help="Deterministic sampling seed",
    )
    prepare_labels_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing annotation files, including manual labels",
    )

    validate_labels_parser = subparsers.add_parser(
        "validate-labels",
        help="Validate manual correspondence labels and report progress",
    )
    _add_root_argument(validate_labels_parser)

    extract_parser = subparsers.add_parser(
        "extract-correspondence",
        help="Extract structured events from correspondence with Gemini",
    )
    _add_path_arguments(extract_parser)
    selection = extract_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--doc-id",
        action="append",
        help="Document ID to extract; may be specified more than once",
    )
    selection.add_argument(
        "--gold-complete",
        action="store_true",
        help="Extract all manually completed gold documents",
    )
    selection.add_argument(
        "--all",
        dest="all_documents",
        action="store_true",
        help="Extract every correspondence document",
    )
    extract_parser.add_argument("--limit", type=int, help="Maximum documents to process")
    extract_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Documents per Gemini request, from 1 to 100 (default: 100)",
    )
    extract_parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=15.0,
        help="Minimum time between Gemini requests (default: 15)",
    )
    extract_parser.add_argument(
        "--request-budget",
        type=int,
        default=20,
        help="Refuse a run requiring more API calls than this value (default: 20)",
    )
    extract_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show cache usage and required API calls without contacting Gemini",
    )
    extract_parser.add_argument("--model", help="Gemini model override")
    extract_parser.add_argument(
        "--force",
        action="store_true",
        help="Call Gemini even when an identical cached extraction exists",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate-extraction",
        help="Compare saved model extractions with completed gold labels",
    )
    _add_path_arguments(evaluate_parser)
    return parser


def _print_table_summary(title: str, results: Sequence[object]) -> None:
    print(f"{title}\n")
    print(f"{'Table':<38} {'Rows':>10}")
    print(f"{'-' * 38} {'-' * 10}")
    for result in results:
        print(f"{result.table_name:<38} {result.row_count:>10,}")


def _print_quality(database_path: Path) -> None:
    print(render_quality_report(load_quality_summary(database_path)))


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "prepare-labels":
        settings = Settings.from_root(args.root)
        try:
            paths = prepare_annotations(
                settings,
                per_type=args.per_type,
                seed=args.seed,
                force=args.force,
            )
        except AnnotationError as exc:
            print(f"Annotation preparation failed: {exc}")
            return 1
        print("Annotation set prepared")
        print(f"\nSample:     {paths.sample}")
        print(f"Labels:     {paths.labels}")
        print(f"Entity IDs: {paths.entities}")
        return 0

    if args.command == "validate-labels":
        settings = Settings.from_root(args.root)
        try:
            result = validate_annotations(settings)
        except AnnotationError as exc:
            print(f"Annotation validation failed: {exc}")
            return 1
        print(render_validation_result(result))
        return 1 if result.issues else 0

    if args.command == "extract-correspondence":
        project = Settings.from_root(args.root, args.database)
        extraction_settings = ExtractionSettings.from_project(project, model=args.model)
        try:
            result = extract_correspondence(
                extraction_settings,
                document_ids=args.doc_id,
                gold_complete=args.gold_complete,
                all_documents=args.all_documents,
                limit=args.limit,
                batch_size=args.batch_size,
                request_interval_seconds=args.request_interval_seconds,
                request_budget=args.request_budget,
                dry_run=args.dry_run,
                force=args.force,
            )
        except (ExtractionError, GeminiConfigurationError, FileNotFoundError, ValueError) as exc:
            print(f"Correspondence extraction failed: {exc}")
            return 1
        print(render_extraction_result(result))
        return 1 if result.failed_count else 0

    if args.command == "evaluate-extraction":
        settings = Settings.from_root(args.root, args.database)
        try:
            result = evaluate_extractions(settings)
        except (EvaluationError, FileNotFoundError, ValueError) as exc:
            print(f"Extraction evaluation failed: {exc}")
            return 1
        print(render_evaluation(result))
        return 0

    if args.command == "ingest":
        settings = Settings.from_root(args.root, args.database)
        try:
            results = ingest_all(settings)
        except IngestionError as exc:
            print(f"Ingestion failed: {exc}")
            return 1
        _print_table_summary("Ingestion completed", results)
        print(f"\nDatabase: {settings.database_path}")
        return 0

    if args.command == "transform":
        settings = Settings.from_root(args.root, args.database)
        try:
            results = transform_all(settings)
            _print_table_summary("Transformation completed", results)
            print()
            _print_quality(settings.database_path)
        except (TransformationError, FileNotFoundError, ValueError) as exc:
            print(f"Transformation failed: {exc}")
            return 1
        return 0

    if args.command == "quality":
        settings = Settings.from_root(args.root, args.database)
        try:
            _print_quality(settings.database_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Quality report failed: {exc}")
            return 1
        return 0

    if args.command == "model":
        settings = Settings.from_root(args.root, args.database)
        try:
            results = build_model(settings)
            _print_table_summary("Model build completed", results)
            print(f"\nDatabase: {settings.database_path}")
        except (ModelBuildError, FileNotFoundError, ValueError) as exc:
            print(f"Model build failed: {exc}")
            return 1
        return 0

    if args.command == "model-correspondence":
        settings = Settings.from_root(args.root, args.database)
        try:
            results = build_correspondence_model(settings)
            _print_table_summary("Correspondence model completed", results)
            print(f"\nDatabase: {settings.database_path}")
        except (CorrespondenceModelError, FileNotFoundError, ValueError) as exc:
            print(f"Correspondence model failed: {exc}")
            return 1
        return 0

    if args.command == "analyze":
        settings = Settings.from_root(args.root, args.database)
        try:
            results = build_analysis(settings)
            _print_table_summary("Analysis build completed", results)
            print(f"\nDatabase: {settings.database_path}")
        except (AnalysisBuildError, FileNotFoundError, ValueError) as exc:
            print(f"Analysis build failed: {exc}")
            return 1
        return 0

    if args.command == "serve-api":
        import uvicorn

        settings = Settings.from_root(args.root, args.database)
        uvicorn.run(create_app(settings), host=args.host, port=args.port)
        return 0

    if args.command == "build":
        settings = Settings.from_root(args.root, args.database)
        try:
            ingestion_results = ingest_all(settings)
            transformation_results = transform_all(settings)
            model_results = build_model(settings)
            _print_table_summary("Ingestion completed", ingestion_results)
            print()
            _print_table_summary("Transformation completed", transformation_results)
            print()
            _print_table_summary("Model build completed", model_results)
            print()
            _print_quality(settings.database_path)
            print(f"\nDatabase: {settings.database_path}")
        except (
            IngestionError,
            ModelBuildError,
            TransformationError,
            FileNotFoundError,
            ValueError,
        ) as exc:
            print(f"Build failed: {exc}")
            return 1
        return 0

    return 2
