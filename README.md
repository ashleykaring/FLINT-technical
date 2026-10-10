# FLINT Construction Data & Platform Engineering Assessment

This repository contains a reproducible data pipeline and application slice for
the FLINT construction portfolio case study.

## Current milestone: ingestion through governed correspondence events

The ingestion pipeline loads every supplied source into a local DuckDB database
without applying business-level cleaning. Source values are retained as strings
where practical so that formatting and data-quality problems remain visible to
the later staging layer.

The estimating API JSON is the canonical estimating source. Its flattened CSV
copy is also loaded and reconciled against the JSON during every ingestion run.

### Sources

| Source file | Raw table |
|---|---|
| `jobs_reference.csv` | `raw_jobs` |
| `estimates_budget_api.json` | `raw_estimate_api_projects`, `raw_estimate_api_line_items` |
| `estimates_budget.csv` | `raw_estimate_csv` |
| `job_cost_ledger.csv` | `raw_job_cost_ledger` |
| `schedule_activities.csv` | `raw_schedule_activities` |
| `equipment_rental_log.xlsx` | `raw_equipment` |
| `project_correspondence.jsonl` | `raw_correspondence` |

Every raw record includes its source file, source row, ingestion run, ingestion
timestamp, and a content fingerprint. The database also records run- and
source-level metadata in `meta_ingestion_runs` and `meta_ingestion_sources`.

### Staging model

The transformation layer converts raw strings into typed, analysis-ready
columns without silently discarding suspect records. Each staging table carries
explicit quality flags so downstream models can choose whether to include,
exclude, or quarantine a record.

| Staging table | Primary responsibility |
|---|---|
| `stg_jobs` | Canonical job identifiers and typed job attributes |
| `stg_estimates` | Typed original/current estimates and missing-value flags |
| `stg_job_cost_ledger` | Parsed transactions, canonical entities, duplicate flags, and cost-code mapping |
| `stg_schedule_activities` | Normalized percentages, dates, and sequence validation |
| `stg_equipment` | Valid spreadsheet rows, ownership normalization, job resolution, and unit economics |
| `stg_correspondence` | Structural document validation before AI extraction |

The governed `data/reference/cost_code_map.csv` bridge reconciles the legacy ERP
taxonomy to the estimating taxonomy. Unexpected code `99-999` is deliberately
retained as unmapped and reported as a quality issue.

### Dimensional model and marts

The model layer turns staging records into conformed job, cost-code, and
subcontractor dimensions plus cost, budget, schedule, and equipment facts.
Unknown members retain unresolved records and their dollars. Five
reconciliation checks make row and ledger-dollar preservation a build gate.

Dashboard-ready marts cover job financials, cost versus progress, equipment
economics, subcontractor exposure, cost-code exposure, and portfolio risk. See
[`docs/data-model.md`](docs/data-model.md) for grains and relationships and
[`docs/metric-definitions.md`](docs/metric-definitions.md) for formulas and
business assumptions.

## Setup

This project uses Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --dev
```

## Run ingestion

```powershell
uv run flint ingest
```

The default output is `warehouse/flint.duckdb`. To use a different location:

```powershell
uv run flint ingest --database path/to/flint.duckdb
```

Ingestion is idempotent: each run replaces the raw tables rather than appending
the same static extracts again. Previous run metadata remains available.

## Run transformations

After ingestion, build the typed staging layer and quality-issue table:

```powershell
uv run flint transform
```

To print the latest quality report without rebuilding tables:

```powershell
uv run flint quality
```

After transformation, build or rebuild the dimensional model and marts:

```powershell
uv run flint model
```

For a complete refresh, run the end-to-end command:

```powershell
uv run flint build
```

`build` runs ingestion, transformation, dimensional modeling, and quality
reporting. Every data-building stage is transactional and idempotent. Run
history is retained in `meta_ingestion_runs`, `meta_transformation_runs`, and
`meta_model_runs`.

The current source package produces 4,421 traceable quality issues:

| Severity | Rows | Examples |
|---|---:|---|
| Error | 432 | Missing ledger jobs, unmapped cost codes, reversed actual dates |
| Warning | 3,689 | Duplicate postings, missing current estimates, corrected aliases |
| Info | 300 | Normalized percentages and excluded spreadsheet headings |

These counts are regression-tested. A source change that alters them requires
review rather than silently changing the analytical population.

## Tests and linting

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Prepare correspondence evaluation labels

Create the deterministic 45-document evaluation sample before integrating an
LLM provider:

```powershell
uv run flint prepare-labels
uv run flint validate-labels
```

Complete `data/annotations/correspondence_gold.jsonl` using the adjacent
annotation README and entity reference. Preparation refuses to overwrite an
existing gold file unless `--force` is supplied.

## Run correspondence extraction

Set `GEMINI_API_KEY` in the shell, then start with one labeled document:

```powershell
uv run flint extract-correspondence --doc-id CO-2027
uv run flint evaluate-extraction
```

Responses are schema-validated, grounded against source text and canonical
entities, persisted to DuckDB, and cached by the complete prompt/model/schema
fingerprint. See [`docs/llm-integration.md`](docs/llm-integration.md) before
running more than one document.

After validating the labeled sample, process the full correspondence source in
quota-aware batches (1,200 documents become 12 model requests):

```powershell
uv run flint extract-correspondence --all --batch-size 100
```

After all documents are extracted, build the current, reconciled correspondence
fact without making any additional API calls:

```powershell
uv run flint model-correspondence
```

This selects one current extraction per document, applies reviewed job aliases,
normalizes deterministic schedule-only classifications, and fails atomically if
coverage, entity resolution, grounding, or event reconciliation is incomplete.
See [`docs/correspondence-model.md`](docs/correspondence-model.md).

## Repository layout

```text
app/                 React/TypeScript application (later milestone)
data/raw/            Immutable supplied extracts
data/reference/      Governed cross-system mappings
docs/                Data model, findings, and architecture documentation
pipeline/            Python ingestion, modeling, quality, and AI code
tests/               Automated tests
warehouse/           Generated local DuckDB database (not committed)
```
