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
  actual_cost_to_date: number;
  projected_final_cost: number;
  projected_cost_variance: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
  jobs_in_view: number;
  jobs_requiring_attention: number;
}

export interface BudgetOutlookSummary {
  total_jobs: number;
  currently_over_count: number;
  forecast_only_count: number;
  within_forecast_count: number;
  missing_budget_count: number;
  current_gross_overrun: number;
  projected_gross_overrun: number;
  forecast_only_exposure: number;
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
  adjusted_actual_cost: number;
  budget_outlook: "already_over" | "forecast_over" | "within_forecast" | "missing_budget";
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
  budget_outlook: BudgetOutlookSummary;
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

export interface JobFinancialSummary {
  job_id: string;
  division: string;
  contract_type: string;
  project_manager_id: string;
  start_date: string | null;
  planned_days: number | null;
  reported_progress_pct: number | null;
  cost_spent_pct: number | null;
  progress_status: ProgressStatus;
  combined_risk_level: string;
  risk_reasons: string;
  contract_value_proxy: number;
  current_cost_budget: number;
  adjusted_actual_cost: number;
  committed_cost: number;
  forecast_remaining: number;
  projected_final_cost: number;
  projected_cost_variance: number;
  projected_margin: number;
  confirmed_unbooked_cost: number;
  unbooked_contract_value: number;
  potential_downside_cost: number;
  reported_budget_variance: number;
  unquantified_backcharge_count: number;
  schedule_event_count: number;
  maximum_reported_delay_days: number | null;
}

export interface MonthlyCostPoint {
  period: string;
  actual_cost: number;
  adjustment: number;
  committed_cost: number;
  forecast_remaining: number;
  adjusted_actual_cost: number;
  cumulative_adjusted_actual_cost: number;
}

export interface CostCodeDetail {
  cost_code: string;
  description: string;
  current_budget: number;
  adjusted_actual_cost: number;
  committed_cost: number;
  forecast_remaining: number;
  projected_cost: number;
  projected_variance: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
}

export interface ExposureBucket {
  category: string;
  event_count: number;
  amount: number;
}

export interface CorrespondenceEventDetail {
  event_key: string;
  doc_id: string;
  doc_type: string;
  event_index: number;
  category: string;
  event_type: string;
  scope: string | null;
  cost_code: string | null;
  cost_code_description: string | null;
  subcontractor_id: string | null;
  amount: number | null;
  booking_status: string;
  approval_status: string;
  schedule_impact_days: number | null;
  schedule_impact_type: string;
  evidence_text: string;
}

export interface ScheduleSummary {
  activity_count: number;
  incomplete_activity_count: number;
  mean_activity_progress_pct: number | null;
  reversed_actual_activity_count: number;
  schedule_correspondence_event_count: number;
  maximum_reported_delay_days: number | null;
}

export interface ScheduleActivityDetail {
  activity_id: string;
  activity_name: string;
  baseline_start: string | null;
  baseline_finish: string | null;
  actual_start: string | null;
  actual_finish: string | null;
  pct_complete: number | null;
  baseline_duration_days: number | null;
  actual_duration_days: number | null;
  duration_variance_days: number | null;
  has_reversed_actual_dates: boolean;
}

export interface SubcontractorJobExposure {
  subcontractor_id: string;
  display_name: string;
  actual_cost: number;
  adjustment: number;
  committed_cost: number;
  forecast_remaining: number;
  projected_cost_exposure: number;
  correspondence_event_count: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
}

export interface JobDetail {
  summary: JobFinancialSummary;
  scenarios: ScenarioSummary[];
  monthly_costs: MonthlyCostPoint[];
  cost_codes: CostCodeDetail[];
  exposure_buckets: ExposureBucket[];
  correspondence_events: CorrespondenceEventDetail[];
  schedule_summary: ScheduleSummary;
  schedule_activities: ScheduleActivityDetail[];
  subcontractors: SubcontractorJobExposure[];
}

export type JobAnswerSection =
  | "FINANCIAL"
  | "COST_CODES"
  | "SCHEDULE"
  | "EQUIPMENT"
  | "CORRESPONDENCE"
  | "SUBCONTRACTORS";

export interface JobAnswerFact {
  statement: string;
  source_section: JobAnswerSection;
}

export interface JobQuestionResponse {
  answer: string;
  supporting_facts: JobAnswerFact[];
  caveat: string | null;
}

export interface InsightsHeadline {
  job_count: number;
  current_cost_budget: number;
  projected_final_cost: number;
  net_projected_cost_variance: number;
  positive_cost_variance: number;
  base_projected_margin: number;
  confirmed_adjusted_margin: number;
  downside_scenario_margin: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
  critical_cost_progress_jobs: number;
  jobs_to_eighty_pct: number;
  top_five_variance_share: number;
}

export interface DivisionInsight {
  division: string;
  job_count: number;
  current_cost_budget: number;
  projected_final_cost: number;
  projected_cost_variance: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
  downside_scenario_margin: number;
}

export interface RiskRankingInsight {
  rank: number;
  job_id: string;
  division: string;
  projected_cost_variance: number;
  potential_downside_cost: number;
  cumulative_pct: number;
}

export interface CostProgressInsight {
  job_id: string;
  division: string;
  reported_progress_pct: number | null;
  cost_spent_pct: number | null;
  cost_progress_variance: number | null;
  status: ProgressStatus;
}

export interface EquipmentInsight {
  division: string;
  ownership: string;
  assignment_count: number;
  job_count: number;
  total_equipment_cost: number;
  production_units: number;
  cost_per_unit: number | null;
  average_utilization: number | null;
}

export interface CostCodeRiskInsight {
  cost_code: string;
  description: string;
  job_count: number;
  projected_cost_variance: number;
  correspondence_downside: number;
}

export interface SubcontractorRiskInsight {
  subcontractor_id: string;
  division_count: number;
  ledger_projected_cost: number;
  confirmed_unbooked_cost: number;
  potential_downside_cost: number;
}

export interface CorrespondenceJobInsight {
  job_id: string;
  division: string;
  event_count: number;
  confirmed_unbooked_cost: number;
  unbooked_contract_value: number;
  potential_downside_cost: number;
  reported_budget_variance: number;
  maximum_reported_delay_days: number | null;
}

export interface QualityInsight {
  severity: string;
  issue_count: number;
}

export interface ReconciliationInsight {
  layer: string;
  passed_checks: number;
  total_checks: number;
}

export interface PortfolioInsights {
  headline: InsightsHeadline;
  divisions: DivisionInsight[];
  risk_ranking: RiskRankingInsight[];
  progress_statuses: StatusCount[];
  cost_progress_jobs: CostProgressInsight[];
  equipment: EquipmentInsight[];
  cross_division_cost_code_count: number;
  cross_division_subcontractor_count: number;
  cost_code_risks: CostCodeRiskInsight[];
  subcontractor_risks: SubcontractorRiskInsight[];
  correspondence_categories: ExposureBucket[];
  correspondence_jobs: CorrespondenceJobInsight[];
  quality_issues: QualityInsight[];
  reconciliations: ReconciliationInsight[];
  analysis_quality_issue_count: number;
}

export interface EquipmentFilters {
  division: string | null;
  ownership: string | null;
  equipment_type: string | null;
  job_id: string | null;
}

export interface EquipmentFilterOptions {
  divisions: string[];
  ownership_types: string[];
  equipment_types: string[];
  jobs: string[];
}

export interface EquipmentKpis {
  assignment_count: number;
  job_count: number;
  total_equipment_cost: number;
  production_units: number;
  weighted_cost_per_unit: number | null;
  average_utilization: number | null;
  owned_cost_per_unit: number | null;
  rented_cost_per_unit: number | null;
  rental_premium_pct: number | null;
}

export interface EquipmentBreakdown {
  division: string;
  ownership: string;
  assignment_count: number;
  job_count: number;
  total_equipment_cost: number;
  production_units: number;
  cost_per_unit: number | null;
  average_utilization: number | null;
}

export interface EquipmentTypeSummary {
  equipment_type: string;
  ownership: string;
  assignment_count: number;
  job_count: number;
  total_equipment_cost: number;
  production_units: number;
  cost_per_unit: number | null;
  average_utilization: number | null;
}

export interface EquipmentAssignment {
  assignment_key: string;
  job_id: string;
  division: string;
  equipment_type: string;
  ownership: string;
  monthly_rate: number;
  months_on_job: number;
  utilization: number | null;
  production_units: number;
  total_equipment_cost: number;
  cost_per_unit: number | null;
}

export interface EquipmentDashboard {
  filters: EquipmentFilterOptions;
  applied_filters: EquipmentFilters;
  kpis: EquipmentKpis;
  division_comparison: EquipmentBreakdown[];
  type_summary: EquipmentTypeSummary[];
  assignments: EquipmentAssignment[];
}

export interface EquipmentActiveFilters {
  division: string;
  ownership: string;
  equipmentType: string;
  jobId: string;
}
