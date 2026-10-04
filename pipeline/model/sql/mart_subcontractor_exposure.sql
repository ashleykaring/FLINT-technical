CREATE OR REPLACE TABLE mart_subcontractor_exposure AS
SELECT
    costs.subcontractor_key,
    subcontractors.subcontractor_id,
    subcontractors.display_name,
    subcontractors.source_variant_count,
    count(DISTINCT costs.job_key) FILTER (WHERE NOT jobs.is_unknown) AS job_count,
    count(DISTINCT jobs.division) FILTER (WHERE NOT jobs.is_unknown) AS division_count,
    string_agg(DISTINCT jobs.division, ', ' ORDER BY jobs.division)
        FILTER (WHERE NOT jobs.is_unknown) AS divisions,
    sum(costs.amount) FILTER (WHERE costs.transaction_type = 'ACTUAL') AS actual_cost,
    sum(costs.amount) FILTER (WHERE costs.transaction_type = 'ADJUSTMENT') AS adjustment,
    sum(costs.amount) FILTER (WHERE costs.transaction_type = 'COMMITTED') AS committed_cost,
    sum(costs.amount) FILTER (WHERE costs.transaction_type = 'FORECAST') AS forecast_remaining,
    coalesce(sum(costs.amount) FILTER (WHERE costs.transaction_type = 'ACTUAL'), 0)
        + coalesce(sum(costs.amount) FILTER (WHERE costs.transaction_type = 'ADJUSTMENT'), 0)
        + coalesce(sum(costs.amount) FILTER (WHERE costs.transaction_type = 'FORECAST'), 0)
        AS projected_cost_exposure,
    count(DISTINCT jobs.division) FILTER (WHERE NOT jobs.is_unknown) > 1
        AS is_cross_division
FROM fact_cost_transaction AS costs
JOIN dim_subcontractor AS subcontractors USING (subcontractor_key)
JOIN dim_job AS jobs USING (job_key)
WHERE NOT subcontractors.is_unknown
GROUP BY
    costs.subcontractor_key,
    subcontractors.subcontractor_id,
    subcontractors.display_name,
    subcontractors.source_variant_count;
