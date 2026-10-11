CREATE OR REPLACE TABLE mart_correspondence_exposure AS
WITH normalized AS (
    SELECT
        events.*,
        jobs.division,
        jobs.contract_type,
        CASE
            WHEN events.scope IS NULL THEN NULL
            ELSE trim(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(lower(trim(events.scope)), '^acceleration of (the )?', ''),
                        '^the ',
                        ''
                    ),
                    ' spec$',
                    ''
                )
            )
        END AS normalized_scope
    FROM fact_correspondence_event_current AS events
    JOIN dim_job AS jobs USING (job_key)
),
classified AS (
    SELECT
        normalized.*,
        mapping.estimate_cost_code AS cost_code_key,
        codes.canonical_description AS cost_code_description,
        mapping.resolution_basis AS cost_code_resolution_basis,
        CASE
            WHEN event_type = 'change_order'
             AND financial_impact_type = 'cost'
             AND booking_status = 'not_booked'
             AND approval_status = 'authorized'
                THEN 'confirmed_unbooked_cost'
            WHEN event_type = 'change_order'
             AND financial_impact_type = 'contract_value'
             AND booking_status = 'not_booked'
                THEN 'unbooked_contract_value'
            WHEN event_type = 'change_order'
             AND financial_impact_type = 'cost'
             AND approval_status = 'pending'
                THEN 'pending_change_cost'
            WHEN event_type = 'potential_cost' THEN 'potential_cost'
            WHEN event_type = 'budget_variance' THEN 'budget_variance'
            WHEN event_type = 'backcharge' THEN 'disputed_backcharge_unquantified'
            WHEN event_type = 'schedule_risk' THEN 'schedule_only'
            ELSE 'other'
        END AS exposure_category
    FROM normalized
    LEFT JOIN ref_correspondence_scope_cost_code AS mapping
        ON normalized.normalized_scope = mapping.scope_key
       AND mapping.division IN ('ALL', normalized.division)
    LEFT JOIN dim_cost_code AS codes
        ON codes.cost_code_key = mapping.estimate_cost_code
)
SELECT
    *,
    CASE
        WHEN exposure_category = 'unbooked_contract_value' THEN coalesce(amount, 0)
        WHEN exposure_category = 'confirmed_unbooked_cost' THEN -coalesce(amount, 0)
        ELSE 0
    END AS confirmed_margin_adjustment,
    CASE
        WHEN exposure_category IN ('pending_change_cost', 'potential_cost')
            THEN coalesce(amount, 0)
        ELSE 0
    END AS potential_downside_amount,
    CASE
        WHEN exposure_category = 'budget_variance' THEN coalesce(amount, 0)
        ELSE 0
    END AS reported_budget_variance_amount
FROM classified;
