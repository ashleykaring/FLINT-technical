CREATE OR REPLACE TABLE mart_correspondence_cost_code_exposure AS
SELECT
    division,
    coalesce(cost_code_key, 'UNMAPPED_COST_CODE') AS cost_code_key,
    coalesce(cost_code_description, 'Unmapped correspondence scope')
        AS cost_code_description,
    count(*) AS event_count,
    count(DISTINCT job_key) AS job_count,
    sum(amount) FILTER (WHERE exposure_category = 'confirmed_unbooked_cost')
        AS confirmed_unbooked_cost,
    sum(amount) FILTER (WHERE exposure_category = 'unbooked_contract_value')
        AS unbooked_contract_value,
    sum(amount) FILTER (WHERE exposure_category = 'pending_change_cost')
        AS pending_change_cost,
    sum(amount) FILTER (WHERE exposure_category = 'potential_cost') AS potential_cost,
    sum(amount) FILTER (WHERE exposure_category = 'budget_variance')
        AS reported_budget_variance,
    count(*) FILTER (WHERE exposure_category = 'disputed_backcharge_unquantified')
        AS unquantified_backcharge_count,
    max(schedule_impact_days) FILTER (WHERE schedule_impact_type = 'delay')
        AS maximum_reported_delay_days
FROM mart_correspondence_exposure
GROUP BY division, coalesce(cost_code_key, 'UNMAPPED_COST_CODE'),
    coalesce(cost_code_description, 'Unmapped correspondence scope');
