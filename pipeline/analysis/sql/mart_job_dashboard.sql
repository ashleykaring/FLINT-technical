CREATE OR REPLACE TABLE mart_job_dashboard AS
WITH scored AS (
    SELECT
        adjusted.*,
        base.risk_level AS base_risk_level,
        base.risk_reasons AS base_risk_reasons,
        CASE
            WHEN adjusted.downside_scenario_margin < 0 OR base.risk_level = 'critical'
                THEN 'critical'
            WHEN base.risk_level = 'high'
              OR adjusted.confirmed_unbooked_cost
                    / nullif(adjusted.current_cost_budget, 0) >= 0.05
              OR adjusted.maximum_reported_delay_days >= 15 THEN 'high'
            WHEN base.risk_level = 'watch'
              OR adjusted.potential_downside_cost > 0
              OR adjusted.reported_budget_variance > 0
              OR adjusted.schedule_event_count > 0 THEN 'watch'
            ELSE 'normal'
        END AS combined_risk_level
    FROM mart_job_risk_adjusted AS adjusted
    JOIN mart_portfolio_risk AS base USING (job_key)
)
SELECT
    *,
    concat_ws(
        '; ',
        nullif(base_risk_reasons, ''),
        CASE WHEN confirmed_unbooked_cost > 0 THEN 'authorized cost not booked' END,
        CASE WHEN unbooked_contract_value > 0 THEN 'contract value not booked' END,
        CASE WHEN pending_change_cost > 0 THEN 'pending change cost' END,
        CASE WHEN potential_cost > 0 THEN 'RFI potential cost' END,
        CASE WHEN reported_budget_variance > 0 THEN 'reported budget variance' END,
        CASE WHEN maximum_reported_delay_days >= 15 THEN 'material reported delay' END,
        CASE WHEN unquantified_backcharge_count > 0 THEN 'unquantified backcharge dispute' END
    ) AS combined_risk_reasons
FROM scored;
