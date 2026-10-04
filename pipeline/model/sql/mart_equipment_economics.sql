CREATE OR REPLACE TABLE mart_equipment_economics AS
SELECT
    jobs.division,
    equipment.ownership,
    count(*) AS assignment_count,
    count(DISTINCT equipment.job_key) AS job_count,
    sum(equipment.total_equipment_cost) AS total_equipment_cost,
    sum(equipment.production_units) AS total_production_units,
    sum(equipment.total_equipment_cost) / nullif(sum(equipment.production_units), 0)
        AS weighted_cost_per_production_unit,
    avg(equipment.cost_per_production_unit) AS mean_assignment_cost_per_unit,
    avg(equipment.utilization) AS average_utilization
FROM fact_equipment_usage AS equipment
JOIN dim_job AS jobs USING (job_key)
WHERE NOT jobs.is_unknown
GROUP BY jobs.division, equipment.ownership;
