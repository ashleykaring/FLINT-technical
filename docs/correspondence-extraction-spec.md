# Correspondence extraction contract

## Objective

Convert each free-text RFI, change order, or field log into zero or more
evidence-backed events. The future LLM must extract stated facts; it must not
invent amounts, dates, entity matches, or business status.

One document may produce multiple events when it discusses unrelated issues.
Cost and schedule impacts caused by the same issue belong to one event.

## Event fields

| Field | Meaning |
|---|---|
| `event_index` | One-based event order within the document |
| `job_reference` | Exact job wording found in the text |
| `job_id` | Canonical ID from `entity_reference.csv`, or `null` |
| `subcontractor_reference` | Exact subcontractor wording found in the text |
| `subcontractor_id` | Canonical ID from `entity_reference.csv`, or `null` |
| `scope` | Work scope as written, without forcing a cost-code mapping |
| `event_type` | Primary event classification |
| `amount` | Numeric dollar magnitude; zero only for explicit no-impact language |
| `financial_impact_type` | Whether the amount is cost, contract value, variance, or backcharge |
| `amount_status` | Evidentiary state of the amount |
| `booking_status` | Whether the text says the amount is in the cost system |
| `schedule_impact_days` | Nonnegative day magnitude |
| `schedule_impact_type` | Delay, recovery, available float, none, or unknown |
| `approval_status` | Proposed/approval state stated in the document |
| `referenced_date` | Explicit date in ISO `YYYY-MM-DD` format |
| `date_context` | Meaning of that date, such as “response deadline” |
| `evidence_text` | Exact source span supporting the event |

The controlled values live in `pipeline/ai/schema.py`. These values will also
be used to constrain structured model output.

## Grounding rules

- Use only information stated in the document and supplied entity reference.
- Use `null` for an unstated value; do not make a plausible guess.
- Preserve written project and subcontractor references before resolving them.
- Do not translate a written scope into a canonical cost code during extraction.
- Treat contract-value changes separately from costs.
- Treat a budget overrun separately from a new cost estimate.
- Do not assume an amount is booked unless the document says so.
- “No cost impact” is an explicit zero. No mention of cost is unknown, not zero.
- A recovery is not a negative delay; record its positive magnitude with type
  `recovery`.
- Available float is not an incurred delay.
- Evidence must be copied exactly from the source text.

## Evaluation boundary

The gold set is for prompt/model evaluation and must never be included as
few-shot examples in the same evaluation request. Prompt examples should come
from documents outside the sampled evaluation population.
