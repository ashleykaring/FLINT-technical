from __future__ import annotations

from pipeline.api.repository import load_portfolio_dashboard
from pipeline.api.schemas import DashboardFilters
from pipeline.config import Settings


def test_portfolio_dashboard_is_typed_filterable_and_complete(
    analysis_settings: Settings,
) -> None:
    dashboard = load_portfolio_dashboard(analysis_settings)

    assert dashboard.kpis.jobs_in_view == 42
    assert len(dashboard.jobs) == 42
    assert len(dashboard.pareto) == 42
    assert [scenario.scenario for scenario in dashboard.scenarios] == [
        "Base forecast",
        "Confirmed adjusted",
        "Downside",
    ]
    assert dashboard.pareto[-1].cumulative_pct == 1
    assert sum(item.job_count for item in dashboard.status_counts) == 42

    building = load_portfolio_dashboard(
        analysis_settings,
        DashboardFilters(division="Building"),
    )
    assert building.kpis.jobs_in_view == 24
    assert all(job.division == "Building" for job in building.jobs)
    assert sum(item.job_count for item in building.status_counts) == 24

    selected_status = dashboard.filters.progress_statuses[0]
    status_view = load_portfolio_dashboard(
        analysis_settings,
        DashboardFilters(progress_status=selected_status),
    )
    assert status_view.jobs
    assert all(job.progress_status == selected_status for job in status_view.jobs)
