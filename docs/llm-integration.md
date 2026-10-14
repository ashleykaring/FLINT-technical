# Gemini correspondence extraction

The extraction layer uses the official Google Gen AI Python SDK with a
Pydantic response schema. Gold labels are used only after inference for
evaluation; they are never placed in the model prompt.

The active prompt is `correspondence-v3`. Earlier prompt versions remain in the
repository so prior cached runs and evaluation results retain clear provenance.

Version 3 tightens the event boundary for related RFI cost and schedule impacts,
requires explicit language for approval states, and prevents a bare positive-day
"schedule impact" from being inferred as a delay.

After model validation, deterministic guardrails enforce the two source-explicit
semantics that should not depend on model judgment: a bare "schedule impact N
days" has unknown direction, and pending/not-applicable approval states require
supporting approval language. These semantics are versioned as
`correspondence-event-v2`, so older cached outputs are not reused.

Evidence must be an exact source span. When the provider paraphrases its evidence
citation, the pipeline safely substitutes the complete immutable correspondence
record rather than accepting ungrounded text or failing an otherwise valid event.

## Configuration

Set the key in the current PowerShell session without adding it to the
repository:

```powershell
$env:GEMINI_API_KEY = "your-key"
```

Optionally select a different accessible structured-output model:

```powershell
$env:GEMINI_MODEL = "gemini-3.8-flash"
```

If both `GOOGLE_API_KEY` and `GEMINI_API_KEY` exist, the pipeline stops rather
than relying on ambiguous credential precedence.

## Safe rollout

Run one document first:

```powershell
uv run flint extract-correspondence --doc-id CO-2027
uv run flint evaluate-extraction
```

After reviewing that result, run the completed gold documents together in one
request:

```powershell
uv run flint extract-correspondence --gold-complete
uv run flint evaluate-extraction
```

Successful responses are cached using a fingerprint of the provider, model,
prompt, schema, entity reference, and source document. Repeating a command does
not call Gemini again unless `--force` is supplied.

## Quota-safe batch extraction

The source contains 1,200 correspondence documents. The production path bundles
up to 100 documents in each model request while validating, storing, and caching
every document separately:

```powershell
uv run flint extract-correspondence --all --batch-size 100
```

With an empty cache, that command requires 12 API requests. The CLI refuses to
start a run requiring more than the default 20-request budget. Requests are
spaced at least 15 seconds apart, and provider-level automatic retries are
disabled so a temporary 429 or 503 cannot silently consume several requests.
The run also stops after the first failed batch instead of spending requests on
later batches. Rerun the same command after a transient failure; successful
documents are read from the cache and only missing documents are submitted.

Preview the exact cache and request plan without contacting Gemini:

```powershell
uv run flint extract-correspondence --all --batch-size 100 --dry-run
```

Useful safeguards can be adjusted explicitly:

```powershell
uv run flint extract-correspondence --all `
  --batch-size 100 `
  --request-interval-seconds 15 `
  --request-budget 20
```

Use `--limit` for a staged rollout, for example `--all --limit 100`. Batch size
is capped at 100 to limit response size and failure blast radius.

## Persistence

- `meta_ai_extraction_runs` records each extraction run.
- `ai_correspondence_extractions` stores version and token metadata plus JSON.
- `fact_correspondence_event` stores typed event rows for analysis.
- `ai_extraction_failures` records provider or grounding failures.
- `artifacts/llm/raw_responses/` stores ignored raw responses for debugging.

Every model response is validated against the Pydantic contract and then
checked for exact evidence spans and allowed canonical entity IDs before it is
accepted.

After full extraction, run `uv run flint model-correspondence`. This builds the
single-current-version fact, applies governed deterministic cleanup, and gates
the result with coverage, reconciliation, entity-resolution, and grounding
checks. Historical raw responses remain available for provenance but are not
included in analysis.

## Selected-job question answering

The job-detail page includes a deliberately small optional AI feature. A single
question is posted to `POST /api/jobs/{job_id}/ask`; the Python service retrieves
the governed job detail and job-filtered equipment packet, labels the financial,
cost-code, schedule, equipment, correspondence, and subcontractor sections, and
sends only that context to Gemini. The model returns a typed answer, two to four
supporting facts with source-section labels, and an optional caveat.

The API key remains server-side. The prompt treats correspondence text as
untrusted data, prohibits outside facts and generated SQL, defines the financial
scenario terms, and requires an explicit insufficient-data response when the
packet cannot answer a question. This prototype is single-turn and intentionally
has no history, persistence, caching, embeddings, or autonomous tools.

Set `GEMINI_QA_MODEL` to choose a separate question-answering model. It defaults
to `gemini-3.5-flash-lite`, makes one request per submitted question, and retries
once only for temporary 408/5xx provider failures. It does not retry quota 429s.
