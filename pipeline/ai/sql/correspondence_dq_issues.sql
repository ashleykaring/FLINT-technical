CREATE OR REPLACE TABLE correspondence_dq_issues AS
SELECT
    concat('unresolved_job_reference:', correspondence_event_key) AS issue_key,
    'unresolved_job_reference' AS check_name,
    'error' AS severity,
    correspondence_event_key,
    doc_id,
    concat('Job reference ', job_reference, ' has no canonical job ID') AS description
FROM fact_correspondence_event_current
WHERE job_resolution_method = 'unresolved'

UNION ALL

SELECT
    concat('unresolved_subcontractor_reference:', correspondence_event_key),
    'unresolved_subcontractor_reference',
    'error',
    correspondence_event_key,
    doc_id,
    concat(
        'Subcontractor reference ', subcontractor_reference,
        ' has no canonical subcontractor ID'
    )
FROM fact_correspondence_event_current
WHERE subcontractor_resolution_method = 'unresolved'

UNION ALL

SELECT
    concat('unknown_job_dimension_key:', correspondence_event_key),
    'unknown_job_dimension_key',
    'error',
    correspondence_event_key,
    doc_id,
    concat('Job key ', job_key, ' is absent from dim_job')
FROM fact_correspondence_event_current AS events
WHERE NOT EXISTS (
    SELECT 1 FROM dim_job AS jobs WHERE jobs.job_key = events.job_key
)

UNION ALL

SELECT
    concat('unknown_subcontractor_dimension_key:', correspondence_event_key),
    'unknown_subcontractor_dimension_key',
    'error',
    correspondence_event_key,
    doc_id,
    concat('Subcontractor key ', subcontractor_key, ' is absent from dim_subcontractor')
FROM fact_correspondence_event_current AS events
WHERE NOT EXISTS (
    SELECT 1
    FROM dim_subcontractor AS subcontractors
    WHERE subcontractors.subcontractor_key = events.subcontractor_key
)

UNION ALL

SELECT
    concat('ungrounded_evidence:', correspondence_event_key),
    'ungrounded_evidence',
    'error',
    correspondence_event_key,
    doc_id,
    'Evidence text is not an exact span of the source document'
FROM fact_correspondence_event_current
WHERE evidence_text IS NULL
   OR source_document_text IS NULL
   OR position(evidence_text IN source_document_text) = 0

UNION ALL

SELECT
    concat('ungrounded_entity_or_scope:', correspondence_event_key),
    'ungrounded_entity_or_scope',
    'error',
    correspondence_event_key,
    doc_id,
    'A copied job, subcontractor, or scope value is absent from the source document'
FROM fact_correspondence_event_current
WHERE (job_reference IS NOT NULL AND position(job_reference IN source_document_text) = 0)
   OR (
       subcontractor_reference IS NOT NULL
       AND position(subcontractor_reference IN source_document_text) = 0
   )
   OR (scope IS NOT NULL AND position(scope IN source_document_text) = 0)

UNION ALL

SELECT
    concat('schedule_only_other_event:', correspondence_event_key),
    'schedule_only_other_event',
    'error',
    correspondence_event_key,
    doc_id,
    'Schedule-only event remains classified as other after normalization'
FROM fact_correspondence_event_current
WHERE event_type = 'other'
  AND schedule_impact_days IS NOT NULL
  AND (amount IS NULL OR amount = 0)
  AND financial_impact_type IN ('none', 'unknown')

UNION ALL

SELECT
    concat('invalid_event_magnitude:', correspondence_event_key),
    'invalid_event_magnitude',
    'error',
    correspondence_event_key,
    doc_id,
    'Event contains a negative financial or schedule magnitude'
FROM fact_correspondence_event_current
WHERE amount < 0 OR schedule_impact_days < 0;
