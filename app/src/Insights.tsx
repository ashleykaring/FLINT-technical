import { useEffect, useState } from "react";

import { fetchPortfolioInsights } from "./api";
import { ParetoChart, StatusSummary } from "./components/Charts";
import { currency, percent, titleCase } from "./format";
import type { PortfolioInsights, RiskRankingInsight } from "./types";

function InsightKpi({
  label,
  value,
  note,
  tone = "default",
}: {
  label: string;
  value: string;
  note: string;
  tone?: "default" | "dark" | "lime";
}) {
  return (
    <article className={`kpi-card kpi-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </article>
  );
}

function SectionHeading({
  number,
  eyebrow,
  question,
  title,
  conclusion,
}: {
  number: string;
  eyebrow: string;
  question: string;
  title?: string;
  conclusion?: string;
}) {
  return (
    <div className="insight-heading">
      <span>{number}</span>
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <p className="insight-question">
          <strong>Question</strong>
          {question}
        </p>
        {title && <h2>{title}</h2>}
        {conclusion && <p>{conclusion}</p>}
      </div>
    </div>
  );
}

function CostScenarioBridge({ insights }: { insights: PortfolioInsights }) {
  const values = [
    {
      label: "Base projected cost",
      value: insights.headline.projected_final_cost,
    },
    {
      label: "Confirmed cost scenario",
      value:
        insights.headline.projected_final_cost +
        insights.headline.confirmed_unbooked_cost,
    },
    {
      label: "Downside cost scenario",
      value:
        insights.headline.projected_final_cost +
        insights.headline.confirmed_unbooked_cost +
        insights.headline.potential_downside_cost,
    },
  ];
  const maximum = Math.max(...values.map((item) => Math.abs(item.value)), 1);
  return (
    <div className="margin-bridge">
      {values.map((item, index) => (
        <div key={item.label}>
          <div>
            <span>{item.label}</span>
            <strong>{currency(item.value)}</strong>
          </div>
          <div className="insight-track">
            <i
              className={`margin-fill margin-fill-${index}`}
              style={{ width: `${(Math.abs(item.value) / maximum) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function rankingAsPareto(ranking: RiskRankingInsight[]) {
  return ranking.map((item) => ({
    rank: item.rank,
    job_id: item.job_id,
    exposure: item.projected_cost_variance,
    cumulative_pct: item.cumulative_pct,
  }));
}

function InsightsPage({ onOpenJob }: { onOpenJob: (jobId: string) => void }) {
  const [insights, setInsights] = useState<PortfolioInsights | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchPortfolioInsights()
      .then((result) => {
        if (!active) return;
        setInsights(result);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load assessment findings",
        );
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <section className="error-panel">
        <strong>Insights are unavailable</strong>
        <p>{error}</p>
      </section>
    );
  }
  if (!insights) {
    return (
      <div className="loading-panel">
        <span>Loading assessment evidence…</span>
      </div>
    );
  }

  const owned = new Map(
    insights.equipment
      .filter((item) => item.ownership.toLowerCase() === "owned")
      .map((item) => [item.division, item]),
  );
  const visibleCorrespondenceCategories = insights.correspondence_categories.filter(
    (item) =>
      ![
        "unbooked_contract_value",
        "disputed_backcharge_unquantified",
        "schedule_only",
      ].includes(item.category),
  );
  const correspondenceEvents = visibleCorrespondenceCategories.reduce(
    (total, item) => total + item.event_count,
    0,
  );
  const anomalies = insights.anomalies;
  const anomalyCards = anomalies
    ? [
        {
          label: "Unmapped cost code",
          value: anomalies.unmapped_ledger_cost_codes.join(", ") || "—",
          detail: `${anomalies.unmapped_ledger_posting_count.toLocaleString()} ledger postings could not be mapped`,
        },
        {
          label: "Jobs without budgets",
          value: `${anomalies.missing_budget_job_ids.length} jobs`,
          detail: anomalies.missing_budget_job_ids.join(", ") || "None",
        },
        {
          label: "Duplicate ledger rows",
          value: anomalies.duplicate_ledger_rows_excluded.toLocaleString(),
          detail: `${currency(anomalies.duplicate_ledger_amount_excluded)} excluded before analysis`,
        },
        {
          label: "Reversed schedule dates",
          value: `${anomalies.reversed_schedule_activity_count} activities`,
          detail: `Across ${anomalies.reversed_schedule_job_count} jobs; actual finish precedes start`,
        },
        {
          label: "Missing job IDs",
          value: `${anomalies.missing_job_id_posting_count} postings`,
          detail: "Preserved under UNKNOWN_JOB for investigation",
        },
      ]
    : [];

  return (
    <div className="insights-page">
      <header className="page-header insights-header">
        <div>
          <p className="eyebrow">Assessment evidence</p>
          <h1>Assessment findings</h1>
        </div>
      </header>

      <section className="insight-jumpbar" aria-label="Insight sections">
        {[
          ["financial", "Financial outlook"],
          ["concentration", "Concentration"],
          ["progress", "Cost / progress"],
          ["equipment", "Equipment"],
          ["cross-division", "Cross-division"],
          ["correspondence", "Correspondence"],
          ["quality", "Data quality"],
        ].map(([id, label], index) => (
          <button
            key={id}
            type="button"
            onClick={() => document.getElementById(id)?.scrollIntoView()}
          >
            <span>0{index + 1}</span>
            {label}
          </button>
        ))}
      </section>

      <section className="kpi-grid insights-kpis">
        <InsightKpi
          tone="dark"
          label="Net projected variance"
          value={currency(insights.headline.net_projected_cost_variance)}
          note="Projected cost above current budget"
        />
        <InsightKpi
          label="Positive variance exposure"
          value={currency(insights.headline.positive_cost_variance)}
          note="Adverse jobs before favorable offsets"
        />
        <InsightKpi
          tone="lime"
          label="Confirmed unbooked"
          value={currency(insights.headline.confirmed_unbooked_cost)}
          note="Authorized cost absent from ledger"
        />
        <InsightKpi
          label="Potential downside"
          value={currency(insights.headline.potential_downside_cost)}
          note="Pending and potential changes"
        />
        <InsightKpi
          label="Critical burn profile"
          value={`${insights.headline.critical_cost_progress_jobs} jobs`}
          note="Cost is materially ahead of progress"
        />
        <InsightKpi
          label="Risk concentration"
          value={`${insights.headline.jobs_to_eighty_pct} jobs`}
          note="Reach 80% of adverse variance"
        />
      </section>

      <section className="card insight-section" id="financial">
        <SectionHeading
          number="01"
          eyebrow="Financial outlook"
          question="What are projected cost-to-complete and margin by portfolio segment?"
          title="Projected portfolio cost increases under correspondence downside"
          conclusion={`${currency(insights.headline.projected_final_cost)} of base projected cost rises to ${currency(insights.headline.projected_final_cost + insights.headline.confirmed_unbooked_cost + insights.headline.potential_downside_cost)} if confirmed and potential correspondence costs materialize.`}
        />
        <div className="insight-two-column">
          <CostScenarioBridge insights={insights} />
          <div className="division-comparison">
            {insights.divisions.map((division) => (
              <article key={division.division}>
                <div>
                  <strong>{division.division}</strong>
                  <span>{division.job_count} jobs</span>
                </div>
                <dl>
                  <div>
                    <dt>Current budget</dt>
                    <dd>{currency(division.current_cost_budget)}</dd>
                  </div>
                  <div>
                    <dt>Base projected cost</dt>
                    <dd>{currency(division.projected_final_cost)}</dd>
                  </div>
                  <div>
                    <dt>Projected variance</dt>
                    <dd>{currency(division.projected_cost_variance)}</dd>
                  </div>
                  <div>
                    <dt>Downside projected cost</dt>
                    <dd>
                      {currency(
                        division.projected_final_cost +
                          division.confirmed_unbooked_cost +
                          division.potential_downside_cost,
                      )}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="card insight-section" id="concentration">
        <SectionHeading
          number="02"
          eyebrow="Risk concentration"
          question="Where is cost risk concentrated across jobs and cost codes?"
          title="A focused job list captures most adverse variance"
          conclusion={`${insights.headline.jobs_to_eighty_pct} jobs account for 80% of positive variance; the top five alone represent ${percent(insights.headline.top_five_variance_share, 1)}.`}
        />
        <div className="insight-two-column concentration-grid">
          <ParetoChart points={rankingAsPareto(insights.risk_ranking)} />
          <div className="rank-list">
            {insights.risk_ranking.slice(0, 7).map((job) => (
              <button
                key={job.job_id}
                type="button"
                onClick={() => onOpenJob(job.job_id)}
              >
                <span>{String(job.rank).padStart(2, "0")}</span>
                <div>
                  <strong>{job.job_id}</strong>
                  <small>{job.division}</small>
                </div>
                <div>
                  <strong>{currency(job.projected_cost_variance)}</strong>
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="card insight-section" id="progress">
        <SectionHeading
          number="03"
          eyebrow="Delivery efficiency"
          question="Which jobs are spending ahead of reported progress?"
          title="Cost burn is ahead of reported progress on most jobs"
          conclusion={`${insights.headline.critical_cost_progress_jobs} jobs are critical, making cost-to-progress divergence is apparent.`}
        />
        <div className="insight-two-column progress-grid">
          <StatusSummary counts={insights.progress_statuses} />
          <div className="compact-table">
            <div className="compact-table-head">
              <span>Job</span>
              <span>Progress</span>
              <span>Cost</span>
              <span>Gap</span>
            </div>
            {insights.cost_progress_jobs.slice(0, 8).map((job) => (
              <button
                key={job.job_id}
                type="button"
                onClick={() => onOpenJob(job.job_id)}
              >
                <span>
                  <strong>{job.job_id}</strong>
                  <small>{job.division}</small>
                </span>
                <span>{percent(job.reported_progress_pct)}</span>
                <span>{percent(job.cost_spent_pct)}</span>
                <span className="negative-value">
                  {percent(job.cost_progress_variance, 1)}
                </span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="card insight-section" id="equipment">
        <SectionHeading
          number="04"
          eyebrow="Equipment economics"
          question="How do owned and rented equipment economics compare?"
          title="Rented equipment carries a cost-per-unit premium in both divisions"
          conclusion="Ownership strategy should be evaluated by division: utilization is similar, while rented unit economics are consistently higher."
        />
        <div className="equipment-grid">
          {insights.equipment.map((item) => {
            const ownedPeer = owned.get(item.division);
            const premium =
              item.ownership.toLowerCase() === "rented" &&
              ownedPeer?.cost_per_unit &&
              item.cost_per_unit
                ? item.cost_per_unit / ownedPeer.cost_per_unit - 1
                : null;
            return (
              <article key={`${item.division}-${item.ownership}`}>
                <div>
                  <span>{item.division}</span>
                  <strong>{titleCase(item.ownership)}</strong>
                </div>
                <strong>
                  {item.cost_per_unit === null
                    ? "—"
                    : `${currency(item.cost_per_unit, false)} / unit`}
                </strong>
                <dl>
                  <div>
                    <dt>Utilization</dt>
                    <dd>{percent(item.average_utilization, 1)}</dd>
                  </div>
                  <div>
                    <dt>Assignments</dt>
                    <dd>{item.assignment_count}</dd>
                  </div>
                  <div>
                    <dt>Total cost</dt>
                    <dd>{currency(item.total_equipment_cost)}</dd>
                  </div>
                </dl>
                {premium !== null && (
                  <p>{percent(premium, 1)} premium to owned</p>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="card insight-section" id="cross-division">
        <SectionHeading
          number="05"
          eyebrow="Cross-division exposure"
          question="Which cost codes and subcontractors create cross-division exposure?"
          title="Shared cost codes and subcontractors"
          conclusion={`${insights.cross_division_cost_code_count} cost codes and ${insights.cross_division_subcontractor_count} subcontractors span both divisions.`}
        />
        <div className="cross-counts">
          <div>
            <strong>{insights.cross_division_cost_code_count}</strong>
            <span>shared cost codes</span>
          </div>
          <div>
            <strong>{insights.cross_division_subcontractor_count}</strong>
            <span>cross-division subcontractors</span>
          </div>
        </div>
        <div className="insight-two-column cross-tables">
          <div className="compact-table">
            <h3>Cost-code exposure</h3>
            <div className="compact-table-head three">
              <span>Cost code</span>
              <span>Variance</span>
              <span>Downside</span>
            </div>
            {insights.cost_code_risks.slice(0, 7).map((item) => (
              <div className="compact-row three" key={item.cost_code}>
                <span>
                  <strong>{item.cost_code}</strong>
                  <small>{item.description}</small>
                </span>
                <span>{currency(item.projected_cost_variance)}</span>
                <span>{currency(item.correspondence_downside)}</span>
              </div>
            ))}
          </div>
          <div className="compact-table">
            <h3>Subcontractor exposure</h3>
            <div className="compact-table-head three">
              <span>Subcontractor</span>
              <span>Ledger</span>
              <span>Downside</span>
            </div>
            {insights.subcontractor_risks.slice(0, 7).map((item) => (
              <div className="compact-row three" key={item.subcontractor_id}>
                <span>
                  <strong>{item.subcontractor_id}</strong>
                  <small>{item.division_count} divisions</small>
                </span>
                <span>{currency(item.ledger_projected_cost)}</span>
                <span>{currency(item.potential_downside_cost)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="card insight-section" id="correspondence">
        <SectionHeading
          number="06"
          eyebrow="Correspondence risk"
          question="What exposure appears in correspondence but not the cost system?"
          title="Project communications contain cost and insights not visible in the ledger"
          conclusion={`${correspondenceEvents.toLocaleString()} extracted events identify ${currency(insights.headline.confirmed_unbooked_cost)} confirmed unbooked cost and ${currency(insights.headline.potential_downside_cost)} potential downside.`}
        />
        <div className="correspondence-summary">
          {visibleCorrespondenceCategories.map((item) => (
            <article key={item.category}>
              <span>{titleCase(item.category)}</span>
              <strong>{currency(item.amount)}</strong>
              <small>{item.event_count} events</small>
            </article>
          ))}
        </div>
        <div className="compact-table correspondence-jobs">
          <div className="compact-table-head correspondence-columns">
            <span>Job</span>
            <span>Events</span>
            <span>Confirmed</span>
            <span>Potential</span>
            <span>Delay</span>
          </div>
          {insights.correspondence_jobs.slice(0, 10).map((job) => (
            <button
              className="correspondence-columns"
              key={job.job_id}
              type="button"
              onClick={() => onOpenJob(job.job_id)}
            >
              <span>
                <strong>{job.job_id}</strong>
                <small>{job.division}</small>
              </span>
              <span>{job.event_count}</span>
              <span>{currency(job.confirmed_unbooked_cost)}</span>
              <span>{currency(job.potential_downside_cost)}</span>
              <span>
                {job.maximum_reported_delay_days === null
                  ? "—"
                  : `${job.maximum_reported_delay_days}d`}
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="card insight-section" id="quality">
        <SectionHeading
          number="07"
          eyebrow="Trust & controls"
          question="What additional risks, opportunities, and data issues stand out?"
        />
        {anomalyCards.length > 0 && (
          <>
            <h3 className="anomaly-title">Notable source anomalies</h3>
            <div className="anomaly-grid">
              {anomalyCards.map((item) => (
                <article key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export default InsightsPage;
