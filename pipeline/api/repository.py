from __future__ import annotations

from decimal import Decimal

import duckdb

from pipeline.api.schemas import (
    DashboardFilters,
    FilterOptions,
    JobSummary,
    ParetoPoint,
    PortfolioDashboard,
    PortfolioKpis,
    ScenarioSummary,
    StatusCount,
)
from pipeline.config import Settings

REQUIRED_TABLES = {"mart_job_dashboard", "mart_cost_vs_progress"}


class DashboardDataError(RuntimeError):
    """Raised when dashboard-ready analytical data is unavailable."""


def _number(value: Decimal | float | int | None) -> float:
    return float(value or 0)


def _optional_number(value: Decimal | float | int | None) -> float | None:
    return None if value is None else float(value)


def _where(filters: DashboardFilters) -> tuple[str, list[str]]:
    conditions: list[str] = []
    parameters: list[str] = []
    fields = (
        ("dashboard.division", filters.division),
        ("dashboard.contract_type", filters.contract_type),
        ("dashboard.project_manager_id", filters.project_manager_id),
        ("progress.cost_progress_status", filters.progress_status),
    )
    for field, value in fields:
        if value:
            conditions.append(f"{field} = ?")
            parameters.append(value)
    clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    return clause, parameters


def _validate_tables(connection: duckdb.DuckDBPyConnection) -> None:
    existing = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise DashboardDataError(
            "dashboard marts are missing; run `flint analyze` first: " + ", ".join(missing)
        )


def _options(connection: duckdb.DuckDBPyConnection) -> FilterOptions:
    def values(column: str, table: str = "mart_job_dashboard") -> list[str]:
        rows = connection.execute(
            f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY {column}"
        ).fetchall()
        return [row[0] for row in rows]

    return FilterOptions(
        divisions=values("division"),
        contract_types=values("contract_type"),
        project_managers=values("project_manager_id"),
        progress_statuses=values("cost_progress_status", "mart_cost_vs_progress"),
    )


def _base_query(where_clause: str) -> str:
    return f"""
        FROM mart_job_dashboard AS dashboard
        JOIN mart_cost_vs_progress AS progress USING (job_key)
        {where_clause}
    """


