CREATE OR REPLACE TABLE stg_correspondence AS
WITH normalized AS (
    SELECT
        nullif(trim(doc_id), '') AS doc_id,
        upper(nullif(trim(doc_type), '')) AS doc_type,
        nullif(trim(text), '') AS text,
        raw_json,
        count(*) OVER (PARTITION BY upper(trim(doc_id))) AS duplicate_source_count,
        row_number() OVER (
            PARTITION BY upper(trim(doc_id))
            ORDER BY _source_row
        ) AS duplicate_rank,
        _source_file,
        _source_row,
        _record_hash
    FROM raw_correspondence
)
SELECT
    * EXCLUDE (duplicate_rank),
    duplicate_rank > 1 AS is_exact_duplicate,
    doc_id IS NOT NULL
        AND doc_type IN ('RFI', 'CO', 'LOG')
        AND text IS NOT NULL
        AND duplicate_rank = 1 AS is_valid
FROM normalized;
