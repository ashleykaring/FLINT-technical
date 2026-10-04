from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Filesystem settings for a local pipeline run."""

    project_root: Path
    raw_data_dir: Path
    database_path: Path

    @classmethod
    def from_root(
        cls,
        project_root: Path | None = None,
        database_path: Path | None = None,
    ) -> Settings:
        root = (project_root or Path(__file__).resolve().parents[1]).resolve()
        database = database_path or root / "warehouse" / "flint.duckdb"
        if not database.is_absolute():
            database = root / database

        return cls(
            project_root=root,
            raw_data_dir=root / "data" / "raw",
            database_path=database.resolve(),
        )