def _kpis(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> PortfolioKpis:
    row = connection.execute(
        """
        SELECT
            coalesce(sum(dashboard.current_cost_budget), 0),
            coalesce(sum(dashboard.base_projected_final_cost), 0),
            coalesce(sum(dashboard.base_projected_cost_variance), 0),
            coalesce(sum(dashboard.confirmed_unbooked_cost), 0),
            coalesce(sum(dashboard.potential_downside_cost), 0),
            count(*),
            count(*) FILTER (
                WHERE progress.cost_progress_status IN ('watch', 'high', 'critical')
            )
        """
        + _base_query(where_clause),
        parameters,
    ).fetchone()
    return PortfolioKpis(
        current_cost_budget=_number(row[0]),
        projected_final_cost=_number(row[1]),
        projected_cost_variance=_number(row[2]),
        confirmed_unbooked_cost=_number(row[3]),
        potential_downside_cost=_number(row[4]),
        jobs_in_view=row[5],
        jobs_requiring_attention=row[6],
    )


def _scenarios(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> list[ScenarioSummary]:
    row = connection.execute(
        """
        SELECT
            coalesce(sum(base_contract_value_proxy), 0),
            coalesce(sum(base_projected_final_cost), 0),
            coalesce(sum(base_projected_margin), 0),
            coalesce(sum(confirmed_adjusted_contract_value_proxy), 0),
            coalesce(sum(confirmed_adjusted_final_cost), 0),
            coalesce(sum(confirmed_adjusted_margin), 0),
            coalesce(sum(downside_scenario_final_cost), 0),
            coalesce(sum(downside_scenario_margin), 0)
        """
        + _base_query(where_clause),
        parameters,
    ).fetchone()
    base_margin = _number(row[2])
    return [
        ScenarioSummary(
            scenario="Base forecast",
            contract_value_proxy=_number(row[0]),
            projected_final_cost=_number(row[1]),
            projected_margin=base_margin,
            change_from_base=0,
        ),
        ScenarioSummary(
            scenario="Confirmed adjusted",
            contract_value_proxy=_number(row[3]),
            projected_final_cost=_number(row[4]),
            projected_margin=_number(row[5]),
            change_from_base=_number(row[5]) - base_margin,
        ),
        ScenarioSummary(
            scenario="Downside",
            contract_value_proxy=_number(row[3]),
            projected_final_cost=_number(row[6]),
            projected_margin=_number(row[7]),
            change_from_base=_number(row[7]) - base_margin,
        ),
    ]


def _status_counts(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> list[StatusCount]:
    rows = connection.execute(
        "SELECT progress.cost_progress_status, count(*) AS job_count "
        + _base_query(where_clause)
        + " GROUP BY progress.cost_progress_status ORDER BY job_count DESC",
        parameters,
    ).fetchall()
    return [StatusCount(status=row[0], job_count=row[1]) for row in rows]


def _jobs(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> list[JobSummary]:
    rows = connection.execute(
        """
        SELECT
            dashboard.job_id,
            dashboard.division,
            dashboard.contract_type,
            dashboard.project_manager_id,
            dashboard.current_cost_budget,
            dashboard.base_projected_final_cost,
            dashboard.base_projected_cost_variance,
            dashboard.reported_progress_pct,
            dashboard.cost_spent_pct,
            dashboard.cost_progress_variance,
            dashboard.confirmed_unbooked_cost,
            dashboard.potential_downside_cost,
            dashboard.maximum_reported_delay_days,
            progress.cost_progress_status,
            dashboard.combined_risk_level,
            dashboard.combined_risk_reasons
        """
        + _base_query(where_clause)
        + """
        ORDER BY
            greatest(dashboard.base_projected_cost_variance, 0)
                + dashboard.potential_downside_cost DESC,
            dashboard.job_id
        """,
        parameters,
    ).fetchall()
    return [
        JobSummary(
            job_id=row[0],
            division=row[1],
            contract_type=row[2],
            project_manager_id=row[3],
            current_cost_budget=_number(row[4]),
            projected_final_cost=_number(row[5]),
            projected_cost_variance=_number(row[6]),
            reported_progress_pct=_optional_number(row[7]),
            cost_spent_pct=_optional_number(row[8]),
            cost_progress_variance=_optional_number(row[9]),
            confirmed_unbooked_cost=_number(row[10]),
            potential_downside_cost=_number(row[11]),
            maximum_reported_delay_days=row[12],
            progress_status=row[13],
            combined_risk_level=row[14],
            risk_reasons=row[15] or "No triggered risk rule",
        )
        for row in rows
    ]


def _pareto(jobs: list[JobSummary]) -> list[ParetoPoint]:
    exposures = [(job.job_id, max(job.projected_cost_variance, 0)) for job in jobs]
    exposures.sort(key=lambda item: item[1], reverse=True)
    total = sum(value for _, value in exposures)
    cumulative = 0.0
    points = []
    for rank, (job_id, value) in enumerate(exposures, start=1):
        cumulative += value
        points.append(
            ParetoPoint(
                rank=rank,
                job_id=job_id,
                exposure=value,
                cumulative_pct=cumulative / total if total else 0,
            )
        )
    return points


def load_portfolio_dashboard(
    settings: Settings,
    filters: DashboardFilters | None = None,
) -> PortfolioDashboard:
    if not settings.database_path.is_file():
        raise DashboardDataError(
            f"DuckDB database does not exist; run `flint build`: {settings.database_path}"
        )

    applied = filters or DashboardFilters()
    where_clause, parameters = _where(applied)
    try:
        connection = duckdb.connect(str(settings.database_path), read_only=True)
        _validate_tables(connection)
        jobs = _jobs(connection, where_clause, parameters)
        return PortfolioDashboard(
            filters=_options(connection),
            applied_filters=applied,
            kpis=_kpis(connection, where_clause, parameters),
            scenarios=_scenarios(connection, where_clause, parameters),
            status_counts=_status_counts(connection, where_clause, parameters),
            jobs=jobs,
            pareto=_pareto(jobs),
        )
    except duckdb.Error as exc:
        raise DashboardDataError(f"could not query dashboard data: {exc}") from exc
    finally:
        if "connection" in locals():
            connection.close()
