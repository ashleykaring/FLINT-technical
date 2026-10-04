CREATE OR REPLACE TABLE fact_budget AS
SELECT
    md5(concat_ws(chr(31), job_id, estimate_cost_code)) AS budget_key,
    CASE WHEN is_known_job THEN job_id ELSE 'UNKNOWN_JOB' END AS job_key,
    coalesce(estimate_cost_code, 'UNMAPPED_COST_CODE') AS cost_code_key,
    original_estimate,
    current_estimate,
    coalesce(current_estimate, original_estimate) AS current_budget_basis,
    current_estimate IS NULL AS used_original_estimate_fallback,
    description,
    _source_file,
    _source_row,
    _record_hash
FROM stg_estimates;
