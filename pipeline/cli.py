from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from pipeline.config import Settings
from pipeline.ingest.runner import IngestionError, ingest_all
from pipeline.model.runner import ModelBuildError, build_model
from pipeline.quality.report import load_quality_summary, render_quality_report
from pipeline.transform.runner import TransformationError, transform_all


def _add_path_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        help="Project root; defaults to the repository containing the package",
    )
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

    build_parser = subparsers.add_parser(
        "build",
        help="Run ingestion, transformation, modeling, and quality reporting",
    )
    _add_path_arguments(build_parser)
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
