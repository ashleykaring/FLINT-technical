CREATE OR REPLACE TABLE mart_cost_code_exposure AS
WITH cost AS (
    SELECT
        cost_code_key,
        count(DISTINCT job_key) FILTER (WHERE job_key <> 'UNKNOWN_JOB') AS job_count,
        sum(amount) FILTER (WHERE transaction_type = 'ACTUAL') AS actual_cost,
        sum(amount) FILTER (WHERE transaction_type = 'ADJUSTMENT') AS adjustment,
        sum(amount) FILTER (WHERE transaction_type = 'COMMITTED') AS committed_cost,
        sum(amount) FILTER (WHERE transaction_type = 'FORECAST') AS forecast_remaining
    FROM fact_cost_transaction
    GROUP BY cost_code_key
),
budget AS (
    SELECT
        cost_code_key,
        sum(original_estimate) AS original_cost_budget,
        sum(current_budget_basis) AS current_cost_budget
    FROM fact_budget
    GROUP BY cost_code_key
)
SELECT
    codes.cost_code_key,
    codes.estimate_cost_code,
    codes.erp_cost_code,
    codes.canonical_description,
    codes.is_unknown,
    coalesce(cost.job_count, 0) AS job_count,
    budget.original_cost_budget,
    budget.current_cost_budget,
    coalesce(cost.actual_cost, 0) AS actual_cost,
    coalesce(cost.adjustment, 0) AS adjustment,
    coalesce(cost.committed_cost, 0) AS committed_cost,
    coalesce(cost.forecast_remaining, 0) AS forecast_remaining,
    coalesce(cost.actual_cost, 0) + coalesce(cost.adjustment, 0)
        + coalesce(cost.forecast_remaining, 0) AS projected_cost,
    coalesce(cost.actual_cost, 0) + coalesce(cost.adjustment, 0)
        + coalesce(cost.forecast_remaining, 0) - budget.current_cost_budget
        AS projected_cost_variance
FROM dim_cost_code AS codes
LEFT JOIN cost USING (cost_code_key)
LEFT JOIN budget USING (cost_code_key);
