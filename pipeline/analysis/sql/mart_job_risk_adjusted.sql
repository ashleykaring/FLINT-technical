CREATE OR REPLACE TABLE mart_job_risk_adjusted AS
SELECT
    financial.job_key,
    financial.job_id,
    financial.division,
    financial.contract_type,
    financial.project_manager_id,
    financial.contract_value_proxy AS base_contract_value_proxy,
    financial.current_cost_budget,
    financial.adjusted_actual_cost,
    financial.committed_cost,
    financial.forecast_remaining,
    financial.projected_final_cost AS base_projected_final_cost,
    financial.projected_margin AS base_projected_margin,
    financial.projected_margin_pct AS base_projected_margin_pct,
    financial.projected_cost_variance AS base_projected_cost_variance,
    financial.cost_spent_pct,
    financial.reported_progress_pct,
    financial.cost_progress_variance,
    exposure.confirmed_unbooked_cost,
    exposure.unbooked_contract_value,
    exposure.pending_change_cost,
    exposure.potential_cost,
    exposure.reported_budget_variance,
    exposure.unquantified_backcharge_count,
    exposure.schedule_event_count,
    exposure.maximum_reported_delay_days,
    exposure.confirmed_margin_adjustment,
    exposure.potential_downside_cost,
    financial.contract_value_proxy + exposure.unbooked_contract_value
        AS confirmed_adjusted_contract_value_proxy,
    financial.projected_final_cost + exposure.confirmed_unbooked_cost
        AS confirmed_adjusted_final_cost,
    financial.projected_margin + exposure.confirmed_margin_adjustment
        AS confirmed_adjusted_margin,
    (financial.projected_margin + exposure.confirmed_margin_adjustment)
        / nullif(financial.contract_value_proxy + exposure.unbooked_contract_value, 0)
        AS confirmed_adjusted_margin_pct,
    financial.projected_final_cost + exposure.confirmed_unbooked_cost
        + exposure.potential_downside_cost AS downside_scenario_final_cost,
    financial.projected_margin + exposure.confirmed_margin_adjustment
        - exposure.potential_downside_cost AS downside_scenario_margin,
    (financial.projected_margin + exposure.confirmed_margin_adjustment
        - exposure.potential_downside_cost)
        / nullif(financial.contract_value_proxy + exposure.unbooked_contract_value, 0)
        AS downside_scenario_margin_pct
FROM mart_job_financial AS financial
JOIN mart_job_correspondence_exposure AS exposure USING (job_key);
