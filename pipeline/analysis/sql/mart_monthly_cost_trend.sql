CREATE OR REPLACE TABLE mart_monthly_cost_trend AS
WITH monthly AS (
    SELECT
        costs.period,
        costs.job_key,
        jobs.job_id,
        jobs.division,
        jobs.contract_type,
        costs.cost_code_key,
        codes.canonical_description AS cost_code_description,
        sum(costs.amount) FILTER (WHERE costs.transaction_type = 'ACTUAL') AS actual_cost,
        sum(costs.amount) FILTER (WHERE costs.transaction_type = 'ADJUSTMENT') AS adjustment,
        sum(costs.amount) FILTER (WHERE costs.transaction_type = 'COMMITTED') AS committed_cost,
        sum(costs.amount) FILTER (WHERE costs.transaction_type = 'FORECAST')
            AS forecast_remaining
    FROM fact_cost_transaction AS costs
    JOIN dim_job AS jobs USING (job_key)
    JOIN dim_cost_code AS codes USING (cost_code_key)
    GROUP BY
        costs.period,
        costs.job_key,
        jobs.job_id,
        jobs.division,
        jobs.contract_type,
        costs.cost_code_key,
        codes.canonical_description
)
SELECT
    *,
    coalesce(actual_cost, 0) + coalesce(adjustment, 0) AS adjusted_actual_cost,
    sum(coalesce(actual_cost, 0) + coalesce(adjustment, 0)) OVER (
        PARTITION BY job_key, cost_code_key
        ORDER BY period
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_adjusted_actual_cost
FROM monthly;
