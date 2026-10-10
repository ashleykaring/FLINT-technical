# Manual correspondence labeling

Edit only `correspondence_gold.jsonl`. The other files are generated reference
material:

- `correspondence_sample.jsonl` is the immutable 45-document sample.
- `entity_reference.csv` lists allowed canonical job and subcontractor IDs.
- `correspondence_gold.jsonl` is the file you complete.

Each physical line is one complete JSON object. Keep every object on one line.
Do not edit `doc_id`, `doc_type`, or `text`.

For each document:

1. Read the entire `text` value.
2. Add one event object per distinct issue, using the template below.
3. Copy entity references and evidence exactly from the text.
4. Resolve IDs only when supported by `entity_reference.csv`; otherwise use
   `null`.
5. Use numbers without dollar signs or commas.
6. Use `null` for information that is not stated.
7. Use an empty `events` list when no cost or schedule event is present.
8. Change `review_status` from `todo` to `complete`. Use `needs_review` when a
   business interpretation needs discussion.

```json
{
  "event_index": 1,
  "job_reference": null,
  "job_id": null,
  "subcontractor_reference": null,
  "subcontractor_id": null,
  "scope": null,
  "event_type": "other",
  "amount": null,
  "financial_impact_type": "unknown",
  "amount_status": "unknown",
  "booking_status": "unknown",
  "schedule_impact_days": null,
  "schedule_impact_type": "unknown",
  "approval_status": "unknown",
  "referenced_date": null,
  "date_context": null,
  "evidence_text": "exact supporting text"
}
```

Allowed values and interpretation rules are documented in
`docs/correspondence-extraction-spec.md`. Validate after every few documents:

```powershell
uv run flint validate-labels
```

Never run `uv run flint prepare-labels --force` after manual work begins. The
force option intentionally replaces the gold file.
