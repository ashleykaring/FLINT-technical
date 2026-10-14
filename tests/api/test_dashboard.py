from __future__ import annotations

import pytest

from pipeline.api.repository import (
    JobNotFoundError,
    load_equipment_dashboard,
    load_job_detail,
    load_portfolio_dashboard,
    load_portfolio_insights,
)
from pipeline.api.schemas import DashboardFilters, EquipmentFilters
from pipeline.config import Settings


def test_portfolio_dashboard_is_typed_filterable_and_complete(
    analysis_settings: Settings,
) -> None:
    dashboard = load_portfolio_dashboard(analysis_settings)

    assert dashboard.kpis.jobs_in_view == 42
    assert dashboard.kpis.actual_cost_to_date == pytest.approx(1_214_932_341.88)
    assert len(dashboard.jobs) == 42
    assert len(dashboard.pareto) == 42
    assert dashboard.budget_outlook.total_jobs == 42
    assert dashboard.budget_outlook.currently_over_count == 23
    assert dashboard.budget_outlook.forecast_only_count == 14
    assert dashboard.budget_outlook.within_forecast_count == 3
    assert dashboard.budget_outlook.missing_budget_count == 2
    assert dashboard.budget_outlook.current_gross_overrun == pytest.approx(79_393_342.23)
    assert dashboard.budget_outlook.projected_gross_overrun == pytest.approx(401_805_834.49)
    assert all(
        job.budget_outlook in {"already_over", "forecast_over", "within_forecast", "missing_budget"}
        for job in dashboard.jobs
    )
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


def test_job_detail_combines_financial_delivery_and_correspondence_data(
    analysis_settings: Settings,
) -> None:
    detail = load_job_detail(analysis_settings, "b2100")

    assert detail.summary.job_id == "B2100"
    assert detail.summary.confirmed_unbooked_cost == 100
    assert detail.summary.potential_downside_cost == 300
    assert len(detail.monthly_costs) == 24
    assert detail.cost_codes
    assert {event.doc_id for event in detail.correspondence_events} == {
        "CO-1",
        "CO-2",
        "RFI-1",
        "LOG-1",
    }
    assert detail.schedule_summary.activity_count > 0
    assert detail.schedule_activities
    assert detail.subcontractors
    assert [scenario.scenario for scenario in detail.scenarios] == [
        "Base forecast",
        "Confirmed adjusted",
        "Downside",
    ]

    with pytest.raises(JobNotFoundError, match="job does not exist"):
        load_job_detail(analysis_settings, "NOT-A-JOB")


def test_portfolio_insights_reconcile_business_questions(
    analysis_settings: Settings,
) -> None:
    insights = load_portfolio_insights(analysis_settings)

    assert insights.headline.job_count == 42
    assert insights.headline.jobs_to_eighty_pct > 0
    assert insights.headline.top_five_variance_share > 0
    assert {item.division for item in insights.divisions} == {"Building", "Civil"}
    assert sum(item.job_count for item in insights.progress_statuses) == 42
    assert len(insights.equipment) == 4
    assert insights.cross_division_cost_code_count > 0
    assert insights.cross_division_subcontractor_count > 0
    assert sum(item.event_count for item in insights.correspondence_categories) == 5
    assert insights.analysis_quality_issue_count == 0
    assert all(item.passed_checks == item.total_checks for item in insights.reconciliations)


def test_equipment_dashboard_is_filterable_and_preserves_assignment_grain(
    analysis_settings: Settings,
) -> None:
    equipment = load_equipment_dashboard(analysis_settings)

    assert equipment.kpis.assignment_count == 215
    assert equipment.kpis.job_count == 42
    assert equipment.kpis.rental_premium_pct == pytest.approx(0.3338, abs=0.0001)
    assert len(equipment.division_comparison) == 4
    assert len(equipment.assignments) == 215
    assert "Excavator" in {item.equipment_type for item in equipment.type_summary}

    civil = load_equipment_dashboard(
        analysis_settings,
        EquipmentFilters(division="Civil"),
    )
    assert civil.kpis.assignment_count == 87
    assert all(item.division == "Civil" for item in civil.assignments)
