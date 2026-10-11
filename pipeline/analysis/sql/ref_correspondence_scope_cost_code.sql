CREATE OR REPLACE TABLE ref_correspondence_scope_cost_code AS
SELECT
    lower(trim(scope_key)) AS scope_key,
    trim(division) AS division,
    trim(estimate_cost_code) AS estimate_cost_code,
    trim(resolution_basis) AS resolution_basis
FROM read_csv(
    '{{correspondence_scope_cost_code_map_path}}',
    header = true,
    all_varchar = true
);
