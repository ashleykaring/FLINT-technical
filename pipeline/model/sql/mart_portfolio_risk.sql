CREATE OR REPLACE TABLE mart_portfolio_risk AS
WITH ledger_quality AS (
    SELECT
        CASE WHEN is_known_job THEN job_id ELSE 'UNKNOWN_JOB' END AS job_key,
        count(*) FILTER (WHERE duplicate_source_count > 1) AS duplicate_posting_group_rows,
        count(*) FILTER (WHERE is_unmapped_cost_code) AS unmapped_cost_postings
    FROM stg_job_cost_ledger
    WHERE NOT is_exact_duplicate
    GROUP BY job_key
),
schedule_quality AS (
    SELECT
        job_key,
        count(*) FILTER (WHERE is_actual_finish_before_start) AS reversed_actual_activities,
        avg(pct_complete) AS mean_activity_progress_pct
    FROM fact_schedule_activity
    GROUP BY job_key
),
equipment AS (
    SELECT
        job_key,
        sum(total_equipment_cost) AS equipment_cost,
        avg(utilization) AS average_equipment_utilization
    FROM fact_equipment_usage
    GROUP BY job_key
),
base AS (
    SELECT
        financial.*,
        coalesce(ledger_quality.duplicate_posting_group_rows, 0)
            AS duplicate_posting_group_rows,
        coalesce(ledger_quality.unmapped_cost_postings, 0) AS unmapped_cost_postings,
        coalesce(schedule_quality.reversed_actual_activities, 0)
            AS reversed_actual_activities,
        schedule_quality.mean_activity_progress_pct,
        coalesce(equipment.equipment_cost, 0) AS equipment_cost,
        equipment.average_equipment_utilization
    FROM mart_job_financial AS financial
    LEFT JOIN ledger_quality USING (job_key)
    LEFT JOIN schedule_quality USING (job_key)
    LEFT JOIN equipment USING (job_key)
)
SELECT
    *,
    CASE
        WHEN is_missing_estimate
            OR projected_margin < 0
            OR cost_progress_variance >= 0.20 THEN 'critical'
        WHEN cost_progress_variance >= 0.10
            OR estimate_drift_pct >= 0.10
            OR reversed_actual_activities > 0 THEN 'high'
        WHEN cost_progress_variance >= 0.05
            OR missing_current_estimate_lines > 0
            OR unmapped_cost_postings > 0 THEN 'watch'
        ELSE 'normal'
    END AS risk_level,
    concat_ws(
        '; ',
        CASE WHEN is_missing_estimate THEN 'missing estimating data' END,
        CASE WHEN projected_margin < 0 THEN 'negative projected margin' END,
        CASE WHEN cost_progress_variance >= 0.10 THEN 'cost burn ahead of progress' END,
        CASE WHEN estimate_drift_pct >= 0.10 THEN 'estimate drift' END,
        CASE WHEN reversed_actual_activities > 0 THEN 'invalid actual schedule dates' END,
        CASE WHEN unmapped_cost_postings > 0 THEN 'unmapped cost postings' END
    ) AS risk_reasons
FROM base;
