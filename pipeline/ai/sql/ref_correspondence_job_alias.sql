CREATE OR REPLACE TABLE ref_correspondence_job_alias AS
WITH loaded AS (
    SELECT
        nullif(trim(job_alias), '') AS job_alias,
        nullif(trim(job_id), '') AS job_id,
        nullif(trim(resolution_basis), '') AS resolution_basis
    FROM read_csv(
        '{{correspondence_job_alias_map_path}}',
        header = true,
        all_varchar = true
    )
)
SELECT
    lower(regexp_replace(job_alias, '\s+', ' ', 'g')) AS job_alias_key,
    job_alias,
    job_id,
    resolution_basis
FROM loaded;
