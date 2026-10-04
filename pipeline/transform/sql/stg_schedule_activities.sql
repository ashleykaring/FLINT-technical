CREATE OR REPLACE TABLE stg_schedule_activities AS
WITH parsed AS (
    SELECT
        nullif(upper(regexp_replace(trim(wbs), '[^A-Za-z0-9]', '', 'g')), '') AS job_id,
        nullif(trim(activity_id), '') AS activity_id,
        nullif(trim(activity_name), '') AS activity_name,
        try_cast(baseline_start AS DATE) AS baseline_start,
        try_cast(baseline_finish AS DATE) AS baseline_finish,
        try_cast(actual_start AS DATE) AS actual_start,
        try_cast(actual_finish AS DATE) AS actual_finish,
        try_cast(pct_complete AS DOUBLE) AS pct_complete_raw,
        CASE
            WHEN try_cast(pct_complete AS DOUBLE) BETWEEN 0 AND 1
                THEN try_cast(pct_complete AS DOUBLE)
            WHEN try_cast(pct_complete AS DOUBLE) > 1
                AND try_cast(pct_complete AS DOUBLE) <= 100
                THEN try_cast(pct_complete AS DOUBLE) / 100.0
        END AS pct_complete,
        _source_file,
        _source_row,
        _record_hash
    FROM raw_schedule_activities
),
enriched AS (
    SELECT
        parsed.*,
        jobs.job_id IS NOT NULL AS is_known_job,
        pct_complete_raw > 1 AND pct_complete_raw <= 100 AS is_percentage_scaled,
        pct_complete_raw IS NULL OR pct_complete_raw < 0 OR pct_complete_raw > 100
            AS is_percentage_invalid,
        baseline_start IS NULL OR baseline_finish IS NULL
            OR baseline_finish < baseline_start AS is_baseline_date_invalid,
        actual_start IS NOT NULL AND actual_finish IS NOT NULL
            AND actual_finish < actual_start AS is_actual_finish_before_start
    FROM parsed
    LEFT JOIN stg_jobs AS jobs USING (job_id)
)
SELECT
    *,
    CASE
        WHEN NOT is_baseline_date_invalid
            THEN date_diff('day', baseline_start, baseline_finish)
    END AS baseline_duration_days,
    CASE
        WHEN actual_start IS NOT NULL
            AND actual_finish IS NOT NULL
            AND NOT is_actual_finish_before_start
            THEN date_diff('day', actual_start, actual_finish)
    END AS actual_duration_days,
    is_known_job
        AND NOT is_percentage_invalid
        AND NOT is_baseline_date_invalid
        AND NOT is_actual_finish_before_start AS is_analysis_eligible
FROM enriched;
