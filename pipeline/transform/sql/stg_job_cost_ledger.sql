CREATE OR REPLACE TABLE stg_job_cost_ledger AS
WITH parsed AS (
    SELECT
        nullif(upper(regexp_replace(trim(job_id), '[^A-Za-z0-9]', '', 'g')), '') AS job_id,
        nullif(trim(cost_code), '') AS erp_cost_code,
        coalesce(
            try_cast(period AS DATE),
            cast(try_strptime(period, '%m/%d/%Y') AS DATE)
        ) AS period,
        nullif(upper(regexp_replace(trim(subcontractor), '[^A-Za-z0-9]', '', 'g')), '')
            AS subcontractor_id,
        nullif(trim(txn_type), '') AS transaction_type,
        try_cast(regexp_replace(amount, '[$,]', '', 'g') AS DECIMAL(18, 4)) AS amount,
        nullif(trim(uom), '') AS unit_of_measure,
        try_cast(quantity AS DECIMAL(18, 4)) AS quantity,
        nullif(trim(job_id), '') IS NULL AS is_missing_job_id,
        amount IS NOT NULL AND trim(amount) <> ''
            AND try_cast(regexp_replace(amount, '[$,]', '', 'g') AS DECIMAL(18, 4)) IS NULL
            AS is_amount_parse_error,
        period IS NOT NULL AND trim(period) <> ''
            AND coalesce(
                try_cast(period AS DATE),
                cast(try_strptime(period, '%m/%d/%Y') AS DATE)
            ) IS NULL AS is_period_parse_error,
        _source_file,
        _source_row,
        _record_hash
    FROM raw_job_cost_ledger
),
enriched AS (
    SELECT
        parsed.*,
        cost_map.estimate_cost_code,
        cost_map.canonical_description AS cost_code_description,
        cost_map.mapping_status AS cost_code_mapping_status,
        jobs.job_id IS NOT NULL AS is_known_job,
        count(*) OVER (PARTITION BY parsed._record_hash) AS duplicate_source_count,
        row_number() OVER (
            PARTITION BY parsed._record_hash
            ORDER BY parsed._source_row
        ) AS duplicate_rank
    FROM parsed
    LEFT JOIN ref_cost_code_map AS cost_map USING (erp_cost_code)
    LEFT JOIN stg_jobs AS jobs USING (job_id)
)
SELECT
    * EXCLUDE (duplicate_rank),
    job_id IS NOT NULL AND NOT is_known_job AS is_unknown_job,
    coalesce(cost_code_mapping_status, 'unmapped') <> 'mapped' AS is_unmapped_cost_code,
    duplicate_rank > 1 AS is_exact_duplicate,
    NOT is_missing_job_id
        AND is_known_job
        AND coalesce(cost_code_mapping_status, 'unmapped') = 'mapped'
        AND NOT is_amount_parse_error
        AND NOT is_period_parse_error
        AND duplicate_rank = 1 AS is_analysis_eligible
FROM enriched;
