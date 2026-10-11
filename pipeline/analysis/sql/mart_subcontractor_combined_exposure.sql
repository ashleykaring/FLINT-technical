CREATE OR REPLACE TABLE mart_subcontractor_combined_exposure AS
WITH correspondence AS (
    SELECT
        subcontractor_key,
        count(*) AS correspondence_event_count,
        count(DISTINCT job_key) AS correspondence_job_count,
        count(DISTINCT division) AS correspondence_division_count,
        sum(amount) FILTER (WHERE exposure_category = 'confirmed_unbooked_cost')
            AS confirmed_unbooked_cost,
        sum(amount) FILTER (WHERE exposure_category = 'unbooked_contract_value')
            AS unbooked_contract_value,
        sum(amount) FILTER (WHERE exposure_category = 'pending_change_cost')
            AS pending_change_cost,
        sum(amount) FILTER (WHERE exposure_category = 'potential_cost')
            AS potential_cost,
        sum(amount) FILTER (WHERE exposure_category = 'budget_variance')
            AS reported_budget_variance
    FROM mart_correspondence_exposure
    GROUP BY subcontractor_key
)
SELECT
    subcontractors.subcontractor_key,
    subcontractors.subcontractor_id,
    subcontractors.display_name,
    coalesce(ledger.job_count, 0) AS ledger_job_count,
    coalesce(ledger.division_count, 0) AS ledger_division_count,
    ledger.divisions AS ledger_divisions,
    coalesce(ledger.actual_cost, 0) AS actual_cost,
    coalesce(ledger.adjustment, 0) AS adjustment,
    coalesce(ledger.committed_cost, 0) AS committed_cost,
    coalesce(ledger.forecast_remaining, 0) AS forecast_remaining,
    coalesce(ledger.projected_cost_exposure, 0) AS ledger_projected_cost_exposure,
    coalesce(correspondence.correspondence_event_count, 0)
        AS correspondence_event_count,
    coalesce(correspondence.correspondence_job_count, 0)
        AS correspondence_job_count,
    coalesce(correspondence.correspondence_division_count, 0)
        AS correspondence_division_count,
    coalesce(correspondence.confirmed_unbooked_cost, 0) AS confirmed_unbooked_cost,
    coalesce(correspondence.unbooked_contract_value, 0) AS unbooked_contract_value,
    coalesce(correspondence.pending_change_cost, 0) AS pending_change_cost,
    coalesce(correspondence.potential_cost, 0) AS potential_cost,
    coalesce(correspondence.reported_budget_variance, 0) AS reported_budget_variance,
    greatest(
        coalesce(ledger.division_count, 0),
        coalesce(correspondence.correspondence_division_count, 0)
    ) > 1 AS is_cross_division
FROM dim_subcontractor AS subcontractors
LEFT JOIN mart_subcontractor_exposure AS ledger USING (subcontractor_key)
LEFT JOIN correspondence USING (subcontractor_key)
WHERE NOT subcontractors.is_unknown;
