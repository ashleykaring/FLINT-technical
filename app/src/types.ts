export type ProgressStatus = "critical" | "high" | "watch" | "normal" | "missing_budget";

export interface DashboardFilters {
  division: string | null;
  contract_type: string | null;
  project_manager_id: string | null;
  progress_status: string | null;
}

export interface FilterOptions {
  divisions: string[];
  contract_types: string[];
  project_managers: string[];
  progress_statuses: string[];
}

export interface PortfolioKpis {
  current_cost_budget: number;
  projected_final_cost: number;
  projected_cost_variance: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
  jobs_in_view: number;
  jobs_requiring_attention: number;
}

export interface ScenarioSummary {
  scenario: string;
  contract_value_proxy: number;
  projected_final_cost: number;
  projected_margin: number;
  change_from_base: number;
}

export interface StatusCount {
  status: ProgressStatus;
  job_count: number;
}

export interface JobSummary {
  job_id: string;
  division: string;
  contract_type: string;
  project_manager_id: string;
  current_cost_budget: number;
  projected_final_cost: number;
  projected_cost_variance: number;
  reported_progress_pct: number | null;
  cost_spent_pct: number | null;
  cost_progress_variance: number | null;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
  maximum_reported_delay_days: number | null;
  progress_status: ProgressStatus;
  combined_risk_level: string;
  risk_reasons: string;
}

export interface ParetoPoint {
  rank: number;
  job_id: string;
  exposure: number;
  cumulative_pct: number;
}

export interface PortfolioDashboard {
  filters: FilterOptions;
  applied_filters: DashboardFilters;
  kpis: PortfolioKpis;
  scenarios: ScenarioSummary[];
  status_counts: StatusCount[];
  jobs: JobSummary[];
  pareto: ParetoPoint[];
}

export interface ActiveFilters {
  division: string;
  contractType: string;
  projectManager: string;
  progressStatus: string;
}
