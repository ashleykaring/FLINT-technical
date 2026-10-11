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

## Correspondence measures

Correspondence `amount` is an extracted event magnitude, not automatically an
additive portfolio cost. Change orders, potential costs, budget variances, and
backcharges represent different commercial concepts or lifecycle stages and may
overlap. Analysis must aggregate them separately unless an explicit de-duplication
or lifecycle rule justifies combination.

Schedule-impact days are also event-level magnitudes. Multiple documents may
describe the same underlying condition, so portfolio reporting surfaces counts,
maximum exposure, and categorized events before treating day values as additive.

The governed fact retains `booking_status`, `amount_status`, and
`approval_status`; these fields determine whether an amount is recorded,
provisional, or approved and must not be collapsed into a single committed-cost
measure without a documented business rule.

### Risk-adjusted scenarios

| Measure | Formula | Interpretation |
|---|---|---|
| Confirmed unbooked cost | Authorized, not-booked change-order cost | Cost likely to enter the system |
| Unbooked contract value | Not-booked change-order contract value | Revenue proxy adjustment; still subject to the contract-value caveat |
| Confirmed adjusted margin | Base projected margin + unbooked contract value - confirmed unbooked cost | Most supportable correspondence adjustment |
| Potential downside cost | Pending change-order cost + RFI potential cost | Scenario amount, not a booked forecast |
| Downside scenario margin | Confirmed adjusted margin - potential downside cost | Deliberately conservative scenario |
| Reported budget variance | Budget-variance log amount | Warning measure only; excluded from scenario arithmetic to avoid overlap |

Backcharges have no supplied amount and are reported as event counts. Schedule
days are summarized using event count and maximum stated delay/recovery; they
are not summed because multiple documents may refer to the same condition.

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

The combined dashboard status retains the base portfolio status. It also marks
a job high when confirmed unbooked cost is at least 5% of current cost budget or
maximum reported delay is at least 15 days, and watch when any pending/potential
cost, budget variance, or schedule event exists. A negative downside-scenario
margin is critical. `combined_risk_reasons` exposes every triggered condition.
