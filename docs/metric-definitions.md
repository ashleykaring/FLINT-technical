# Metric definitions and assumptions

These definitions are the contract for the analytical marts and future
dashboard. Ratios are stored as decimal fractions: `0.15` means 15%.

| Metric | Definition | Notes |
|---|---|---|
| Current cost budget | Sum of current estimate, falling back to original estimate when current is missing | Fallback rows remain flagged |
| Adjusted actual cost | Actual postings + adjustment postings | Adjustments may be positive or negative |
| Forecast remaining | Sum of forecast postings | Treated as remaining cost, not cost already incurred |
| Projected final cost | Adjusted actual cost + forecast remaining | Commitments are shown separately to avoid possible overlap with forecast |
| Projected cost variance | Projected final cost - current cost budget | Positive is unfavorable |
| Estimate drift | Current cost budget - original cost budget | Positive means the estimate increased |
| Cost spent % | Adjusted actual cost / current cost budget | Null when no cost-budget denominator exists |
| Cost-progress variance | Cost spent % - reported job progress % | Positive means cost burn is ahead of reported progress |
| Projected margin | Contract value proxy - projected final cost | See contract-value assumption below |
| Projected margin % | Projected margin / contract value proxy | Null for a zero or missing proxy |
| Equipment cost per production unit | Total equipment cost / production units | Portfolio views use ratio-of-sums weighting |

## Material assumptions

The supplied job field named `original_budget` is used as a **contract value
proxy** because the extracts do not contain an explicit contract revenue/value
field. As a result, projected margin is provisional and must be relabeled or
recalculated if an authoritative contract-value source becomes available.

`COMMITTED` postings are not added to projected final cost. Construction ERP
commitments often overlap actuals or forecast, and the supplied data does not
identify the liquidated or forecast-covered portion. The mart surfaces
committed cost independently so this choice is auditable.

When `current_estimate` is absent, `original_estimate` becomes the current
budget basis. `used_original_estimate_fallback` and the job-level count
`missing_current_estimate_lines` disclose every fallback.

Exact ledger duplicates are identified in staging and represented once in the
fact table. Unknown job and unmapped cost-code postings remain in the facts
under explicit unknown members; they are not silently assigned to a known job
or discarded.

## Risk thresholds

Cost-versus-progress status uses cost-progress variance thresholds: critical at
20 percentage points, high at 10, watch at 5, and normal below 5. Missing budget
takes precedence.

Portfolio risk is critical for missing estimates, negative projected margin,
or cost-progress variance of at least 20 points. It is high for at least 10
points, estimate drift of at least 10%, or reversed actual schedule dates. It
is watch for at least 5 points, missing current-estimate lines, or unmapped cost
postings. The mart includes a human-readable `risk_reasons` field so every
classification can be explained.
