CREATE OR REPLACE TABLE dim_subcontractor AS
WITH variants AS (
    SELECT
        staged.subcontractor_id,
        count(DISTINCT raw.subcontractor) AS source_variant_count
    FROM stg_job_cost_ledger AS staged
    JOIN raw_job_cost_ledger AS raw USING (_source_file, _source_row)
    WHERE staged.subcontractor_id IS NOT NULL
    GROUP BY staged.subcontractor_id
)
SELECT
    subcontractor_id AS subcontractor_key,
    subcontractor_id,
    subcontractor_id AS display_name,
    source_variant_count,
    false AS is_unknown
FROM variants

UNION ALL

SELECT
    'UNKNOWN_SUBCONTRACTOR' AS subcontractor_key,
    cast(NULL AS VARCHAR) AS subcontractor_id,
    'Unknown Subcontractor' AS display_name,
    0 AS source_variant_count,
    true AS is_unknown;
