from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceContract:
    """Expected physical shape of a supplied source file."""

    name: str
    filename: str
    table_name: str
    columns: tuple[str, ...]


JOBS = SourceContract(
    name="jobs_reference",
    filename="jobs_reference.csv",
    table_name="raw_jobs",
    columns=(
        "job_id",
        "division",
        "contract_type",
        "original_budget",
        "start_date",
        "planned_days",
        "pct_complete",
        "pm",
    ),
)

ESTIMATE_CSV = SourceContract(
    name="estimates_budget_csv",
    filename="estimates_budget.csv",
    table_name="raw_estimate_csv",
    columns=(
        "project",
        "est_cost_code",
        "description",
        "original_estimate",
        "current_estimate",
    ),
)

LEDGER = SourceContract(
    name="job_cost_ledger",
    filename="job_cost_ledger.csv",
    table_name="raw_job_cost_ledger",
    columns=(
        "job_id",
        "cost_code",
        "period",
        "subcontractor",
        "txn_type",
        "amount",
        "uom",
        "quantity",
    ),
)

SCHEDULE = SourceContract(
    name="schedule_activities",
    filename="schedule_activities.csv",
    table_name="raw_schedule_activities",
    columns=(
        "wbs",
        "activity_id",
        "activity_name",
        "baseline_start",
        "baseline_finish",
        "actual_start",
        "actual_finish",
        "pct_complete",
    ),
)

EQUIPMENT = SourceContract(
    name="equipment_rental_log",
    filename="equipment_rental_log.xlsx",
    table_name="raw_equipment",
    columns=(
        "Job",
        "Equip_Type",
        "Ownership",
        "Monthly_Rate",
        "Months_On_Job",
        "Utilization",
        "Production_Units",
    ),
)

CORRESPONDENCE = SourceContract(
    name="project_correspondence",
    filename="project_correspondence.jsonl",
    table_name="raw_correspondence",
    columns=("doc_id", "doc_type", "text"),
)

ESTIMATE_API_FILENAME = "estimates_budget_api.json"

CSV_CONTRACTS = (JOBS, ESTIMATE_CSV, LEDGER, SCHEDULE)

ALL_SOURCE_FILENAMES = (
    JOBS.filename,
    ESTIMATE_API_FILENAME,
    ESTIMATE_CSV.filename,
    LEDGER.filename,
    SCHEDULE.filename,
    EQUIPMENT.filename,
    CORRESPONDENCE.filename,
)
