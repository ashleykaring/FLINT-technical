from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.config import Settings
from pipeline.ingest.runner import ingest_all
from pipeline.model.runner import build_model
from pipeline.transform.runner import transform_all

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def modeled_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    database_path = tmp_path_factory.mktemp("modeled-database") / "flint-modeled.duckdb"
    settings = Settings.from_root(PROJECT_ROOT, database_path)
    ingest_all(settings)
    transform_all(settings)
    build_model(settings)
    return settings
