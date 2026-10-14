from __future__ import annotations

from types import SimpleNamespace

import pytest

import pipeline.refresh as refresh_module
from pipeline.ai.config import ExtractionSettings
from pipeline.config import Settings
from pipeline.refresh import RefreshError, refresh_all


def test_refresh_runs_governed_stages_in_order(tmp_path, monkeypatch) -> None:
    settings = Settings.from_root(tmp_path, tmp_path / "warehouse" / "test.duckdb")
    extraction_settings = ExtractionSettings.from_project(settings, model="test-model")
    calls: list[str] = []
    progress: list[str] = []

    def stage(name: str):
        def run(*args, **kwargs):
            calls.append(name)
            return [SimpleNamespace(table_name=name, row_count=1)]

        return run

    extraction = SimpleNamespace(failed_count=0, skipped_count=0)
    monkeypatch.setattr(refresh_module, "ingest_all", stage("ingest"))
    monkeypatch.setattr(refresh_module, "transform_all", stage("transform"))
    monkeypatch.setattr(refresh_module, "build_model", stage("model"))

    def extract(*args, **kwargs):
        calls.append("extract")
        return extraction

    monkeypatch.setattr(refresh_module, "extract_correspondence", extract)
    monkeypatch.setattr(
        refresh_module,
        "build_correspondence_model",
        stage("correspondence"),
    )
    monkeypatch.setattr(refresh_module, "build_analysis", stage("analysis"))

    result = refresh_all(
        settings,
        extraction_settings,
        progress=progress.append,
    )

    assert calls == [
        "ingest",
        "transform",
        "model",
        "extract",
        "correspondence",
        "analysis",
    ]
    assert result.extraction is extraction
    assert progress[0].startswith("[1/6]")
    assert progress[-1].startswith("[6/6]")


def test_refresh_stops_before_modeling_failed_extraction(tmp_path, monkeypatch) -> None:
    settings = Settings.from_root(tmp_path, tmp_path / "warehouse" / "test.duckdb")
    extraction_settings = ExtractionSettings.from_project(settings, model="test-model")
    monkeypatch.setattr(refresh_module, "ingest_all", lambda settings: [])
    monkeypatch.setattr(refresh_module, "transform_all", lambda settings: [])
    monkeypatch.setattr(refresh_module, "build_model", lambda settings: [])
    monkeypatch.setattr(
        refresh_module,
        "extract_correspondence",
        lambda *args, **kwargs: SimpleNamespace(failed_count=1, skipped_count=3),
    )

    with pytest.raises(RefreshError, match="1 failed, 3 skipped"):
        refresh_all(settings, extraction_settings)
