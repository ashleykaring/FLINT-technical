CREATE OR REPLACE TABLE dim_cost_code AS
WITH estimate_codes AS (
    SELECT
        estimate_cost_code,
        min(description) AS canonical_description
    FROM stg_estimates
    GROUP BY estimate_cost_code
),
erp_mapping AS (
    SELECT
        estimate_cost_code,
        min(erp_cost_code) AS erp_cost_code,
        min(mapping_method) AS mapping_method
    FROM ref_cost_code_map
    WHERE mapping_status = 'mapped'
    GROUP BY estimate_cost_code
)
SELECT
    estimate_codes.estimate_cost_code AS cost_code_key,
    estimate_codes.estimate_cost_code,
    erp_mapping.erp_cost_code,
    estimate_codes.canonical_description,
    erp_mapping.mapping_method,
    false AS is_unknown
FROM estimate_codes
LEFT JOIN erp_mapping USING (estimate_cost_code)

UNION ALL

SELECT
    'UNMAPPED_COST_CODE' AS cost_code_key,
    cast(NULL AS VARCHAR) AS estimate_cost_code,
    cast(NULL AS VARCHAR) AS erp_cost_code,
    'Unknown / Unmapped Cost Code' AS canonical_description,
    'unmapped' AS mapping_method,
    true AS is_unknown;
