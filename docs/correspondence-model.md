# Governed correspondence model

The post-extraction correspondence model is built with:

```powershell
uv run flint model-correspondence
```

It is intentionally separate from `flint build`: ingestion, transformation,
and the base dimensional model can run without an API key, while this model
requires completed correspondence extraction.

## Outputs

| Table | Grain and purpose |
|---|---|
| `ref_correspondence_job_alias` | One reviewed shorthand-to-job mapping |
| `ai_correspondence_extraction_current` | One current extraction per source document |
| `fact_correspondence_event_current` | One cleaned current cost or schedule event |
| `correspondence_dq_issues` | Row-level unresolved grounding, entity, and semantic issues |
| `model_correspondence_reconciliation` | Build-gating coverage and integrity checks |

Current extraction selection is restricted to the configured prompt and schema
versions, then chooses the latest response per document. Historical prompt/model
responses remain in the raw AI tables for auditability but cannot enter the
current fact or be double counted.

## Deterministic cleanup

The model preserves model-produced values alongside governed corrections:

- `extracted_job_id` retains the model output; `job_id` applies reviewed aliases
  from `data/reference/correspondence_job_alias_map.csv` when needed.
- `extracted_event_type` retains the model output; `event_type` converts an
  `other` event to `schedule_risk` only when it has schedule days and no positive
  or classified financial impact.
- `job_resolution_method`, `is_job_alias_resolved`, and
  `is_event_type_normalized` expose every correction.
- Evidence, copied references, and scope remain exact source spans.

## Build gates

The transaction is rolled back unless all checks pass:

1. Every valid source document has one current extraction.
2. Event rows reconcile to the event arrays in current extraction JSON.
3. Stable current event keys are unique.
4. All copied job and subcontractor references resolve.
5. Every schedule-only `other` event is normalized.
6. No grounding, relationship, magnitude, or other row-level issue remains.

The completed source currently produces 1,200 current extractions and 1,307
current events, with 17 reviewed job-alias resolutions and 24 deterministic
event-type normalizations.
