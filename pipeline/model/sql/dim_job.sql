CREATE OR REPLACE TABLE dim_job AS
SELECT
    job_id AS job_key,
    job_id,
    division,
    contract_type,
    original_budget AS contract_value_proxy,
    start_date,
    planned_days,
    pct_complete AS reported_progress_pct,
    project_manager_id,
    is_duplicate_source,
    false AS is_unknown
FROM stg_jobs

UNION ALL

SELECT
    'UNKNOWN_JOB' AS job_key,
    cast(NULL AS VARCHAR) AS job_id,
    'Unknown' AS division,
    'Unknown' AS contract_type,
    cast(NULL AS DECIMAL(18, 2)) AS contract_value_proxy,
    cast(NULL AS DATE) AS start_date,
    cast(NULL AS INTEGER) AS planned_days,
    cast(NULL AS DOUBLE) AS reported_progress_pct,
    cast(NULL AS VARCHAR) AS project_manager_id,
    false AS is_duplicate_source,
    true AS is_unknown;
