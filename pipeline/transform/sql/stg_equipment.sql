CREATE OR REPLACE TABLE stg_equipment AS
WITH parsed AS (
    SELECT
        nullif(trim("Job"), '') AS source_job_reference,
        nullif(upper(regexp_replace(trim("Job"), '[^A-Za-z0-9]', '', 'g')), '')
            AS normalized_job_reference,
        nullif(trim("Equip_Type"), '') AS equipment_type,
        CASE upper(trim("Ownership"))
            WHEN 'OWNED' THEN 'Owned'
            WHEN 'OWN' THEN 'Owned'
            WHEN 'O' THEN 'Owned'
            WHEN 'RENTED' THEN 'Rented'
            WHEN 'RENT' THEN 'Rented'
            WHEN 'R' THEN 'Rented'
        END AS ownership,
        try_cast("Monthly_Rate" AS DECIMAL(18, 2)) AS monthly_rate,
        try_cast("Months_On_Job" AS DECIMAL(18, 2)) AS months_on_job,
        try_cast("Utilization" AS DOUBLE) AS utilization_raw,
        CASE
            WHEN try_cast("Utilization" AS DOUBLE) BETWEEN 0 AND 1
                THEN try_cast("Utilization" AS DOUBLE)
            WHEN try_cast("Utilization" AS DOUBLE) > 1
                AND try_cast("Utilization" AS DOUBLE) <= 100
                THEN try_cast("Utilization" AS DOUBLE) / 100.0
        END AS utilization,
        try_cast("Production_Units" AS DECIMAL(18, 2)) AS production_units,
        upper(trim(coalesce("Job", ''))) = 'JOB'
            OR upper(trim(coalesce("Job", ''))) LIKE 'TOTALS%'
            AS is_non_data_row,
        _source_file,
        _source_row,
        _record_hash
    FROM raw_equipment
),
resolved AS (
    SELECT
        parsed.*,
        CASE
            WHEN exact_job.job_id IS NOT NULL THEN exact_job.job_id
            WHEN right(normalized_job_reference, 1) = 'X'
                AND suffix_job.job_id IS NOT NULL THEN suffix_job.job_id
            ELSE normalized_job_reference
        END AS job_id,
        CASE
            WHEN exact_job.job_id IS NOT NULL THEN 'exact'
            WHEN right(normalized_job_reference, 1) = 'X'
                AND suffix_job.job_id IS NOT NULL THEN 'suffix_x'
            ELSE 'unresolved'
        END AS job_resolution_method
    FROM parsed
    LEFT JOIN stg_jobs AS exact_job
        ON parsed.normalized_job_reference = exact_job.job_id
    LEFT JOIN stg_jobs AS suffix_job
        ON right(parsed.normalized_job_reference, 1) = 'X'
        AND left(parsed.normalized_job_reference, length(parsed.normalized_job_reference) - 1)
            = suffix_job.job_id
),
typed AS (
    SELECT
        *,
        monthly_rate * months_on_job AS total_equipment_cost,
        CASE
            WHEN production_units > 0
                THEN (monthly_rate * months_on_job) / production_units
        END AS cost_per_production_unit,
        utilization_raw > 1 AND utilization_raw <= 100 AS is_utilization_scaled,
        utilization_raw IS NULL OR utilization_raw < 0 OR utilization_raw > 100
            AS is_utilization_invalid,
        ownership IS NULL AS is_ownership_invalid,
        monthly_rate IS NULL OR months_on_job IS NULL OR production_units IS NULL
            AS is_numeric_parse_error,
        job_resolution_method = 'suffix_x' AS is_job_suffix_corrected
    FROM resolved
    WHERE NOT is_non_data_row
)
SELECT
    typed.*,
    jobs.job_id IS NULL AS is_unknown_job,
    jobs.job_id IS NOT NULL
        AND NOT is_utilization_invalid
        AND NOT is_ownership_invalid
        AND NOT is_numeric_parse_error AS is_analysis_eligible
FROM typed
LEFT JOIN stg_jobs AS jobs USING (job_id);
