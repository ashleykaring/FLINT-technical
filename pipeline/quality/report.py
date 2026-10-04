from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class QualitySummary:
    total_issues: int
    severity_counts: tuple[tuple[str, int], ...]
    check_counts: tuple[tuple[str, str, int], ...]


def load_quality_summary(database_path: Path) -> QualitySummary:
    if not database_path.is_file():
        raise FileNotFoundError(f"DuckDB database does not exist: {database_path}")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        if "dq_issues" not in tables:
            raise ValueError("dq_issues does not exist; run `flint transform` first")

        total = connection.execute("SELECT count(*) FROM dq_issues").fetchone()[0]
        severity_counts = tuple(
            connection.execute(
                """
                SELECT severity, count(*)
                FROM dq_issues
                GROUP BY severity
                ORDER BY CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END
                """
            ).fetchall()
        )
        check_counts = tuple(
            connection.execute(
                """
                SELECT severity, check_name, count(*)
                FROM dq_issues
                GROUP BY severity, check_name
                ORDER BY CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                         check_name
                """
            ).fetchall()
        )

    return QualitySummary(total, severity_counts, check_counts)


def render_quality_report(summary: QualitySummary) -> str:
    lines = [f"Data-quality issues: {summary.total_issues:,}", ""]
    for severity, count in summary.severity_counts:
        lines.append(f"{severity.upper():<8} {count:>8,}")

    lines.extend(["", f"{'Severity':<10} {'Check':<38} {'Rows':>8}"])
    lines.append(f"{'-' * 10} {'-' * 38} {'-' * 8}")
    for severity, check_name, count in summary.check_counts:
        lines.append(f"{severity:<10} {check_name:<38} {count:>8,}")
    return "\n".join(lines)
