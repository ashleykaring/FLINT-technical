CREATE OR REPLACE TABLE ref_cost_code_map AS
SELECT
    trim(erp_cost_code) AS erp_cost_code,
    nullif(trim(estimate_cost_code), '') AS estimate_cost_code,
    trim(canonical_description) AS canonical_description,
    trim(mapping_method) AS mapping_method,
    trim(mapping_status) AS mapping_status
FROM read_csv(
    '{{cost_code_map_path}}',
    header = true,
    all_varchar = true
);
