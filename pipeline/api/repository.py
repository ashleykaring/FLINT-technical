from __future__ import annotations

from decimal import Decimal

import duckdb

from pipeline.api.schemas import (
    BudgetOutlookSummary,
    CorrespondenceEventDetail,
    CorrespondenceJobInsight,
    CostCodeDetail,
    CostCodeRiskInsight,
    CostProgressInsight,
    DashboardFilters,
    DivisionInsight,
    EquipmentAssignment,
    EquipmentBreakdown,
    EquipmentDashboard,
    EquipmentFilterOptions,
    EquipmentFilters,
    EquipmentInsight,
    EquipmentKpis,
    EquipmentTypeSummary,
    ExposureBucket,
    FilterOptions,
    InsightsHeadline,
    JobDetail,
    JobFinancialSummary,
    JobSummary,
    MonthlyCostPoint,
    ParetoPoint,
    PortfolioAnomalies,
    PortfolioDashboard,
    PortfolioInsights,
    PortfolioKpis,
    QualityInsight,
    ReconciliationInsight,
    RiskRankingInsight,
    ScenarioSummary,
    ScheduleActivityDetail,
    ScheduleSummary,
    StatusCount,
    SubcontractorJobExposure,
    SubcontractorRiskInsight,
)
from pipeline.config import Settings

REQUIRED_TABLES = {
    "analysis_dq_issues",
    "dq_issues",
    "dim_cost_code",
    "dim_job",
    "dim_subcontractor",
    "fact_budget",
    "fact_cost_transaction",
    "fact_equipment_usage",
    "fact_schedule_activity",
    "mart_correspondence_exposure",
    "mart_correspondence_cost_code_exposure",
    "mart_cost_code_exposure",
    "mart_cost_vs_progress",
    "mart_equipment_economics",
    "mart_job_dashboard",
    "mart_job_correspondence_exposure",
    "mart_job_financial",
    "mart_monthly_cost_trend",
    "mart_subcontractor_combined_exposure",
    "model_analysis_reconciliation",
    "model_correspondence_reconciliation",
    "model_reconciliation",
}


class DashboardDataError(RuntimeError):
    """Raised when dashboard-ready analytical data is unavailable."""


class JobNotFoundError(DashboardDataError):
    """Raised when a requested canonical job does not exist."""


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
            coalesce(sum(dashboard.adjusted_actual_cost), 0),
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
        actual_cost_to_date=_number(row[1]),
        projected_final_cost=_number(row[2]),
        projected_cost_variance=_number(row[3]),
        confirmed_unbooked_cost=_number(row[4]),
        potential_downside_cost=_number(row[5]),
        jobs_in_view=row[6],
        jobs_requiring_attention=row[7],
    )


