# Initial portfolio findings

These findings answer the case-study questions from the current local extracts.
They are reproducible from the DuckDB marts with `uv run flint analyze`. Dollar
values are rounded for readability; the tables retain full precision.

## Executive readout

The supplied portfolio has a broad baseline cost problem, not a concentrated
outlier problem. Projected final cost is **$1.616B** against a current cost
budget of **$1.127B**. The positive projected cost variance totals **$401.8M**;
19 jobs are required to reach 80% of that exposure, while the top five account
for 37.5%. This argues for portfolio-wide controls plus focused review of the
largest jobs rather than treating one project as the sole cause.

All 42 jobs show negative base projected margin under the supplied
`original_budget` contract-value proxy. Base portfolio margin is **-$674.1M**.
Because no authoritative contract revenue field was supplied, this is an
important decision-use caveat: the cost variance is supportable, but the margin
result must be validated against a real contract-value source.

Correspondence changes the portfolio view in a controlled way. It contains
**$12.552M** of authorized unbooked cost and **$11.869M** of unbooked contract
value, reducing confirmed-adjusted margin by **$0.683M** to **-$674.7M**. A
separate downside scenario adds **$13.078M** of pending change cost and
**$21.831M** of RFI potential cost, producing **-$709.7M** margin. The
**$10.789M** of reported budget variance is shown independently and is not
added again because it may overlap these events or the forecast.

## Answers by assessment question

### 1. Cost-to-complete and projected margin

| Division | Jobs | Contract value proxy | Current cost budget | Projected final cost | Base margin | Downside margin |
|---|---:|---:|---:|---:|---:|---:|
| Building | 24 | $560.4M | $700.0M | $987.3M | -$426.9M | -$447.2M |
| Civil | 18 | $381.4M | $426.6M | $628.6M | -$247.2M | -$262.4M |

`mart_job_risk_adjusted` supports job, division, and contract-type views;
`mart_monthly_cost_trend` supplies period, job, and cost-code trends. The five
largest job cost variances are B2108 ($42.3M), C2132 ($30.5M), B2107 ($29.1M),
B2121 ($26.7M), and B2112 ($22.0M).

### 2. Cost-risk concentration

The largest cost-code variances are General Conditions ($43.4M), Plumbing
($33.4M), Roofing ($32.5M), Electrical ($31.9M), and Structural Steel ($31.3M).
The top five jobs represent 37.5% of positive projected job variance, and 19
jobs are needed to cross the 80% Pareto threshold. A dashboard Pareto should
therefore offer both job and cost-code ranking rather than imply a single-point
concentration.

### 3. Cost burn versus progress

Twenty-five jobs are critical because cost burn exceeds reported progress by at
least 20 percentage points; their mean gap is 51.8 points. Seven are high,
three watch, five normal, and two lack a usable budget denominator. B2108 has
the largest displayed gap at 99.0 points. This comparison is diagnostic rather
than earned-value accounting because the extracts do not include a time-phased
budget or schedule-weighted earned value.

### 4. Equipment economics

| Division | Ownership | Assignments | Total cost | Units | Cost/unit | Avg. utilization |
|---|---|---:|---:|---:|---:|---:|
| Building | Owned | 54 | $1.082M | 149,949 | $7.22 | 62.4% |
| Building | Rented | 74 | $1.486M | 175,414 | $8.47 | 62.8% |
| Civil | Owned | 37 | $0.519M | 90,523 | $5.74 | 58.8% |
| Civil | Rented | 50 | $1.078M | 113,232 | $9.52 | 66.9% |

Rented equipment costs more per production unit in both divisions—17% more in
Building and 66% more in Civil. Utilization is similar or higher for rentals,
so mix, equipment class, and job conditions should be checked before treating
the difference as a pure ownership saving opportunity.

### 5. Cross-division exposure

All 21 modeled cost-code members and all 60 known subcontractors appear across
both divisions. This makes enterprise-level vendor and cost-code controls
relevant. The combined subcontractor mart deliberately keeps ledger projected
cost separate from correspondence risk so the two cannot be accidentally
double counted.

### 6. Exposure present in correspondence but absent from the cost system

Correspondence yielded 1,307 events across 1,200 documents and ties to 13 jobs.
The governed event categories are:

| Category | Events | Amount |
|---|---:|---:|
| RFI potential cost | 257 | $21.831M |
| Pending change cost | 137 | $13.078M |
| Confirmed unbooked cost | 135 | $12.552M |
| Unbooked contract value | 128 | $11.869M |
| Reported budget variance | 127 | $10.789M |
| Schedule-only | 416 | — |
| Unquantified disputed backcharge | 107 | — |

B2100 has the largest pending-plus-potential amount at $3.566M, followed by
B2110 ($3.321M), C2127 ($3.129M), and B2122 ($3.121M). Structural Steel has the
largest division/cost-code downside exposure at $4.190M in Building, followed
by Building HVAC ($3.692M) and Building Utilities ($3.677M).

### 7. Additional risks and opportunities

- Thirteen jobs have stated delays; the maximum is 24 days. Days are not summed
  because documents may refer to the same schedule condition.
- The baseline quality layer exposes 432 errors, 3,689 warnings, and 300
  informational corrections. Unknown jobs, unmapped codes, duplicate postings,
  and reversed dates remain visible instead of being silently discarded.
- The final analysis layer has zero new quality issues and all eight
  reconciliations pass, so the scenario arithmetic is traceable even though
  source-system quality and the contract-value assumption remain material.
- Civil rented equipment has the clearest unit-cost review opportunity, while
  General Conditions is the largest cost-code variance control opportunity.

## Dashboard handoff

The first application slice should use `mart_job_dashboard` as its landing
table: portfolio KPI cards, risk-status/job filters, a base-versus-confirmed-
versus-downside margin comparison, and a ranked job table with explainable risk
reasons. Drill-throughs can use the cost-code, subcontractor, equipment, monthly
trend, and event-level exposure marts without recomputing business logic in the
frontend.
