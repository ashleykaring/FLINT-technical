from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class DataQualityCheck:
    name: str
    source_table: str
    severity: str
    query: str


CHECKS = (
    DataQualityCheck(
        name="duplicate_job_id",
        source_table="stg_jobs",
        severity="warning",
        query="""
            SELECT
                job_id AS record_key,
                concat('Canonical job has ', duplicate_source_count, ' source rows') AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_jobs
            WHERE is_duplicate_source
        """,
    ),
    DataQualityCheck(
        name="missing_current_estimate",
        source_table="stg_estimates",
        severity="warning",
        query="""
            SELECT
                concat(job_id, ':', estimate_cost_code) AS record_key,
                'Current estimate is missing; original estimate remains available' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_estimates
            WHERE is_current_estimate_missing
        """,
    ),
    DataQualityCheck(
        name="job_missing_estimate",
        source_table="stg_jobs",
        severity="error",
        query="""
            SELECT
                jobs.job_id AS record_key,
                'Job has no estimating-system line items' AS description,
                jobs._source_file AS source_file,
                jobs._source_row AS source_row
            FROM stg_jobs AS jobs
            WHERE NOT EXISTS (
                SELECT 1
                FROM stg_estimates AS estimates
                WHERE estimates.job_id = jobs.job_id
            )
        """,
    ),
    DataQualityCheck(
        name="duplicate_ledger_posting",
        source_table="stg_job_cost_ledger",
        severity="warning",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                concat('Exact posting fingerprint occurs ', duplicate_source_count, ' times')
                    AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_job_cost_ledger
            WHERE is_exact_duplicate
        """,
    ),
    DataQualityCheck(
        name="missing_ledger_job",
        source_table="stg_job_cost_ledger",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                'Ledger posting has no job identifier' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_job_cost_ledger
            WHERE is_missing_job_id
        """,
    ),
    DataQualityCheck(
        name="unknown_ledger_job",
        source_table="stg_job_cost_ledger",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                concat('Ledger job ', job_id, ' is absent from the job dimension') AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_job_cost_ledger
            WHERE is_unknown_job
        """,
    ),
    DataQualityCheck(
        name="unmapped_ledger_cost_code",
        source_table="stg_job_cost_ledger",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                concat('ERP cost code ', coalesce(erp_cost_code, '<missing>'), ' is not mapped')
                    AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_job_cost_ledger
            WHERE is_unmapped_cost_code
        """,
    ),
    DataQualityCheck(
        name="ledger_amount_parse_error",
        source_table="stg_job_cost_ledger",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                'Ledger amount could not be parsed' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_job_cost_ledger
            WHERE is_amount_parse_error
        """,
    ),
    DataQualityCheck(
        name="ledger_period_parse_error",
        source_table="stg_job_cost_ledger",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                'Ledger period could not be parsed' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_job_cost_ledger
            WHERE is_period_parse_error
        """,
    ),
    DataQualityCheck(
        name="schedule_percentage_scaled",
        source_table="stg_schedule_activities",
        severity="info",
        query="""
            SELECT
                activity_id AS record_key,
                concat('Whole-number percentage ', pct_complete_raw, ' was divided by 100')
                    AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_schedule_activities
            WHERE is_percentage_scaled
        """,
    ),
    DataQualityCheck(
        name="schedule_percentage_invalid",
        source_table="stg_schedule_activities",
        severity="error",
        query="""
            SELECT
                activity_id AS record_key,
                'Schedule percentage is missing or outside the supported range' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_schedule_activities
            WHERE is_percentage_invalid
        """,
    ),
    DataQualityCheck(
        name="schedule_baseline_dates_invalid",
        source_table="stg_schedule_activities",
        severity="error",
        query="""
            SELECT
                activity_id AS record_key,
                'Baseline dates are missing or finish precedes start' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_schedule_activities
            WHERE is_baseline_date_invalid
        """,
    ),
    DataQualityCheck(
        name="actual_finish_before_start",
        source_table="stg_schedule_activities",
        severity="error",
        query="""
            SELECT
                activity_id AS record_key,
                'Actual finish precedes actual start' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_schedule_activities
            WHERE is_actual_finish_before_start
        """,
    ),
    DataQualityCheck(
        name="equipment_non_data_row",
        source_table="raw_equipment",
        severity="info",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                'Spreadsheet header or totals row was excluded from staging' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM raw_equipment
            WHERE upper(trim(coalesce("Job", ''))) = 'JOB'
               OR upper(trim(coalesce("Job", ''))) LIKE 'TOTALS%'
        """,
    ),
    DataQualityCheck(
        name="equipment_job_suffix_corrected",
        source_table="stg_equipment",
        severity="warning",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                concat('Resolved job alias ', source_job_reference, ' to ', job_id) AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_equipment
            WHERE is_job_suffix_corrected
        """,
    ),
    DataQualityCheck(
        name="unknown_equipment_job",
        source_table="stg_equipment",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                concat('Equipment job ', source_job_reference, ' could not be resolved')
                    AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_equipment
            WHERE is_unknown_job
        """,
    ),
    DataQualityCheck(
        name="equipment_value_invalid",
        source_table="stg_equipment",
        severity="error",
        query="""
            SELECT
                cast(_source_row AS VARCHAR) AS record_key,
                'Equipment ownership, utilization, or numeric value is invalid' AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_equipment
            WHERE is_ownership_invalid OR is_utilization_invalid OR is_numeric_parse_error
        """,
    ),
    DataQualityCheck(
        name="duplicate_correspondence_id",
        source_table="stg_correspondence",
        severity="warning",
        query="""
            SELECT
                doc_id AS record_key,
                concat(
                    'Document identifier occurs ', duplicate_source_count, ' times'
                ) AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_correspondence
            WHERE is_exact_duplicate
        """,
    ),
    DataQualityCheck(
        name="invalid_correspondence_record",
        source_table="stg_correspondence",
        severity="error",
        query="""
            SELECT
                coalesce(doc_id, cast(_source_row AS VARCHAR)) AS record_key,
                'Correspondence record has an invalid identifier, type, or text value'
                    AS description,
                _source_file AS source_file,
                _source_row AS source_row
            FROM stg_correspondence
            WHERE NOT is_valid
        """,
    ),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_quality_issues(connection: duckdb.DuckDBPyConnection) -> int:
    selects = []
    for check in CHECKS:
        selects.append(
            f"""
            SELECT
                {_sql_literal(check.name)} AS check_name,
                {_sql_literal(check.source_table)} AS source_table,
                {_sql_literal(check.severity)} AS severity,
                cast(record_key AS VARCHAR) AS record_key,
                cast(description AS VARCHAR) AS description,
                cast(source_file AS VARCHAR) AS source_file,
                cast(source_row AS BIGINT) AS source_row
            FROM ({check.query}) AS issues
            """
        )

    connection.execute("CREATE OR REPLACE TABLE dq_issues AS " + " UNION ALL ".join(selects))
    return connection.execute("SELECT count(*) FROM dq_issues").fetchone()[0]
