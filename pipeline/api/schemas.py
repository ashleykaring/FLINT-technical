from __future__ import annotations

from pydantic import BaseModel


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
    projected_final_cost: float
    projected_cost_variance: float
    confirmed_unbooked_cost: float
    potential_downside_cost: float
    jobs_in_view: int
    jobs_requiring_attention: int


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


class ParetoPoint(BaseModel):
    rank: int
    job_id: str
    exposure: float
    cumulative_pct: float


class PortfolioDashboard(BaseModel):
    filters: FilterOptions
    applied_filters: DashboardFilters
    kpis: PortfolioKpis
    scenarios: list[ScenarioSummary]
    status_counts: list[StatusCount]
    jobs: list[JobSummary]
    pareto: list[ParetoPoint]
