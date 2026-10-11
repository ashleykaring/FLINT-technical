CREATE OR REPLACE TABLE model_analysis_reconciliation AS
WITH checks AS (
    SELECT
        'correspondence_event_rows' AS check_name,
        (SELECT count(*) FROM fact_correspondence_event_current)::DECIMAL(24, 4)
            AS expected_value,
        (SELECT count(*) FROM mart_correspondence_exposure)::DECIMAL(24, 4)
            AS actual_value

    UNION ALL

    SELECT
        'correspondence_event_amount',
        (SELECT coalesce(sum(amount), 0) FROM fact_correspondence_event_current),
        (SELECT coalesce(sum(amount), 0) FROM mart_correspondence_exposure)

    UNION ALL

    SELECT
        'mapped_nonnull_scopes',
        (SELECT count(*) FROM fact_correspondence_event_current WHERE scope IS NOT NULL),
        (SELECT count(*) FROM mart_correspondence_exposure
            WHERE scope IS NOT NULL AND cost_code_key IS NOT NULL)

    UNION ALL

    SELECT
        'job_exposure_rows',
        (SELECT count(*) FROM dim_job WHERE NOT is_unknown),
        (SELECT count(*) FROM mart_job_correspondence_exposure)

    UNION ALL

    SELECT
        'job_risk_adjusted_rows',
        (SELECT count(*) FROM mart_job_financial),
        (SELECT count(*) FROM mart_job_risk_adjusted)

    UNION ALL

    SELECT
        'categorized_correspondence_events',
        (SELECT count(*) FROM fact_correspondence_event_current),
        (SELECT count(*) FROM mart_correspondence_exposure
            WHERE exposure_category IS NOT NULL)

    UNION ALL

    SELECT
        'monthly_ledger_amount',
        (SELECT coalesce(sum(amount), 0) FROM fact_cost_transaction),
        (SELECT coalesce(sum(actual_cost), 0) + coalesce(sum(adjustment), 0)
            + coalesce(sum(committed_cost), 0) + coalesce(sum(forecast_remaining), 0)
         FROM mart_monthly_cost_trend)

    UNION ALL

    SELECT
        'analysis_dq_issues',
        0,
        (SELECT count(*) FROM analysis_dq_issues)
)
SELECT
    check_name,
    expected_value,
    actual_value,
    actual_value - expected_value AS difference,
    abs(actual_value - expected_value) < 0.01 AS passed
FROM checks;
