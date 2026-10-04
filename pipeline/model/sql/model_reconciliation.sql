CREATE OR REPLACE TABLE model_reconciliation AS
SELECT
    *,
    source_rows - excluded_rows = modeled_rows
        AND (amount_difference IS NULL OR abs(amount_difference) < 0.01) AS passed
FROM (
WITH ledger AS (
    SELECT
        count(*) AS source_rows,
        count(*) FILTER (WHERE is_exact_duplicate) AS excluded_rows,
        sum(amount) AS source_amount,
        sum(amount) FILTER (WHERE is_exact_duplicate) AS excluded_amount
    FROM stg_job_cost_ledger
),
ledger_fact AS (
    SELECT count(*) AS modeled_rows, sum(amount) AS modeled_amount
    FROM fact_cost_transaction
)
SELECT
    'jobs_row_reconciliation' AS check_name,
    (SELECT count(*) FROM raw_jobs) AS source_rows,
    (SELECT count(*) FROM raw_jobs) - (SELECT count(*) FROM stg_jobs) AS excluded_rows,
    (SELECT count(*) FROM dim_job WHERE NOT is_unknown) AS modeled_rows,
    cast(NULL AS DECIMAL(24, 4)) AS source_amount,
    cast(NULL AS DECIMAL(24, 4)) AS excluded_amount,
    cast(NULL AS DECIMAL(24, 4)) AS modeled_amount,
    cast(NULL AS DECIMAL(24, 4)) AS amount_difference

UNION ALL

SELECT
    'budget_row_reconciliation',
    (SELECT count(*) FROM stg_estimates),
    0,
    (SELECT count(*) FROM fact_budget),
    NULL,
    NULL,
    NULL,
    NULL

UNION ALL

SELECT
    'ledger_row_and_amount_reconciliation',
    ledger.source_rows,
    ledger.excluded_rows,
    ledger_fact.modeled_rows,
    ledger.source_amount,
    coalesce(ledger.excluded_amount, 0),
    ledger_fact.modeled_amount,
    ledger.source_amount - coalesce(ledger.excluded_amount, 0) - ledger_fact.modeled_amount
FROM ledger
CROSS JOIN ledger_fact

UNION ALL

SELECT
    'schedule_row_reconciliation',
    (SELECT count(*) FROM stg_schedule_activities),
    0,
    (SELECT count(*) FROM fact_schedule_activity),
    NULL,
    NULL,
    NULL,
    NULL

UNION ALL

SELECT
    'equipment_row_reconciliation',
    (SELECT count(*) FROM raw_equipment),
    (SELECT count(*) FROM raw_equipment) - (SELECT count(*) FROM stg_equipment),
    (SELECT count(*) FROM fact_equipment_usage),
    NULL,
    NULL,
    NULL,
    NULL
) AS reconciled;
