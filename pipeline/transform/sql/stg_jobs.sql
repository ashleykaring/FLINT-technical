CREATE OR REPLACE TABLE stg_jobs AS
WITH normalized AS (
    SELECT
        nullif(upper(regexp_replace(trim(job_id), '[^A-Za-z0-9]', '', 'g')), '') AS job_id,
        nullif(trim(division), '') AS division,
        nullif(trim(contract_type), '') AS contract_type,
        try_cast(regexp_replace(original_budget, '[$,]', '', 'g') AS DECIMAL(18, 2))
            AS original_budget,
        try_cast(start_date AS DATE) AS start_date,
        try_cast(planned_days AS INTEGER) AS planned_days,
        CASE
            WHEN try_cast(pct_complete AS DOUBLE) BETWEEN 0 AND 1
                THEN try_cast(pct_complete AS DOUBLE)
            WHEN try_cast(pct_complete AS DOUBLE) BETWEEN 1 AND 100
                THEN try_cast(pct_complete AS DOUBLE) / 100.0
        END AS pct_complete,
        nullif(trim(pm), '') AS project_manager_id,
        _source_file,
        _source_row,
        _record_hash
    FROM raw_jobs
),
ranked AS (
    SELECT
        *,
        count(*) OVER (PARTITION BY job_id) AS duplicate_source_count,
        row_number() OVER (PARTITION BY job_id ORDER BY _source_row) AS source_rank
    FROM normalized
)
SELECT
    job_id,
    division,
    contract_type,
    original_budget,
    start_date,
    planned_days,
    pct_complete,
    project_manager_id,
    duplicate_source_count,
    duplicate_source_count > 1 AS is_duplicate_source,
    job_id IS NOT NULL
        AND division IN ('Building', 'Civil')
        AND original_budget IS NOT NULL
        AND start_date IS NOT NULL
        AND planned_days IS NOT NULL
        AND pct_complete IS NOT NULL AS is_valid,
    _source_file,
    _source_row,
    _record_hash
FROM ranked
WHERE source_rank = 1;
