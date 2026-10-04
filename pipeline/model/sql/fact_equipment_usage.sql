CREATE OR REPLACE TABLE fact_equipment_usage AS
SELECT
    concat(_source_file, ':', cast(_source_row AS VARCHAR)) AS equipment_usage_key,
    CASE WHEN NOT is_unknown_job THEN job_id ELSE 'UNKNOWN_JOB' END AS job_key,
    equipment_type,
    ownership,
    monthly_rate,
    months_on_job,
    utilization,
    production_units,
    total_equipment_cost,
    cost_per_production_unit,
    job_resolution_method,
    is_job_suffix_corrected,
    is_utilization_scaled,
    is_analysis_eligible,
    _source_file,
    _source_row,
    _record_hash
FROM stg_equipment;
