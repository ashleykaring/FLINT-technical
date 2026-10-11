CREATE OR REPLACE TABLE analysis_dq_issues AS
SELECT
    'unmapped_correspondence_scope' AS issue_type,
    'error' AS severity,
    correspondence_event_key AS record_key,
    concat('Scope "', scope, '" could not be mapped for division ', division) AS detail
FROM mart_correspondence_exposure
WHERE scope IS NOT NULL AND cost_code_key IS NULL

UNION ALL

SELECT
    'orphan_correspondence_subcontractor',
    'error',
    exposure.correspondence_event_key,
    concat('Subcontractor key ', exposure.subcontractor_key, ' is absent from dimension')
FROM mart_correspondence_exposure AS exposure
LEFT JOIN dim_subcontractor AS subcontractors USING (subcontractor_key)
WHERE subcontractors.subcontractor_key IS NULL;