def _budget_outlook(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> BudgetOutlookSummary:
    row = connection.execute(
        """
        SELECT
            count(*),
            count(*) FILTER (
                WHERE dashboard.current_cost_budget IS NOT NULL
                  AND dashboard.adjusted_actual_cost > dashboard.current_cost_budget
            ),
            count(*) FILTER (
                WHERE dashboard.current_cost_budget IS NOT NULL
                  AND dashboard.adjusted_actual_cost <= dashboard.current_cost_budget
                  AND dashboard.base_projected_final_cost > dashboard.current_cost_budget
            ),
            count(*) FILTER (
                WHERE dashboard.current_cost_budget IS NOT NULL
                  AND dashboard.base_projected_final_cost <= dashboard.current_cost_budget
            ),
            count(*) FILTER (WHERE dashboard.current_cost_budget IS NULL),
            coalesce(sum(
                greatest(dashboard.adjusted_actual_cost - dashboard.current_cost_budget, 0)
            ) FILTER (WHERE dashboard.current_cost_budget IS NOT NULL), 0),
            coalesce(sum(
                greatest(dashboard.base_projected_final_cost - dashboard.current_cost_budget, 0)
            ) FILTER (WHERE dashboard.current_cost_budget IS NOT NULL), 0),
            coalesce(sum(
                dashboard.base_projected_final_cost - dashboard.current_cost_budget
            ) FILTER (
                WHERE dashboard.current_cost_budget IS NOT NULL
                  AND dashboard.adjusted_actual_cost <= dashboard.current_cost_budget
                  AND dashboard.base_projected_final_cost > dashboard.current_cost_budget
            ), 0)
        """
        + _base_query(where_clause),
        parameters,
    ).fetchone()
    return BudgetOutlookSummary(
        total_jobs=row[0],
        currently_over_count=row[1],
        forecast_only_count=row[2],
        within_forecast_count=row[3],
        missing_budget_count=row[4],
        current_gross_overrun=_number(row[5]),
        projected_gross_overrun=_number(row[6]),
        forecast_only_exposure=_number(row[7]),
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
            dashboard.combined_risk_reasons,
            dashboard.adjusted_actual_cost,
            CASE
                WHEN dashboard.current_cost_budget IS NULL THEN 'missing_budget'
                WHEN dashboard.adjusted_actual_cost > dashboard.current_cost_budget
                    THEN 'already_over'
                WHEN dashboard.base_projected_final_cost > dashboard.current_cost_budget
                    THEN 'forecast_over'
                ELSE 'within_forecast'
            END AS budget_outlook
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
            adjusted_actual_cost=_number(row[16]),
            budget_outlook=row[17],
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
            budget_outlook=_budget_outlook(connection, where_clause, parameters),
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


def _date(value: object | None) -> str | None:
    return None if value is None else str(value)


def _job_summary(connection: duckdb.DuckDBPyConnection, job_id: str) -> JobFinancialSummary:
    row = connection.execute(
        """
        SELECT
            dashboard.job_id,
            dashboard.division,
            dashboard.contract_type,
            dashboard.project_manager_id,
            jobs.start_date,
            jobs.planned_days,
            dashboard.reported_progress_pct,
            dashboard.cost_spent_pct,
            progress.cost_progress_status,
            dashboard.combined_risk_level,
            dashboard.combined_risk_reasons,
            dashboard.base_contract_value_proxy,
            dashboard.current_cost_budget,
            dashboard.adjusted_actual_cost,
            dashboard.committed_cost,
            dashboard.forecast_remaining,
            dashboard.base_projected_final_cost,
            dashboard.base_projected_cost_variance,
            dashboard.base_projected_margin,
            dashboard.confirmed_unbooked_cost,
            dashboard.unbooked_contract_value,
            dashboard.potential_downside_cost,
            dashboard.reported_budget_variance,
            dashboard.unquantified_backcharge_count,
            dashboard.schedule_event_count,
            dashboard.maximum_reported_delay_days
        FROM mart_job_dashboard AS dashboard
        JOIN mart_cost_vs_progress AS progress USING (job_key)
        JOIN dim_job AS jobs USING (job_key)
        WHERE dashboard.job_id = ?
        """,
        [job_id],
    ).fetchone()
    if row is None:
        raise JobNotFoundError(f"job does not exist: {job_id}")
    return JobFinancialSummary(
        job_id=row[0],
        division=row[1],
        contract_type=row[2],
        project_manager_id=row[3],
        start_date=_date(row[4]),
        planned_days=row[5],
        reported_progress_pct=_optional_number(row[6]),
        cost_spent_pct=_optional_number(row[7]),
        progress_status=row[8],
        combined_risk_level=row[9],
        risk_reasons=row[10] or "No triggered risk rule",
        contract_value_proxy=_number(row[11]),
        current_cost_budget=_number(row[12]),
        adjusted_actual_cost=_number(row[13]),
        committed_cost=_number(row[14]),
        forecast_remaining=_number(row[15]),
        projected_final_cost=_number(row[16]),
        projected_cost_variance=_number(row[17]),
        projected_margin=_number(row[18]),
        confirmed_unbooked_cost=_number(row[19]),
        unbooked_contract_value=_number(row[20]),
        potential_downside_cost=_number(row[21]),
        reported_budget_variance=_number(row[22]),
        unquantified_backcharge_count=row[23],
        schedule_event_count=row[24],
        maximum_reported_delay_days=row[25],
    )


def _job_scenarios(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
) -> list[ScenarioSummary]:
    row = connection.execute(
        """
        SELECT
            base_contract_value_proxy,
            base_projected_final_cost,
            base_projected_margin,
            confirmed_adjusted_contract_value_proxy,
            confirmed_adjusted_final_cost,
            confirmed_adjusted_margin,
            downside_scenario_final_cost,
            downside_scenario_margin
        FROM mart_job_dashboard
        WHERE job_id = ?
        """,
        [job_id],
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


def _monthly_costs(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
) -> list[MonthlyCostPoint]:
    rows = connection.execute(
        """
        SELECT
            period,
            coalesce(sum(actual_cost), 0),
            coalesce(sum(adjustment), 0),
            coalesce(sum(committed_cost), 0),
            coalesce(sum(forecast_remaining), 0),
            coalesce(sum(adjusted_actual_cost), 0),
            coalesce(sum(cumulative_adjusted_actual_cost), 0)
        FROM mart_monthly_cost_trend
        WHERE job_id = ?
        GROUP BY period
        ORDER BY period
        """,
        [job_id],
    ).fetchall()
    return [
        MonthlyCostPoint(
            period=_date(row[0]) or "",
            actual_cost=_number(row[1]),
            adjustment=_number(row[2]),
            committed_cost=_number(row[3]),
            forecast_remaining=_number(row[4]),
            adjusted_actual_cost=_number(row[5]),
            cumulative_adjusted_actual_cost=_number(row[6]),
        )
        for row in rows
    ]


def _cost_codes(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
) -> list[CostCodeDetail]:
    rows = connection.execute(
        """
        WITH budget AS (
            SELECT cost_code_key, sum(current_budget_basis) AS current_budget
            FROM fact_budget
            WHERE job_key = ?
            GROUP BY cost_code_key
        ),
        costs AS (
            SELECT
                cost_code_key,
                sum(amount) FILTER (WHERE transaction_type = 'ACTUAL') AS actual_cost,
                sum(amount) FILTER (WHERE transaction_type = 'ADJUSTMENT') AS adjustment,
                sum(amount) FILTER (WHERE transaction_type = 'COMMITTED') AS committed_cost,
                sum(amount) FILTER (WHERE transaction_type = 'FORECAST') AS forecast_remaining
            FROM fact_cost_transaction
            WHERE job_key = ?
            GROUP BY cost_code_key
        ),
        correspondence AS (
            SELECT
                coalesce(cost_code_key, 'UNMAPPED_COST_CODE') AS cost_code_key,
                sum(amount) FILTER (WHERE exposure_category = 'confirmed_unbooked_cost')
                    AS confirmed_unbooked_cost,
                sum(potential_downside_amount) AS potential_downside_cost
            FROM mart_correspondence_exposure
            WHERE job_id = ?
            GROUP BY coalesce(cost_code_key, 'UNMAPPED_COST_CODE')
        ),
        keys AS (
            SELECT cost_code_key FROM budget
            UNION
            SELECT cost_code_key FROM costs
            UNION
            SELECT cost_code_key FROM correspondence
        )
        SELECT
            keys.cost_code_key,
            codes.canonical_description,
            coalesce(budget.current_budget, 0),
            coalesce(costs.actual_cost, 0) + coalesce(costs.adjustment, 0)
                AS adjusted_actual_cost,
            coalesce(costs.committed_cost, 0),
            coalesce(costs.forecast_remaining, 0),
            coalesce(costs.actual_cost, 0) + coalesce(costs.adjustment, 0)
                + coalesce(costs.forecast_remaining, 0) AS projected_cost,
            coalesce(costs.actual_cost, 0) + coalesce(costs.adjustment, 0)
                + coalesce(costs.forecast_remaining, 0)
                - coalesce(budget.current_budget, 0) AS projected_variance,
            coalesce(correspondence.confirmed_unbooked_cost, 0),
            coalesce(correspondence.potential_downside_cost, 0)
        FROM keys
        JOIN dim_cost_code AS codes USING (cost_code_key)
        LEFT JOIN budget USING (cost_code_key)
        LEFT JOIN costs USING (cost_code_key)
        LEFT JOIN correspondence USING (cost_code_key)
        ORDER BY abs(projected_variance) + coalesce(correspondence.potential_downside_cost, 0)
            DESC, keys.cost_code_key
        """,
        [job_id, job_id, job_id],
    ).fetchall()
    return [
        CostCodeDetail(
            cost_code=row[0],
            description=row[1],
            current_budget=_number(row[2]),
            adjusted_actual_cost=_number(row[3]),
            committed_cost=_number(row[4]),
            forecast_remaining=_number(row[5]),
            projected_cost=_number(row[6]),
            projected_variance=_number(row[7]),
            confirmed_unbooked_cost=_number(row[8]),
            potential_downside_cost=_number(row[9]),
        )
        for row in rows
    ]


def _exposure_buckets(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
) -> list[ExposureBucket]:
    rows = connection.execute(
        """
        SELECT exposure_category, count(*), coalesce(sum(amount), 0)
        FROM mart_correspondence_exposure
        WHERE job_id = ?
        GROUP BY exposure_category
        ORDER BY coalesce(sum(amount), 0) DESC, exposure_category
        """,
        [job_id],
    ).fetchall()
    return [
        ExposureBucket(category=row[0], event_count=row[1], amount=_number(row[2])) for row in rows
    ]


def _correspondence_events(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
) -> list[CorrespondenceEventDetail]:
    rows = connection.execute(
        """
        SELECT
            correspondence_event_key,
            doc_id,
            doc_type,
            event_index,
            exposure_category,
            event_type,
            scope,
            cost_code_key,
            cost_code_description,
            subcontractor_id,
            amount,
            booking_status,
            approval_status,
            schedule_impact_days,
            schedule_impact_type,
            evidence_text
        FROM mart_correspondence_exposure
        WHERE job_id = ?
        ORDER BY
            CASE exposure_category
                WHEN 'confirmed_unbooked_cost' THEN 1
                WHEN 'unbooked_contract_value' THEN 2
                WHEN 'pending_change_cost' THEN 3
                WHEN 'potential_cost' THEN 4
                WHEN 'budget_variance' THEN 5
                ELSE 6
            END,
            coalesce(amount, 0) DESC,
            doc_id,
            event_index
        """,
        [job_id],
    ).fetchall()
    return [
        CorrespondenceEventDetail(
            event_key=row[0],
            doc_id=row[1],
            doc_type=row[2],
            event_index=row[3],
            category=row[4],
            event_type=row[5],
            scope=row[6],
            cost_code=row[7],
            cost_code_description=row[8],
            subcontractor_id=row[9],
            amount=_optional_number(row[10]),
            booking_status=row[11],
            approval_status=row[12],
            schedule_impact_days=row[13],
            schedule_impact_type=row[14],
            evidence_text=row[15],
        )
        for row in rows
    ]


def _schedule(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
    summary: JobFinancialSummary,
) -> tuple[ScheduleSummary, list[ScheduleActivityDetail]]:
    aggregate = connection.execute(
        """
        SELECT
            count(*),
            count(*) FILTER (WHERE pct_complete < 1),
            avg(pct_complete),
            count(*) FILTER (WHERE is_actual_finish_before_start)
        FROM fact_schedule_activity
        WHERE job_key = ?
        """,
        [job_id],
    ).fetchone()
    rows = connection.execute(
        """
        SELECT
            activity_id,
            activity_name,
            baseline_start,
            baseline_finish,
            actual_start,
            actual_finish,
            pct_complete,
            baseline_duration_days,
            actual_duration_days,
            CASE
                WHEN actual_duration_days IS NOT NULL AND baseline_duration_days IS NOT NULL
                    THEN actual_duration_days - baseline_duration_days
            END AS duration_variance_days,
            is_actual_finish_before_start
        FROM fact_schedule_activity
        WHERE job_key = ?
        ORDER BY
            is_actual_finish_before_start DESC,
            coalesce(pct_complete, 0),
            abs(coalesce(actual_duration_days - baseline_duration_days, 0)) DESC,
            activity_id
        LIMIT 12
        """,
        [job_id],
    ).fetchall()
    schedule_summary = ScheduleSummary(
        activity_count=aggregate[0],
        incomplete_activity_count=aggregate[1],
        mean_activity_progress_pct=_optional_number(aggregate[2]),
        reversed_actual_activity_count=aggregate[3],
        schedule_correspondence_event_count=summary.schedule_event_count,
        maximum_reported_delay_days=summary.maximum_reported_delay_days,
    )
    activities = [
        ScheduleActivityDetail(
            activity_id=row[0],
            activity_name=row[1],
            baseline_start=_date(row[2]),
            baseline_finish=_date(row[3]),
            actual_start=_date(row[4]),
            actual_finish=_date(row[5]),
            pct_complete=_optional_number(row[6]),
            baseline_duration_days=row[7],
            actual_duration_days=row[8],
            duration_variance_days=row[9],
            has_reversed_actual_dates=row[10],
        )
        for row in rows
    ]
    return schedule_summary, activities


def _subcontractors(
    connection: duckdb.DuckDBPyConnection,
    job_id: str,
) -> list[SubcontractorJobExposure]:
    rows = connection.execute(
        """
        WITH ledger AS (
            SELECT
                subcontractor_key,
                sum(amount) FILTER (WHERE transaction_type = 'ACTUAL') AS actual_cost,
                sum(amount) FILTER (WHERE transaction_type = 'ADJUSTMENT') AS adjustment,
                sum(amount) FILTER (WHERE transaction_type = 'COMMITTED') AS committed_cost,
                sum(amount) FILTER (WHERE transaction_type = 'FORECAST') AS forecast_remaining
            FROM fact_cost_transaction
            WHERE job_key = ?
            GROUP BY subcontractor_key
        ),
        correspondence AS (
            SELECT
                subcontractor_key,
                count(*) AS event_count,
                sum(amount) FILTER (WHERE exposure_category = 'confirmed_unbooked_cost')
                    AS confirmed_unbooked_cost,
                sum(potential_downside_amount) AS potential_downside_cost
            FROM mart_correspondence_exposure
            WHERE job_id = ?
            GROUP BY subcontractor_key
        ),
        keys AS (
            SELECT subcontractor_key FROM ledger
            UNION
            SELECT subcontractor_key FROM correspondence
        )
        SELECT
            keys.subcontractor_key,
            subcontractors.display_name,
            coalesce(ledger.actual_cost, 0),
            coalesce(ledger.adjustment, 0),
            coalesce(ledger.committed_cost, 0),
            coalesce(ledger.forecast_remaining, 0),
            coalesce(ledger.actual_cost, 0) + coalesce(ledger.adjustment, 0)
                + coalesce(ledger.forecast_remaining, 0) AS projected_cost_exposure,
            coalesce(correspondence.event_count, 0),
            coalesce(correspondence.confirmed_unbooked_cost, 0),
            coalesce(correspondence.potential_downside_cost, 0)
        FROM keys
        JOIN dim_subcontractor AS subcontractors USING (subcontractor_key)
        LEFT JOIN ledger USING (subcontractor_key)
        LEFT JOIN correspondence USING (subcontractor_key)
        ORDER BY projected_cost_exposure + coalesce(correspondence.potential_downside_cost, 0)
            DESC, keys.subcontractor_key
        """,
        [job_id, job_id],
    ).fetchall()
    return [
        SubcontractorJobExposure(
            subcontractor_id=row[0],
            display_name=row[1],
            actual_cost=_number(row[2]),
            adjustment=_number(row[3]),
            committed_cost=_number(row[4]),
            forecast_remaining=_number(row[5]),
            projected_cost_exposure=_number(row[6]),
            correspondence_event_count=row[7],
            confirmed_unbooked_cost=_number(row[8]),
            potential_downside_cost=_number(row[9]),
        )
        for row in rows
    ]


def load_job_detail(settings: Settings, job_id: str) -> JobDetail:
    if not settings.database_path.is_file():
        raise DashboardDataError(
            f"DuckDB database does not exist; run `flint build`: {settings.database_path}"
        )

    canonical_job_id = job_id.strip().upper()
    try:
        connection = duckdb.connect(str(settings.database_path), read_only=True)
        _validate_tables(connection)
        summary = _job_summary(connection, canonical_job_id)
        schedule_summary, schedule_activities = _schedule(
            connection,
            canonical_job_id,
            summary,
        )
        return JobDetail(
            summary=summary,
            scenarios=_job_scenarios(connection, canonical_job_id),
            monthly_costs=_monthly_costs(connection, canonical_job_id),
            cost_codes=_cost_codes(connection, canonical_job_id),
            exposure_buckets=_exposure_buckets(connection, canonical_job_id),
            correspondence_events=_correspondence_events(connection, canonical_job_id),
            schedule_summary=schedule_summary,
            schedule_activities=schedule_activities,
            subcontractors=_subcontractors(connection, canonical_job_id),
        )
    except JobNotFoundError:
        raise
    except duckdb.Error as exc:
        raise DashboardDataError(f"could not query job detail: {exc}") from exc
    finally:
        if "connection" in locals():
            connection.close()


def _portfolio_headline(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[InsightsHeadline, list[RiskRankingInsight]]:
    rows = connection.execute(
        """
        SELECT
            dashboard.job_id,
            dashboard.division,
            dashboard.current_cost_budget,
            dashboard.base_projected_final_cost,
            dashboard.base_projected_cost_variance,
            dashboard.base_projected_margin,
            dashboard.confirmed_adjusted_margin,
            dashboard.downside_scenario_margin,
            dashboard.confirmed_unbooked_cost,
            dashboard.potential_downside_cost,
            progress.cost_progress_status
        FROM mart_job_dashboard AS dashboard
        JOIN mart_cost_vs_progress AS progress USING (job_key)
        ORDER BY dashboard.job_id
        """
    ).fetchall()
    ranked = sorted(rows, key=lambda row: max(_number(row[4]), 0), reverse=True)
    positive_variance = sum(max(_number(row[4]), 0) for row in ranked)
    cumulative = 0.0
    ranking: list[RiskRankingInsight] = []
    for rank, row in enumerate(ranked, start=1):
        variance = max(_number(row[4]), 0)
        cumulative += variance
        ranking.append(
            RiskRankingInsight(
                rank=rank,
                job_id=row[0],
                division=row[1],
                projected_cost_variance=variance,
                potential_downside_cost=_number(row[9]),
                cumulative_pct=cumulative / positive_variance if positive_variance else 0,
            )
        )

    jobs_to_eighty = next(
        (point.rank for point in ranking if point.cumulative_pct >= 0.8),
        len(ranking),
    )
    headline = InsightsHeadline(
        job_count=len(rows),
        current_cost_budget=sum(_number(row[2]) for row in rows),
        projected_final_cost=sum(_number(row[3]) for row in rows),
        net_projected_cost_variance=sum(_number(row[4]) for row in rows),
        positive_cost_variance=positive_variance,
        base_projected_margin=sum(_number(row[5]) for row in rows),
        confirmed_adjusted_margin=sum(_number(row[6]) for row in rows),
        downside_scenario_margin=sum(_number(row[7]) for row in rows),
        confirmed_unbooked_cost=sum(_number(row[8]) for row in rows),
        potential_downside_cost=sum(_number(row[9]) for row in rows),
        critical_cost_progress_jobs=sum(row[10] == "critical" for row in rows),
        jobs_to_eighty_pct=jobs_to_eighty,
        top_five_variance_share=(
            sum(max(_number(row[4]), 0) for row in ranked[:5]) / positive_variance
            if positive_variance
            else 0
        ),
    )
    return headline, ranking


def _division_insights(connection: duckdb.DuckDBPyConnection) -> list[DivisionInsight]:
    rows = connection.execute(
        """
        SELECT
            division,
            count(*),
            sum(current_cost_budget),
            sum(base_projected_final_cost),
            sum(base_projected_cost_variance),
            sum(confirmed_unbooked_cost),
            sum(potential_downside_cost),
            sum(downside_scenario_margin)
        FROM mart_job_dashboard
        GROUP BY division
        ORDER BY division
        """
    ).fetchall()
    return [
        DivisionInsight(
            division=row[0],
            job_count=row[1],
            current_cost_budget=_number(row[2]),
            projected_final_cost=_number(row[3]),
            projected_cost_variance=_number(row[4]),
            confirmed_unbooked_cost=_number(row[5]),
            potential_downside_cost=_number(row[6]),
            downside_scenario_margin=_number(row[7]),
        )
        for row in rows
    ]


def _cost_progress_insights(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[list[StatusCount], list[CostProgressInsight]]:
    status_rows = connection.execute(
        """
        SELECT cost_progress_status, count(*)
        FROM mart_cost_vs_progress
        GROUP BY cost_progress_status
        ORDER BY count(*) DESC, cost_progress_status
        """
    ).fetchall()
    job_rows = connection.execute(
        """
        SELECT
            job_id,
            division,
            reported_progress_pct,
            cost_spent_pct,
            cost_progress_variance,
            cost_progress_status
        FROM mart_cost_vs_progress
        ORDER BY abs(coalesce(cost_progress_variance, 0)) DESC, job_id
        """
    ).fetchall()
    return (
        [StatusCount(status=row[0], job_count=row[1]) for row in status_rows],
        [
            CostProgressInsight(
                job_id=row[0],
                division=row[1],
                reported_progress_pct=_optional_number(row[2]),
                cost_spent_pct=_optional_number(row[3]),
                cost_progress_variance=_optional_number(row[4]),
                status=row[5],
            )
            for row in job_rows
        ],
    )


def _equipment_insights(connection: duckdb.DuckDBPyConnection) -> list[EquipmentInsight]:
    rows = connection.execute(
        """
        SELECT
            division,
            ownership,
            assignment_count,
            job_count,
            total_equipment_cost,
            total_production_units,
            weighted_cost_per_production_unit,
            average_utilization
        FROM mart_equipment_economics
        ORDER BY division, ownership
        """
    ).fetchall()
    return [
        EquipmentInsight(
            division=row[0],
            ownership=row[1],
            assignment_count=row[2],
            job_count=row[3],
            total_equipment_cost=_number(row[4]),
            production_units=_number(row[5]),
            cost_per_unit=_optional_number(row[6]),
            average_utilization=_optional_number(row[7]),
        )
        for row in rows
    ]


def _cross_division_insights(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[int, int, list[CostCodeRiskInsight], list[SubcontractorRiskInsight]]:
    cross_cost_codes = connection.execute(
        """
        SELECT count(*) FROM (
            SELECT costs.cost_code_key
            FROM fact_cost_transaction AS costs
            JOIN dim_job AS jobs USING (job_key)
            WHERE NOT jobs.is_unknown
            GROUP BY costs.cost_code_key
            HAVING count(DISTINCT jobs.division) > 1
        )
        """
    ).fetchone()[0]
    cross_subcontractors = connection.execute(
        """
        SELECT count(*) FROM mart_subcontractor_combined_exposure
        WHERE is_cross_division
        """
    ).fetchone()[0]
    cost_code_rows = connection.execute(
        """
        WITH correspondence AS (
            SELECT
                cost_code_key,
                sum(coalesce(pending_change_cost, 0) + coalesce(potential_cost, 0))
                    AS correspondence_downside
            FROM mart_correspondence_cost_code_exposure
            GROUP BY cost_code_key
        )
        SELECT
            costs.cost_code_key,
            costs.canonical_description,
            costs.job_count,
            costs.projected_cost_variance,
            coalesce(correspondence.correspondence_downside, 0)
        FROM mart_cost_code_exposure AS costs
        LEFT JOIN correspondence USING (cost_code_key)
        WHERE NOT costs.is_unknown
        ORDER BY greatest(coalesce(costs.projected_cost_variance, 0), 0)
            + coalesce(correspondence.correspondence_downside, 0) DESC,
            costs.cost_code_key
        """
    ).fetchall()
    subcontractor_rows = connection.execute(
        """
        SELECT
            subcontractor_id,
            greatest(ledger_division_count, correspondence_division_count),
            ledger_projected_cost_exposure,
            confirmed_unbooked_cost,
            pending_change_cost + potential_cost AS potential_downside_cost
        FROM mart_subcontractor_combined_exposure
        WHERE is_cross_division
        ORDER BY ledger_projected_cost_exposure + pending_change_cost + potential_cost DESC,
            subcontractor_id
        """
    ).fetchall()
    return (
        cross_cost_codes,
        cross_subcontractors,
        [
            CostCodeRiskInsight(
                cost_code=row[0],
                description=row[1],
                job_count=row[2],
                projected_cost_variance=_number(row[3]),
                correspondence_downside=_number(row[4]),
            )
            for row in cost_code_rows
        ],
        [
            SubcontractorRiskInsight(
                subcontractor_id=row[0],
                division_count=row[1],
                ledger_projected_cost=_number(row[2]),
                confirmed_unbooked_cost=_number(row[3]),
                potential_downside_cost=_number(row[4]),
            )
            for row in subcontractor_rows
        ],
    )


def _correspondence_insights(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[list[ExposureBucket], list[CorrespondenceJobInsight]]:
    category_rows = connection.execute(
        """
        SELECT exposure_category, count(*), coalesce(sum(amount), 0)
        FROM mart_correspondence_exposure
        GROUP BY exposure_category
        ORDER BY coalesce(sum(amount), 0) DESC, exposure_category
        """
    ).fetchall()
    job_rows = connection.execute(
        """
        SELECT
            job_id,
            division,
            correspondence_event_count,
            confirmed_unbooked_cost,
            unbooked_contract_value,
            potential_downside_cost,
            reported_budget_variance,
            maximum_reported_delay_days
        FROM mart_job_correspondence_exposure
        WHERE correspondence_event_count > 0
        ORDER BY potential_downside_cost + confirmed_unbooked_cost DESC, job_id
        """
    ).fetchall()
    return (
        [
            ExposureBucket(category=row[0], event_count=row[1], amount=_number(row[2]))
            for row in category_rows
        ],
        [
            CorrespondenceJobInsight(
                job_id=row[0],
                division=row[1],
                event_count=row[2],
                confirmed_unbooked_cost=_number(row[3]),
                unbooked_contract_value=_number(row[4]),
                potential_downside_cost=_number(row[5]),
                reported_budget_variance=_number(row[6]),
                maximum_reported_delay_days=row[7],
            )
            for row in job_rows
        ],
    )


def _quality_insights(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[list[QualityInsight], list[ReconciliationInsight], int]:
    quality_rows = connection.execute(
        """
        SELECT severity, count(*)
        FROM dq_issues
        GROUP BY severity
        ORDER BY CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END
        """
    ).fetchall()
    reconciliation_rows = connection.execute(
        """
        SELECT 'Core model', count(*) FILTER (WHERE passed), count(*)
        FROM model_reconciliation
        UNION ALL
        SELECT 'Correspondence', count(*) FILTER (WHERE passed), count(*)
        FROM model_correspondence_reconciliation
        UNION ALL
        SELECT 'Analysis marts', count(*) FILTER (WHERE passed), count(*)
        FROM model_analysis_reconciliation
        """
    ).fetchall()
    analysis_issues = connection.execute("SELECT count(*) FROM analysis_dq_issues").fetchone()[0]
    return (
        [QualityInsight(severity=row[0], issue_count=row[1]) for row in quality_rows],
        [
            ReconciliationInsight(layer=row[0], passed_checks=row[1], total_checks=row[2])
            for row in reconciliation_rows
        ],
        analysis_issues,
    )


def _portfolio_anomalies(connection: duckdb.DuckDBPyConnection) -> PortfolioAnomalies:
    row = connection.execute(
        """
        WITH ledger AS (
            SELECT
                count(*) FILTER (WHERE is_unmapped_cost_code)
                    AS unmapped_ledger_posting_count,
                list_sort(list(DISTINCT erp_cost_code) FILTER (
                    WHERE is_unmapped_cost_code AND erp_cost_code IS NOT NULL
                )) AS unmapped_ledger_cost_codes,
                coalesce(sum(duplicate_source_count - 1) FILTER (
                    WHERE was_deduplicated
                ), 0) AS duplicate_ledger_rows_excluded,
                coalesce(sum(amount * (duplicate_source_count - 1)) FILTER (
                    WHERE was_deduplicated
                ), 0) AS duplicate_ledger_amount_excluded,
                count(*) FILTER (WHERE transaction_type = 'ADJUSTMENT')
                    AS adjustment_transaction_count,
                coalesce(sum(amount) FILTER (
                    WHERE transaction_type = 'ADJUSTMENT'
                ), 0) AS net_adjustment_amount,
                count(*) FILTER (WHERE is_missing_job_id)
                    AS missing_job_id_posting_count
            FROM fact_cost_transaction
        ),
        jobs AS (
            SELECT
                list(job_id ORDER BY job_id) FILTER (WHERE is_missing_estimate)
                    AS missing_budget_job_ids,
                count(*) FILTER (WHERE estimate_drift_pct >= 0.10)
                    AS estimate_drift_job_count
            FROM mart_job_financial
        ),
        schedule AS (
            SELECT
                count(*) FILTER (WHERE is_actual_finish_before_start)
                    AS reversed_schedule_activity_count,
                count(DISTINCT job_key) FILTER (
                    WHERE is_actual_finish_before_start
                ) AS reversed_schedule_job_count
            FROM fact_schedule_activity
        )
        SELECT
            ledger.unmapped_ledger_posting_count,
            ledger.unmapped_ledger_cost_codes,
            jobs.missing_budget_job_ids,
            ledger.duplicate_ledger_rows_excluded,
            ledger.duplicate_ledger_amount_excluded,
            ledger.adjustment_transaction_count,
            ledger.net_adjustment_amount,
            jobs.estimate_drift_job_count,
            schedule.reversed_schedule_activity_count,
            schedule.reversed_schedule_job_count,
            ledger.missing_job_id_posting_count
        FROM ledger, jobs, schedule
        """
    ).fetchone()
    return PortfolioAnomalies(
        unmapped_ledger_posting_count=row[0],
        unmapped_ledger_cost_codes=list(row[1] or []),
        missing_budget_job_ids=list(row[2] or []),
        duplicate_ledger_rows_excluded=row[3],
        duplicate_ledger_amount_excluded=_number(row[4]),
        adjustment_transaction_count=row[5],
        net_adjustment_amount=_number(row[6]),
        estimate_drift_job_count=row[7],
        reversed_schedule_activity_count=row[8],
        reversed_schedule_job_count=row[9],
        missing_job_id_posting_count=row[10],
    )


def load_portfolio_insights(settings: Settings) -> PortfolioInsights:
    if not settings.database_path.is_file():
        raise DashboardDataError(
            f"DuckDB database does not exist; run `flint build`: {settings.database_path}"
        )

    try:
        connection = duckdb.connect(str(settings.database_path), read_only=True)
        _validate_tables(connection)
        headline, ranking = _portfolio_headline(connection)
        progress_statuses, progress_jobs = _cost_progress_insights(connection)
        (
            cross_cost_codes,
            cross_subcontractors,
            cost_code_risks,
            subcontractor_risks,
        ) = _cross_division_insights(connection)
        correspondence_categories, correspondence_jobs = _correspondence_insights(connection)
        quality, reconciliations, analysis_issues = _quality_insights(connection)
        return PortfolioInsights(
            headline=headline,
            divisions=_division_insights(connection),
            risk_ranking=ranking,
            progress_statuses=progress_statuses,
            cost_progress_jobs=progress_jobs,
            equipment=_equipment_insights(connection),
            cross_division_cost_code_count=cross_cost_codes,
            cross_division_subcontractor_count=cross_subcontractors,
            cost_code_risks=cost_code_risks,
            subcontractor_risks=subcontractor_risks,
            correspondence_categories=correspondence_categories,
            correspondence_jobs=correspondence_jobs,
            quality_issues=quality,
            reconciliations=reconciliations,
            analysis_quality_issue_count=analysis_issues,
            anomalies=_portfolio_anomalies(connection),
        )
    except duckdb.Error as exc:
        raise DashboardDataError(f"could not query portfolio insights: {exc}") from exc
    finally:
        if "connection" in locals():
            connection.close()


def _equipment_where(filters: EquipmentFilters) -> tuple[str, list[str]]:
    conditions = ["equipment.is_analysis_eligible", "NOT jobs.is_unknown"]
    parameters: list[str] = []
    fields = (
        ("jobs.division", filters.division),
        ("equipment.ownership", filters.ownership),
        ("equipment.equipment_type", filters.equipment_type),
        ("jobs.job_id", filters.job_id),
    )
    for field, value in fields:
        if value:
            conditions.append(f"{field} = ?")
            parameters.append(value)
    return "WHERE " + " AND ".join(conditions), parameters


def _equipment_options(connection: duckdb.DuckDBPyConnection) -> EquipmentFilterOptions:
    def values(column: str) -> list[str]:
        rows = connection.execute(
            f"""
            SELECT DISTINCT {column}
            FROM fact_equipment_usage AS equipment
            JOIN dim_job AS jobs USING (job_key)
            WHERE equipment.is_analysis_eligible
              AND NOT jobs.is_unknown
              AND {column} IS NOT NULL
            ORDER BY {column}
            """
        ).fetchall()
        return [row[0] for row in rows]

    return EquipmentFilterOptions(
        divisions=values("jobs.division"),
        ownership_types=values("equipment.ownership"),
        equipment_types=values("equipment.equipment_type"),
        jobs=values("jobs.job_id"),
    )


def _equipment_kpis(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> EquipmentKpis:
    row = connection.execute(
        f"""
        SELECT
            count(*),
            count(DISTINCT jobs.job_id),
            coalesce(sum(equipment.total_equipment_cost), 0),
            coalesce(sum(equipment.production_units), 0),
            sum(equipment.total_equipment_cost)
                / nullif(sum(equipment.production_units), 0),
            avg(equipment.utilization),
            sum(equipment.total_equipment_cost) FILTER (
                WHERE equipment.ownership = 'Owned'
            ) / nullif(sum(equipment.production_units) FILTER (
                WHERE equipment.ownership = 'Owned'
            ), 0),
            sum(equipment.total_equipment_cost) FILTER (
                WHERE equipment.ownership = 'Rented'
            ) / nullif(sum(equipment.production_units) FILTER (
                WHERE equipment.ownership = 'Rented'
            ), 0)
        FROM fact_equipment_usage AS equipment
        JOIN dim_job AS jobs USING (job_key)
        {where_clause}
        """,
        parameters,
    ).fetchone()
    owned_cost = _optional_number(row[6])
    rented_cost = _optional_number(row[7])
    premium = (
        rented_cost / owned_cost - 1
        if owned_cost not in (None, 0) and rented_cost is not None
        else None
    )
    return EquipmentKpis(
        assignment_count=row[0],
        job_count=row[1],
        total_equipment_cost=_number(row[2]),
        production_units=_number(row[3]),
        weighted_cost_per_unit=_optional_number(row[4]),
        average_utilization=_optional_number(row[5]),
        owned_cost_per_unit=owned_cost,
        rented_cost_per_unit=rented_cost,
        rental_premium_pct=premium,
    )


def _equipment_breakdown(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> list[EquipmentBreakdown]:
    rows = connection.execute(
        f"""
        SELECT
            jobs.division,
            equipment.ownership,
            count(*),
            count(DISTINCT jobs.job_id),
            sum(equipment.total_equipment_cost),
            sum(equipment.production_units),
            sum(equipment.total_equipment_cost)
                / nullif(sum(equipment.production_units), 0),
            avg(equipment.utilization)
        FROM fact_equipment_usage AS equipment
        JOIN dim_job AS jobs USING (job_key)
        {where_clause}
        GROUP BY jobs.division, equipment.ownership
        ORDER BY jobs.division, equipment.ownership
        """,
        parameters,
    ).fetchall()
    return [
        EquipmentBreakdown(
            division=row[0],
            ownership=row[1],
            assignment_count=row[2],
            job_count=row[3],
            total_equipment_cost=_number(row[4]),
            production_units=_number(row[5]),
            cost_per_unit=_optional_number(row[6]),
            average_utilization=_optional_number(row[7]),
        )
        for row in rows
    ]


def _equipment_type_summary(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> list[EquipmentTypeSummary]:
    rows = connection.execute(
        f"""
        SELECT
            equipment.equipment_type,
            equipment.ownership,
            count(*),
            count(DISTINCT jobs.job_id),
            sum(equipment.total_equipment_cost),
            sum(equipment.production_units),
            sum(equipment.total_equipment_cost)
                / nullif(sum(equipment.production_units), 0),
            avg(equipment.utilization)
        FROM fact_equipment_usage AS equipment
        JOIN dim_job AS jobs USING (job_key)
        {where_clause}
        GROUP BY equipment.equipment_type, equipment.ownership
        ORDER BY sum(equipment.total_equipment_cost) DESC,
            equipment.equipment_type, equipment.ownership
        """,
        parameters,
    ).fetchall()
    return [
        EquipmentTypeSummary(
            equipment_type=row[0],
            ownership=row[1],
            assignment_count=row[2],
            job_count=row[3],
            total_equipment_cost=_number(row[4]),
            production_units=_number(row[5]),
            cost_per_unit=_optional_number(row[6]),
            average_utilization=_optional_number(row[7]),
        )
        for row in rows
    ]


def _equipment_assignments(
    connection: duckdb.DuckDBPyConnection,
    where_clause: str,
    parameters: list[str],
) -> list[EquipmentAssignment]:
    rows = connection.execute(
        f"""
        SELECT
            equipment.equipment_usage_key,
            jobs.job_id,
            jobs.division,
            equipment.equipment_type,
            equipment.ownership,
            equipment.monthly_rate,
            equipment.months_on_job,
            equipment.utilization,
            equipment.production_units,
            equipment.total_equipment_cost,
            equipment.cost_per_production_unit
        FROM fact_equipment_usage AS equipment
        JOIN dim_job AS jobs USING (job_key)
        {where_clause}
        ORDER BY equipment.total_equipment_cost DESC,
            jobs.job_id, equipment.equipment_type
        """,
        parameters,
    ).fetchall()
    return [
        EquipmentAssignment(
            assignment_key=row[0],
            job_id=row[1],
            division=row[2],
            equipment_type=row[3],
            ownership=row[4],
            monthly_rate=_number(row[5]),
            months_on_job=_number(row[6]),
            utilization=_optional_number(row[7]),
            production_units=_number(row[8]),
            total_equipment_cost=_number(row[9]),
            cost_per_unit=_optional_number(row[10]),
        )
        for row in rows
    ]


def load_equipment_dashboard(
    settings: Settings,
    filters: EquipmentFilters | None = None,
) -> EquipmentDashboard:
    if not settings.database_path.is_file():
        raise DashboardDataError(
            f"DuckDB database does not exist; run `flint build`: {settings.database_path}"
        )

    applied = filters or EquipmentFilters()
    where_clause, parameters = _equipment_where(applied)
    try:
        connection = duckdb.connect(str(settings.database_path), read_only=True)
        _validate_tables(connection)
        return EquipmentDashboard(
            filters=_equipment_options(connection),
            applied_filters=applied,
            kpis=_equipment_kpis(connection, where_clause, parameters),
            division_comparison=_equipment_breakdown(connection, where_clause, parameters),
            type_summary=_equipment_type_summary(connection, where_clause, parameters),
            assignments=_equipment_assignments(connection, where_clause, parameters),
        )
    except duckdb.Error as exc:
        raise DashboardDataError(f"could not query equipment dashboard: {exc}") from exc
    finally:
        if "connection" in locals():
            connection.close()
