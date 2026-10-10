CREATE OR REPLACE TABLE model_correspondence_reconciliation AS
WITH metrics AS (
    SELECT
        (SELECT count(*) FROM stg_correspondence WHERE is_valid) AS source_documents,
        (SELECT count(*) FROM ai_correspondence_extraction_current) AS current_documents,
        (
            SELECT coalesce(sum(json_array_length(extraction_json->'events')), 0)
            FROM ai_correspondence_extraction_current
        ) AS extracted_events,
        (SELECT count(*) FROM fact_correspondence_event_current) AS modeled_events,
        (
            SELECT count(*) - count(DISTINCT correspondence_event_key)
            FROM fact_correspondence_event_current
        ) AS duplicate_event_keys,
        (
            SELECT count(*) FROM fact_correspondence_event_current
            WHERE job_resolution_method = 'unresolved'
        ) AS unresolved_jobs,
        (
            SELECT count(*) FROM fact_correspondence_event_current
            WHERE subcontractor_resolution_method = 'unresolved'
        ) AS unresolved_subcontractors,
        (
            SELECT count(*) FROM fact_correspondence_event_current
            WHERE is_event_type_normalized
        ) AS normalized_event_types,
        (
            SELECT count(*) FROM fact_correspondence_event_current
            WHERE extracted_event_type = 'other'
              AND schedule_impact_days IS NOT NULL
              AND (amount IS NULL OR amount = 0)
              AND financial_impact_type IN ('none', 'unknown')
        ) AS extracted_schedule_only_other,
        (
            SELECT count(*) FROM fact_correspondence_event_current
            WHERE event_type = 'other'
              AND schedule_impact_days IS NOT NULL
              AND (amount IS NULL OR amount = 0)
              AND financial_impact_type IN ('none', 'unknown')
        ) AS remaining_schedule_only_other,
        (SELECT count(*) FROM correspondence_dq_issues) AS quality_issues
)
SELECT
    'document_coverage' AS check_name,
    source_documents AS expected_value,
    current_documents AS actual_value,
    source_documents = current_documents AS passed,
    'Every valid correspondence document has one current extraction' AS description
FROM metrics

UNION ALL

SELECT
    'event_row_reconciliation',
    extracted_events,
    modeled_events,
    extracted_events = modeled_events,
    'Structured event rows reconcile to current extraction JSON'
FROM metrics

UNION ALL

SELECT
    'unique_event_keys',
    0,
    duplicate_event_keys,
    duplicate_event_keys = 0,
    'Current correspondence event keys are unique'
FROM metrics

UNION ALL

SELECT
    'unresolved_job_references',
    0,
    unresolved_jobs,
    unresolved_jobs = 0,
    'Every copied job reference resolves to a canonical job ID'
FROM metrics

UNION ALL

SELECT
    'unresolved_subcontractor_references',
    0,
    unresolved_subcontractors,
    unresolved_subcontractors = 0,
    'Every copied subcontractor reference resolves to a canonical subcontractor ID'
FROM metrics

UNION ALL

SELECT
    'normalized_schedule_only_events',
    extracted_schedule_only_other,
    normalized_event_types,
    normalized_event_types = extracted_schedule_only_other,
    'Every extracted schedule-only other event was normalized deterministically'
FROM metrics

UNION ALL

SELECT
    'remaining_schedule_only_other_events',
    0,
    remaining_schedule_only_other,
    remaining_schedule_only_other = 0,
    'No schedule-only event remains classified as other'
FROM metrics

UNION ALL

SELECT
    'correspondence_quality_issues',
    0,
    quality_issues,
    quality_issues = 0,
    'The governed correspondence fact has no unresolved quality issues'
FROM metrics;
