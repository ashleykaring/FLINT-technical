CREATE OR REPLACE TABLE mart_job_correspondence_exposure AS
WITH exposure AS (
    SELECT
        job_key,
        count(*) AS correspondence_event_count,
        count(DISTINCT doc_id) AS correspondence_document_count,
        sum(amount) FILTER (WHERE exposure_category = 'confirmed_unbooked_cost')
            AS confirmed_unbooked_cost,
        sum(amount) FILTER (WHERE exposure_category = 'unbooked_contract_value')
            AS unbooked_contract_value,
        sum(amount) FILTER (WHERE exposure_category = 'pending_change_cost')
            AS pending_change_cost,
        sum(amount) FILTER (WHERE exposure_category = 'potential_cost')
            AS potential_cost,
        sum(amount) FILTER (WHERE exposure_category = 'budget_variance')
            AS reported_budget_variance,
        count(*) FILTER (WHERE exposure_category = 'disputed_backcharge_unquantified')
            AS unquantified_backcharge_count,
        count(*) FILTER (WHERE schedule_impact_days IS NOT NULL) AS schedule_event_count,
        max(schedule_impact_days) FILTER (WHERE schedule_impact_type = 'delay')
            AS maximum_reported_delay_days,
        max(schedule_impact_days) FILTER (WHERE schedule_impact_type = 'recovery')
            AS maximum_reported_recovery_days,
        max(schedule_impact_days) FILTER (WHERE schedule_impact_type = 'available_float')
            AS maximum_reported_available_float_days
    FROM mart_correspondence_exposure
    GROUP BY job_key
)
SELECT
    jobs.job_key,
    jobs.job_id,
    jobs.division,
    jobs.contract_type,
    coalesce(exposure.correspondence_event_count, 0) AS correspondence_event_count,
    coalesce(exposure.correspondence_document_count, 0) AS correspondence_document_count,
    coalesce(exposure.confirmed_unbooked_cost, 0) AS confirmed_unbooked_cost,
    coalesce(exposure.unbooked_contract_value, 0) AS unbooked_contract_value,
    coalesce(exposure.pending_change_cost, 0) AS pending_change_cost,
    coalesce(exposure.potential_cost, 0) AS potential_cost,
    coalesce(exposure.reported_budget_variance, 0) AS reported_budget_variance,
    coalesce(exposure.unquantified_backcharge_count, 0) AS unquantified_backcharge_count,
    coalesce(exposure.schedule_event_count, 0) AS schedule_event_count,
    exposure.maximum_reported_delay_days,
    exposure.maximum_reported_recovery_days,
    exposure.maximum_reported_available_float_days,
    coalesce(exposure.unbooked_contract_value, 0)
        - coalesce(exposure.confirmed_unbooked_cost, 0) AS confirmed_margin_adjustment,
    coalesce(exposure.pending_change_cost, 0) + coalesce(exposure.potential_cost, 0)
        AS potential_downside_cost
FROM dim_job AS jobs
LEFT JOIN exposure USING (job_key)
WHERE NOT jobs.is_unknown;
