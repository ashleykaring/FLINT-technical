CREATE OR REPLACE TABLE fact_cost_transaction AS
SELECT
    _record_hash AS cost_transaction_key,
    CASE WHEN is_known_job THEN job_id ELSE 'UNKNOWN_JOB' END AS job_key,
    CASE
        WHEN cost_code_mapping_status = 'mapped' THEN estimate_cost_code
        ELSE 'UNMAPPED_COST_CODE'
    END AS cost_code_key,
    coalesce(subcontractor_id, 'UNKNOWN_SUBCONTRACTOR') AS subcontractor_key,
    period,
    upper(transaction_type) AS transaction_type,
    amount,
    unit_of_measure,
    quantity,
    erp_cost_code,
    duplicate_source_count,
    duplicate_source_count > 1 AS was_deduplicated,
    is_missing_job_id,
    is_unknown_job,
    is_unmapped_cost_code,
    is_amount_parse_error,
    is_period_parse_error,
    _source_file,
    _source_row,
    _record_hash
FROM stg_job_cost_ledger
WHERE NOT is_exact_duplicate;
