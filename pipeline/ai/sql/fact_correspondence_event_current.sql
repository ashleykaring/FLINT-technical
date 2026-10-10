CREATE OR REPLACE TABLE fact_correspondence_event_current AS
WITH resolved AS (
    SELECT
        f.correspondence_event_key AS source_correspondence_event_key,
        f.cache_key,
        f.doc_id,
        x.doc_type,
        f.event_index,
        f.job_reference,
        f.job_id AS extracted_job_id,
        coalesce(f.job_id, aliases.job_id) AS resolved_job_id,
        CASE
            WHEN f.job_id IS NOT NULL THEN 'model'
            WHEN aliases.job_id IS NOT NULL THEN 'alias_map'
            WHEN f.job_reference IS NULL THEN 'no_reference'
            ELSE 'unresolved'
        END AS job_resolution_method,
        f.subcontractor_reference,
        f.subcontractor_id,
        CASE
            WHEN f.subcontractor_id IS NOT NULL THEN 'model'
            WHEN f.subcontractor_reference IS NULL THEN 'no_reference'
            ELSE 'unresolved'
        END AS subcontractor_resolution_method,
        f.scope,
        f.event_type AS extracted_event_type,
        CASE
            WHEN f.event_type = 'other'
             AND f.schedule_impact_days IS NOT NULL
             AND (f.amount IS NULL OR f.amount = 0)
             AND f.financial_impact_type IN ('none', 'unknown')
                THEN 'schedule_risk'
            ELSE f.event_type
        END AS resolved_event_type,
        f.amount,
        f.financial_impact_type,
        f.amount_status,
        f.booking_status,
        f.schedule_impact_days,
        f.schedule_impact_type,
        f.approval_status,
        f.referenced_date,
        f.date_context,
        f.evidence_text,
        source.text AS source_document_text,
        source._source_file,
        source._source_row,
        x.provider,
        x.model AS extraction_model,
        x.prompt_version,
        x.schema_version,
        x.extracted_at
    FROM ai_correspondence_extraction_current AS x
    JOIN fact_correspondence_event AS f USING (cache_key, doc_id)
    LEFT JOIN ref_correspondence_job_alias AS aliases
        ON lower(regexp_replace(trim(f.job_reference), '\s+', ' ', 'g'))
            = aliases.job_alias_key
    LEFT JOIN stg_correspondence AS source
        ON source.doc_id = f.doc_id AND source.is_valid
)
SELECT
    concat(doc_id, ':', event_index) AS correspondence_event_key,
    source_correspondence_event_key,
    cache_key,
    doc_id,
    doc_type,
    event_index,
    job_reference,
    extracted_job_id,
    resolved_job_id AS job_id,
    coalesce(resolved_job_id, 'UNKNOWN_JOB') AS job_key,
    job_resolution_method,
    job_resolution_method = 'alias_map' AS is_job_alias_resolved,
    subcontractor_reference,
    subcontractor_id,
    coalesce(subcontractor_id, 'UNKNOWN_SUBCONTRACTOR') AS subcontractor_key,
    subcontractor_resolution_method,
    scope,
    extracted_event_type,
    resolved_event_type AS event_type,
    extracted_event_type != resolved_event_type AS is_event_type_normalized,
    amount,
    financial_impact_type,
    amount_status,
    booking_status,
    schedule_impact_days,
    schedule_impact_type,
    approval_status,
    referenced_date,
    date_context,
    evidence_text,
    evidence_text = source_document_text AS uses_full_document_evidence,
    source_document_text,
    provider,
    extraction_model,
    prompt_version,
    schema_version,
    extracted_at,
    _source_file,
    _source_row
FROM resolved;
