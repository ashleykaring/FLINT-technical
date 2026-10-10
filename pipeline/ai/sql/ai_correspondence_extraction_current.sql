CREATE OR REPLACE TABLE ai_correspondence_extraction_current AS
WITH ranked AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY doc_id
            ORDER BY extracted_at DESC, cache_key DESC
        ) AS version_rank
    FROM ai_correspondence_extractions
    WHERE prompt_version = '{{prompt_version}}'
      AND schema_version = '{{schema_version}}'
)
SELECT * EXCLUDE (version_rank)
FROM ranked
WHERE version_rank = 1;
