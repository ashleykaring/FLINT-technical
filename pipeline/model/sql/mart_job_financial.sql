CREATE OR REPLACE TABLE mart_job_financial AS
WITH cost AS (
    SELECT
        job_key,
        sum(amount) FILTER (WHERE transaction_type = 'ACTUAL') AS actual_cost,
        sum(amount) FILTER (WHERE transaction_type = 'ADJUSTMENT') AS adjustment,
        sum(amount) FILTER (WHERE transaction_type = 'COMMITTED') AS committed_cost,
        sum(amount) FILTER (WHERE transaction_type = 'FORECAST') AS forecast_remaining,
        count(*) AS transaction_count,
        count(*) FILTER (WHERE was_deduplicated) AS deduplicated_group_rows
    FROM fact_cost_transaction
    GROUP BY job_key
),
budget AS (
    SELECT
        job_key,
        sum(original_estimate) AS original_cost_budget,
        sum(current_budget_basis) AS current_cost_budget,
        count(*) AS budget_line_count,
        count(*) FILTER (WHERE used_original_estimate_fallback)
            AS missing_current_estimate_lines
    FROM fact_budget
    GROUP BY job_key
),
base AS (
    SELECT
        jobs.job_key,
        jobs.job_id,
        jobs.division,
        jobs.contract_type,
        jobs.project_manager_id,
        jobs.contract_value_proxy,
        jobs.reported_progress_pct,
        budget.original_cost_budget,
        budget.current_cost_budget,
        coalesce(cost.actual_cost, 0) AS actual_cost,
        coalesce(cost.adjustment, 0) AS adjustment,
        coalesce(cost.actual_cost, 0) + coalesce(cost.adjustment, 0)
            AS adjusted_actual_cost,
        coalesce(cost.committed_cost, 0) AS committed_cost,
        coalesce(cost.forecast_remaining, 0) AS forecast_remaining,
        coalesce(cost.actual_cost, 0) + coalesce(cost.adjustment, 0)
            + coalesce(cost.forecast_remaining, 0) AS projected_final_cost,
        coalesce(cost.transaction_count, 0) AS transaction_count,
        coalesce(cost.deduplicated_group_rows, 0) AS deduplicated_group_rows,
        coalesce(budget.budget_line_count, 0) AS budget_line_count,
        coalesce(budget.missing_current_estimate_lines, 0)
            AS missing_current_estimate_lines,
        budget.job_key IS NULL AS is_missing_estimate
    FROM dim_job AS jobs
    LEFT JOIN cost USING (job_key)
    LEFT JOIN budget USING (job_key)
    WHERE NOT jobs.is_unknown
)
SELECT
    *,
    contract_value_proxy - projected_final_cost AS projected_margin,
    (contract_value_proxy - projected_final_cost) / nullif(contract_value_proxy, 0)
        AS projected_margin_pct,
    projected_final_cost - current_cost_budget AS projected_cost_variance,
    (projected_final_cost - current_cost_budget) / nullif(current_cost_budget, 0)
        AS projected_cost_variance_pct,
    current_cost_budget - original_cost_budget AS estimate_drift,
    (current_cost_budget - original_cost_budget) / nullif(original_cost_budget, 0)
        AS estimate_drift_pct,
    adjusted_actual_cost / nullif(current_cost_budget, 0) AS cost_spent_pct,
    adjusted_actual_cost / nullif(current_cost_budget, 0) - reported_progress_pct
        AS cost_progress_variance
FROM base;
