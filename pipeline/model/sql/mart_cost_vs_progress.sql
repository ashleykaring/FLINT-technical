CREATE OR REPLACE TABLE mart_cost_vs_progress AS
SELECT
    job_key,
    job_id,
    division,
    contract_type,
    current_cost_budget,
    adjusted_actual_cost,
    cost_spent_pct,
    reported_progress_pct,
    cost_progress_variance,
    projected_final_cost,
    projected_cost_variance,
    projected_margin,
    CASE
        WHEN is_missing_estimate THEN 'missing_budget'
        WHEN cost_progress_variance >= 0.20 THEN 'critical'
        WHEN cost_progress_variance >= 0.10 THEN 'high'
        WHEN cost_progress_variance >= 0.05 THEN 'watch'
        ELSE 'normal'
    END AS cost_progress_status
FROM mart_job_financial;
