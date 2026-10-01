# Construction Portfolio Dataset — Candidate Package

Four extracts from four different systems at a mid-sized general contractor.
These are raw exports. Treat them as you would real client data: **inspect,
validate, and clean before you trust anything.** The systems were not designed
to talk to each other, so keys and taxonomies will not line up cleanly.

## Files

| File | Source system | Notes |
|---|---|---|
| `job_cost_ledger.csv` | On-prem construction ERP | Transaction-grain cost postings (~360k rows). The large one. |
| `estimates_budget_api.json` | SaaS estimating tool (API pull) | Original & current budget by project/line. `estimates_budget.csv` is the same data flattened. |
| `schedule_activities.csv` | Primavera P6 / MS Project export | Activity baseline vs. actual dates and % complete. |
| `equipment_rental_log.xlsx` | Ops manager's desktop spreadsheet | Owned & rented equipment, rates, utilization. |
| `project_correspondence.jsonl` | Document-management / PM system | ~1,200 free-text RFIs, change orders, and field logs. Unstructured. |
| `jobs_reference.csv` | ERP job dimension | Job → division / contract type / budget / % complete. |

## Columns (as exported)

**job_cost_ledger.csv** — `job_id, cost_code, period, subcontractor, txn_type, amount, uom, quantity`
`txn_type` ∈ {Actual, Committed, Forecast, Adjustment}.

**estimates_budget_api.json** — `project_id` → `line_items[]` of
`{cost_code, description, original_estimate, current_estimate}`.

**schedule_activities.csv** — `wbs, activity_id, activity_name, baseline_start, baseline_finish, actual_start, actual_finish, pct_complete`

**equipment_rental_log.xlsx** — `Job, Equip_Type, Ownership, Monthly_Rate, Months_On_Job, Utilization, Production_Units`

**jobs_reference.csv** — `job_id, division, contract_type, original_budget, start_date, planned_days, pct_complete, pm`

**project_correspondence.jsonl** — one JSON object per line: `{doc_id, doc_type, text}` where
`doc_type` ∈ {RFI, CO, LOG}. Everything else — which job, which cost code, which
subcontractor, the dollar impact, the schedule delay — lives inside the free-text
`text` field, written inconsistently. Some change orders describe cost that is **not yet
booked** to the ledger. You will need to extract this into structured form (an LLM is the
intended tool) and resolve the job/subcontractor references back to canonical IDs before
you can join it to the rest of the model.

## What you're asked to do

See the case study instructions document. In short: clean and model the data,
answer the analytical questions, build a Python pipeline + a small TypeScript
app slice + a grounded AI component, and present portfolio risk and your
architecture recommendation to leadership.

> The cost-code taxonomy in the estimating tool is **not** the same as the ERP's.
> Reconciling them is part of the exercise.
