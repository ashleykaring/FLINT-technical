CREATE OR REPLACE TABLE stg_estimates AS
WITH typed AS (
    SELECT
        nullif(upper(regexp_replace(trim(project_id), '[^A-Za-z0-9]', '', 'g')), '') AS job_id,
        nullif(trim(cost_code), '') AS estimate_cost_code,
        nullif(trim(description), '') AS description,
        try_cast(original_estimate AS DECIMAL(18, 2)) AS original_estimate,
        try_cast(current_estimate AS DECIMAL(18, 2)) AS current_estimate,
        current_estimate IS NOT NULL AND trim(current_estimate) <> ''
            AND try_cast(current_estimate AS DECIMAL(18, 2)) IS NULL
            AS is_current_estimate_parse_error,
        _source_file,
        _source_row,
        _record_hash
    FROM raw_estimate_api_line_items
)
SELECT
    typed.* EXCLUDE (is_current_estimate_parse_error),
    current_estimate IS NULL AND NOT is_current_estimate_parse_error
        AS is_current_estimate_missing,
    is_current_estimate_parse_error,
    jobs.job_id IS NOT NULL AS is_known_job,
    typed.job_id IS NOT NULL
        AND typed.estimate_cost_code IS NOT NULL
        AND typed.original_estimate IS NOT NULL
        AND NOT is_current_estimate_parse_error
        AND jobs.job_id IS NOT NULL AS is_valid
FROM typed
LEFT JOIN stg_jobs AS jobs USING (job_id);
