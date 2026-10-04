CREATE OR REPLACE TABLE fact_schedule_activity AS
SELECT
    activity_id AS schedule_activity_key,
    CASE WHEN is_known_job THEN job_id ELSE 'UNKNOWN_JOB' END AS job_key,
    activity_id,
    activity_name,
    baseline_start,
    baseline_finish,
    actual_start,
    actual_finish,
    pct_complete,
    baseline_duration_days,
    actual_duration_days,
    is_percentage_scaled,
    is_percentage_invalid,
    is_baseline_date_invalid,
    is_actual_finish_before_start,
    is_analysis_eligible,
    _source_file,
    _source_row,
    _record_hash
FROM stg_schedule_activities;
