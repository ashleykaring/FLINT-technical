from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DashboardFilters(BaseModel):
    division: str | None = None
    contract_type: str | None = None
    project_manager_id: str | None = None
    progress_status: str | None = None


class FilterOptions(BaseModel):
    divisions: list[str]
    contract_types: list[str]
    project_managers: list[str]
    progress_statuses: list[str]


class PortfolioKpis(BaseModel):
    current_cost_budget: float
    actual_cost_to_date: float
    projected_final_cost: float
    projected_cost_variance: float
    confirmed_unbooked_cost: float
    potential_downside_cost: float
    jobs_in_view: int
    jobs_requiring_attention: int


class BudgetOutlookSummary(BaseModel):
    total_jobs: int
    currently_over_count: int
    forecast_only_count: int
    within_forecast_count: int
    missing_budget_count: int
    current_gross_overrun: float
    projected_gross_overrun: float
    forecast_only_exposure: float


class ScenarioSummary(BaseModel):
    scenario: str
    contract_value_proxy: float
    projected_final_cost: float
    projected_margin: float
    change_from_base: float


class StatusCount(BaseModel):
    status: str
    job_count: int


class JobSummary(BaseModel):
    job_id: str
    division: str
    contract_type: str
    project_manager_id: str
    current_cost_budget: float
    projected_final_cost: float
    projected_cost_variance: float
    reported_progress_pct: float | None
    cost_spent_pct: float | None
    cost_progress_variance: float | None
    confirmed_unbooked_cost: float
    potential_downside_cost: float
    maximum_reported_delay_days: int | None
    progress_status: str
    combined_risk_level: str
    risk_reasons: str
    adjusted_actual_cost: float
    budget_outlook: str


class ParetoPoint(BaseModel):
    rank: int
    job_id: str
    exposure: float
    cumulative_pct: float


class PortfolioDashboard(BaseModel):
    filters: FilterOptions
    applied_filters: DashboardFilters
    kpis: PortfolioKpis
    budget_outlook: BudgetOutlookSummary
    scenarios: list[ScenarioSummary]
    status_counts: list[StatusCount]
    jobs: list[JobSummary]
    pareto: list[ParetoPoint]


class JobFinancialSummary(BaseModel):
    job_id: str
    division: str
    contract_type: str
    project_manager_id: str
    start_date: str | None
    planned_days: int | None
    reported_progress_pct: float | None
    cost_spent_pct: float | None
    progress_status: str
    combined_risk_level: str
    risk_reasons: str
    contract_value_proxy: float
    current_cost_budget: float
    adjusted_actual_cost: float
    committed_cost: float
    forecast_remaining: float
    projected_final_cost: float
    projected_cost_variance: float
    projected_margin: float
    confirmed_unbooked_cost: float
    unbooked_contract_value: float
    potential_downside_cost: float
    reported_budget_variance: float
    unquantified_backcharge_count: int
    schedule_event_count: int
    maximum_reported_delay_days: int | None


class MonthlyCostPoint(BaseModel):
    period: str
    actual_cost: float
    adjustment: float
    committed_cost: float
    forecast_remaining: float
    adjusted_actual_cost: float
    cumulative_adjusted_actual_cost: float


class CostCodeDetail(BaseModel):
    cost_code: str
    description: str
    current_budget: float
    adjusted_actual_cost: float
    committed_cost: float
    forecast_remaining: float
    projected_cost: float
    projected_variance: float
    confirmed_unbooked_cost: float
    potential_downside_cost: float


class ExposureBucket(BaseModel):
    category: str
    event_count: int
    amount: float


class CorrespondenceEventDetail(BaseModel):
    event_key: str
    doc_id: str
    doc_type: str
    event_index: int
    category: str
    event_type: str
    scope: str | None
    cost_code: str | None
    cost_code_description: str | None
    subcontractor_id: str | None
    amount: float | None
    booking_status: str
    approval_status: str
    schedule_impact_days: int | None
    schedule_impact_type: str
    evidence_text: str


class ScheduleSummary(BaseModel):
    activity_count: int
    incomplete_activity_count: int
    mean_activity_progress_pct: float | None
    reversed_actual_activity_count: int
    schedule_correspondence_event_count: int
    maximum_reported_delay_days: int | None


class ScheduleActivityDetail(BaseModel):
    activity_id: str
    activity_name: str
    baseline_start: str | None
    baseline_finish: str | None
    actual_start: str | None
    actual_finish: str | None
    pct_complete: float | None
    baseline_duration_days: int | None
    actual_duration_days: int | None
    duration_variance_days: int | None
    has_reversed_actual_dates: bool


class SubcontractorJobExposure(BaseModel):
    subcontractor_id: str
    display_name: str
    actual_cost: float
    adjustment: float
    committed_cost: float
    forecast_remaining: float
    projected_cost_exposure: float
    correspondence_event_count: int
    confirmed_unbooked_cost: float
    potential_downside_cost: float


class JobDetail(BaseModel):
    summary: JobFinancialSummary
    scenarios: list[ScenarioSummary]
    monthly_costs: list[MonthlyCostPoint]
    cost_codes: list[CostCodeDetail]
    exposure_buckets: list[ExposureBucket]
    correspondence_events: list[CorrespondenceEventDetail]
    schedule_summary: ScheduleSummary
    schedule_activities: list[ScheduleActivityDetail]
    subcontractors: list[SubcontractorJobExposure]


class JobQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class JobAnswerFact(BaseModel):
    statement: str
    source_section: Literal[
        "FINANCIAL",
        "COST_CODES",
        "SCHEDULE",
        "EQUIPMENT",
        "CORRESPONDENCE",
        "SUBCONTRACTORS",
    ]


class JobQuestionResponse(BaseModel):
    answer: str
    supporting_facts: list[JobAnswerFact]
    caveat: str | None = None


class InsightsHeadline(BaseModel):
    job_count: int
    current_cost_budget: float
    projected_final_cost: float
    net_projected_cost_variance: float
    positive_cost_variance: float
    base_projected_margin: float
    confirmed_adjusted_margin: float
    downside_scenario_margin: float
    confirmed_unbooked_cost: float
    potential_downside_cost: float
    critical_cost_progress_jobs: int
    jobs_to_eighty_pct: int
    top_five_variance_share: float


class DivisionInsight(BaseModel):
    division: str
    job_count: int
    current_cost_budget: float
    projected_final_cost: float
    projected_cost_variance: float
    confirmed_unbooked_cost: float
    potential_downside_cost: float
    downside_scenario_margin: float


class RiskRankingInsight(BaseModel):
    rank: int
    job_id: str
    division: str
    projected_cost_variance: float
    potential_downside_cost: float
    cumulative_pct: float


class CostProgressInsight(BaseModel):
    job_id: str
    division: str
    reported_progress_pct: float | None
    cost_spent_pct: float | None
    cost_progress_variance: float | None
    status: str


class EquipmentInsight(BaseModel):
    division: str
    ownership: str
    assignment_count: int
    job_count: int
    total_equipment_cost: float
    production_units: float
    cost_per_unit: float | None
    average_utilization: float | None


class CostCodeRiskInsight(BaseModel):
    cost_code: str
    description: str
    job_count: int
    projected_cost_variance: float
    correspondence_downside: float


class SubcontractorRiskInsight(BaseModel):
    subcontractor_id: str
    division_count: int
    ledger_projected_cost: float
    confirmed_unbooked_cost: float
    potential_downside_cost: float


class CorrespondenceJobInsight(BaseModel):
    job_id: str
    division: str
    event_count: int
    confirmed_unbooked_cost: float
    unbooked_contract_value: float
    potential_downside_cost: float
    reported_budget_variance: float
    maximum_reported_delay_days: int | None


class QualityInsight(BaseModel):
    severity: str
    issue_count: int


class ReconciliationInsight(BaseModel):
    layer: str
    passed_checks: int
    total_checks: int


class PortfolioInsights(BaseModel):
    headline: InsightsHeadline
    divisions: list[DivisionInsight]
    risk_ranking: list[RiskRankingInsight]
    progress_statuses: list[StatusCount]
    cost_progress_jobs: list[CostProgressInsight]
    equipment: list[EquipmentInsight]
    cross_division_cost_code_count: int
    cross_division_subcontractor_count: int
    cost_code_risks: list[CostCodeRiskInsight]
    subcontractor_risks: list[SubcontractorRiskInsight]
    correspondence_categories: list[ExposureBucket]
    correspondence_jobs: list[CorrespondenceJobInsight]
    quality_issues: list[QualityInsight]
    reconciliations: list[ReconciliationInsight]
    analysis_quality_issue_count: int


class EquipmentFilters(BaseModel):
    division: str | None = None
    ownership: str | None = None
    equipment_type: str | None = None
    job_id: str | None = None


class EquipmentFilterOptions(BaseModel):
    divisions: list[str]
    ownership_types: list[str]
    equipment_types: list[str]
    jobs: list[str]


class EquipmentKpis(BaseModel):
    assignment_count: int
    job_count: int
    total_equipment_cost: float
    production_units: float
    weighted_cost_per_unit: float | None
    average_utilization: float | None
    owned_cost_per_unit: float | None
    rented_cost_per_unit: float | None
    rental_premium_pct: float | None


class EquipmentBreakdown(BaseModel):
    division: str
    ownership: str
    assignment_count: int
    job_count: int
    total_equipment_cost: float
    production_units: float
    cost_per_unit: float | None
    average_utilization: float | None


class EquipmentTypeSummary(BaseModel):
    equipment_type: str
    ownership: str
    assignment_count: int
    job_count: int
    total_equipment_cost: float
    production_units: float
    cost_per_unit: float | None
    average_utilization: float | None


class EquipmentAssignment(BaseModel):
    assignment_key: str
    job_id: str
    division: str
    equipment_type: str
    ownership: str
    monthly_rate: float
    months_on_job: float
    utilization: float | None
    production_units: float
    total_equipment_cost: float
    cost_per_unit: float | None


class EquipmentDashboard(BaseModel):
    filters: EquipmentFilterOptions
    applied_filters: EquipmentFilters
    kpis: EquipmentKpis
    division_comparison: list[EquipmentBreakdown]
    type_summary: list[EquipmentTypeSummary]
    assignments: list[EquipmentAssignment]
