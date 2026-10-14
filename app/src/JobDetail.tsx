import { useEffect, useMemo, useState } from "react";

import { askJob, fetchJobDetail } from "./api";
import { CostCodeChart, MonthlyCostChart, ScenarioComparison } from "./components/Charts";
import { currency, percent, titleCase } from "./format";
import type { JobDetail, JobFinancialSummary, JobQuestionResponse } from "./types";

const SUGGESTED_QUESTIONS = [
  "What is driving this job's projected cost variance?",
  "What unbooked or potential costs should leadership watch?",
  "Is cost burn ahead of reported progress?",
];

function DetailKpi({ label, value, note, tone = "default" }: { label: string; value: string; note: string; tone?: "default" | "dark" | "lime" }) {
  return (
    <article className={`kpi-card kpi-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </article>
  );
}

function CostPosition({ summary }: { summary: JobFinancialSummary }) {
  if (summary.current_cost_budget <= 0) {
    return (
      <section className="card cost-position-card detail-section">
        <div><p className="eyebrow">Budget outlook</p><h2>Current vs forecast</h2></div>
        <p className="cost-position-empty">A usable current cost budget is not available for this job.</p>
      </section>
    );
  }
  const values = [
    { key: "actual", label: "Adjusted actual cost", value: summary.adjusted_actual_cost },
    { key: "budget", label: "Current cost budget", value: summary.current_cost_budget },
    { key: "projected", label: "Projected final cost", value: summary.projected_final_cost },
  ];
  const maximum = Math.max(...values.map((item) => item.value), 1) * 1.05;
  const actualOver = summary.adjusted_actual_cost > summary.current_cost_budget;
  const projectedOver = summary.projected_final_cost > summary.current_cost_budget;
  return (
    <section className="card cost-position-card detail-section">
      <div className="card-heading">
        <div><p className="eyebrow">Budget outlook</p><h2>Current vs forecast</h2></div>
        <span className={`budget-badge budget-${actualOver ? "already_over" : projectedOver ? "forecast_over" : "within_forecast"}`}>
          {actualOver ? "Already over" : projectedOver ? "Forecast to go over" : "Within forecast"}
        </span>
      </div>
      <div className="cost-position-bars">
        {values.map((item) => (
          <div key={item.key}>
            <span>{item.label}</span>
            <div><i className={`cost-position-${item.key}`} style={{ width: `${item.value / maximum * 100}%` }} /></div>
            <strong>{currency(item.value)}</strong>
          </div>
        ))}
      </div>
      <p className="cost-position-note">
        {actualOver
          ? `Actual cost is ${currency(summary.adjusted_actual_cost - summary.current_cost_budget)} above the current budget.`
          : projectedOver
            ? `Actual cost remains within budget, but the forecast finishes ${currency(summary.projected_cost_variance)} over.`
            : `The current forecast remains ${currency(Math.abs(summary.projected_cost_variance))} within budget.`}
      </p>
    </section>
  );
}

function dateLabel(value: string | null): string {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function ExposureOverview({ detail }: { detail: JobDetail }) {
  const totalEvents = detail.exposure_buckets.reduce((sum, bucket) => sum + bucket.event_count, 0);
  return (
    <div className="exposure-overview">
      <div className="exposure-total"><strong>{totalEvents}</strong><span>governed events</span></div>
      <div className="exposure-buckets">
        {detail.exposure_buckets.map((bucket) => (
          <div key={bucket.category}>
            <span>{titleCase(bucket.category)}</span>
            <strong>{bucket.amount ? currency(bucket.amount) : `${bucket.event_count} events`}</strong>
            <small>{bucket.event_count} record{bucket.event_count === 1 ? "" : "s"}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

function CostCodeTable({ detail }: { detail: JobDetail }) {
  return (
    <div className="table-scroll detail-table-scroll">
      <table>
        <thead><tr><th>Cost code</th><th>Budget</th><th>Adjusted actual</th><th>Forecast</th><th>Projected</th><th>Variance</th><th>Correspondence</th></tr></thead>
        <tbody>
          {detail.cost_codes.map((item) => (
            <tr key={item.cost_code}>
              <td><strong>{item.cost_code}</strong><small>{item.description}</small></td>
              <td>{currency(item.current_budget)}</td>
              <td>{currency(item.adjusted_actual_cost)}</td>
              <td>{currency(item.forecast_remaining)}</td>
              <td>{currency(item.projected_cost)}</td>
              <td className={item.projected_variance > 0 ? "negative-value" : "positive-value"}>{currency(item.projected_variance)}</td>
              <td>{currency(item.confirmed_unbooked_cost + item.potential_downside_cost)}<small>{currency(item.confirmed_unbooked_cost)} confirmed</small></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchedulePanel({ detail }: { detail: JobDetail }) {
  const summary = detail.schedule_summary;
  return (
    <>
      <div className="schedule-stats">
        <div><strong>{summary.activity_count}</strong><span>activities</span></div>
        <div><strong>{summary.incomplete_activity_count}</strong><span>incomplete</span></div>
        <div><strong>{percent(summary.mean_activity_progress_pct)}</strong><span>mean progress</span></div>
        <div><strong>{summary.maximum_reported_delay_days === null ? "—" : `${summary.maximum_reported_delay_days}d`}</strong><span>max stated delay</span></div>
      </div>
      <div className="table-scroll detail-table-scroll schedule-table">
        <table>
          <thead><tr><th>Activity</th><th>Progress</th><th>Baseline finish</th><th>Actual finish</th><th>Duration</th><th>Variance</th></tr></thead>
          <tbody>
            {detail.schedule_activities.map((activity) => (
              <tr key={activity.activity_id}>
                <td><strong>{activity.activity_name}</strong><small>{activity.activity_id}</small></td>
                <td>{percent(activity.pct_complete)}</td>
                <td>{dateLabel(activity.baseline_finish)}</td>
                <td className={activity.has_reversed_actual_dates ? "negative-value" : ""}>{dateLabel(activity.actual_finish)}</td>
                <td>{activity.actual_duration_days ?? activity.baseline_duration_days ?? "—"}d</td>
                <td className={(activity.duration_variance_days ?? 0) > 0 ? "negative-value" : ""}>{activity.duration_variance_days === null ? "—" : `${activity.duration_variance_days > 0 ? "+" : ""}${activity.duration_variance_days}d`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function SubcontractorTable({ detail }: { detail: JobDetail }) {
  return (
    <div className="table-scroll detail-table-scroll subcontractor-table">
      <table>
        <thead><tr><th>Subcontractor</th><th>Actual</th><th>Committed</th><th>Forecast</th><th>Projected exposure</th><th>Correspondence</th></tr></thead>
        <tbody>
          {detail.subcontractors.map((subcontractor) => (
            <tr key={subcontractor.subcontractor_id}>
              <td><strong>{subcontractor.display_name}</strong><small>{subcontractor.correspondence_event_count} correspondence events</small></td>
              <td>{currency(subcontractor.actual_cost + subcontractor.adjustment)}</td>
              <td>{currency(subcontractor.committed_cost)}</td>
              <td>{currency(subcontractor.forecast_remaining)}</td>
              <td>{currency(subcontractor.projected_cost_exposure)}</td>
              <td>{currency(subcontractor.confirmed_unbooked_cost + subcontractor.potential_downside_cost)}<small>{currency(subcontractor.confirmed_unbooked_cost)} confirmed</small></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CorrespondenceTable({ detail }: { detail: JobDetail }) {
  return (
    <div className="table-scroll correspondence-table">
      <table>
        <thead><tr><th>Document</th><th>Category / scope</th><th>Subcontractor</th><th>Amount</th><th>Commercial status</th><th>Schedule</th><th>Evidence</th></tr></thead>
        <tbody>
          {detail.correspondence_events.map((event) => (
            <tr key={event.event_key}>
              <td><strong>{event.doc_id}</strong><small>{event.doc_type} · event {event.event_index}</small></td>
              <td><span className={`event-category category-${event.category}`}>{titleCase(event.category)}</span><small>{event.scope ?? "No stated scope"}{event.cost_code ? ` · ${event.cost_code}` : ""}</small></td>
              <td>{event.subcontractor_id ?? "—"}</td>
              <td>{event.amount === null ? "—" : currency(event.amount)}</td>
              <td>{titleCase(event.approval_status)}<small>{titleCase(event.booking_status)}</small></td>
              <td>{event.schedule_impact_days === null ? "—" : `${event.schedule_impact_days}d`}<small>{event.schedule_impact_days === null ? "" : titleCase(event.schedule_impact_type)}</small></td>
              <td className="evidence-cell"><details><summary>View evidence</summary><p>{event.evidence_text}</p></details></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AskJobPanel({ jobId }: { jobId: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<JobQuestionResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  const submitQuestion = async (selectedQuestion?: string) => {
    const value = (selectedQuestion ?? question).trim();
    if (value.length < 3 || asking) return;
    setQuestion(value);
    setAsking(true);
    setAskError(null);
    setAnswer(null);
    try {
      setAnswer(await askJob(jobId, value));
    } catch (reason: unknown) {
      setAskError(reason instanceof Error ? reason.message : "Gemini could not answer this question");
    } finally {
      setAsking(false);
    }
  };

  return (
    <section className="card detail-section ask-job-card">
      <div className="ask-job-heading">
        <div>
          <p className="eyebrow">Grounded AI</p>
          <h2>Ask about {jobId}</h2>
          <p>Gemini receives this job's governed financial, schedule, equipment, subcontractor, and correspondence data.</p>
        </div>
        <span className="metric-pill">Single-turn answer</span>
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void submitQuestion(); }}>
        <textarea
          aria-label={`Question about ${jobId}`}
          maxLength={500}
          placeholder="Ask what is driving risk, what is outside the ledger, or where leadership should focus."
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" disabled={asking || question.trim().length < 3}>
          {asking ? "Reviewing job…" : "Ask Gemini"}
        </button>
      </form>
      <div className="ask-suggestions" aria-label="Suggested questions">
        {SUGGESTED_QUESTIONS.map((item) => (
          <button key={item} type="button" disabled={asking} onClick={() => { void submitQuestion(item); }}>{item}</button>
        ))}
      </div>
      {askError && <div className="ask-error" role="alert"><strong>Question unavailable</strong><span>{askError}</span></div>}
      {answer && (
        <div className="ask-answer" aria-live="polite">
          <div className="ask-answer-label"><span>Gemini</span><small>Grounded in {jobId} only</small></div>
          <p>{answer.answer}</p>
          {answer.supporting_facts.length > 0 && (
            <div className="ask-facts">
              {answer.supporting_facts.map((fact, index) => (
                <div key={`${fact.source_section}-${index}`}>
                  <span>{fact.source_section.replace("_", " ")}</span>
                  <p>{fact.statement}</p>
                </div>
              ))}
            </div>
          )}
          {answer.caveat && <aside><strong>Caveat</strong><span>{answer.caveat}</span></aside>}
        </div>
      )}
    </section>
  );
}

interface JobDetailPageProps {
  jobId: string;
  onBack: () => void;
}

export default function JobDetailPage({ jobId, onBack }: JobDetailPageProps) {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setDetail(null);
    fetchJobDetail(jobId)
      .then((result) => {
        if (!active) return;
        setDetail(result);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Could not load job detail");
      });
    return () => { active = false; };
  }, [jobId]);

  const correspondenceTotal = useMemo(
    () => detail
      ? detail.summary.confirmed_unbooked_cost + detail.summary.potential_downside_cost
      : 0,
    [detail],
  );

  if (error) {
    return <section className="error-panel"><strong>Job detail is unavailable</strong><p>{error}</p><button type="button" className="back-button" onClick={onBack}>Return to portfolio</button></section>;
  }
  if (!detail) return <div className="loading-panel"><span>Loading {jobId} detail…</span></div>;

  const summary = detail.summary;
  return (
    <div className="job-detail-page">
      <header className="job-detail-header">
        <div>
          <button type="button" className="back-button" onClick={onBack}>← Portfolio</button>
          <p className="eyebrow">Job details</p>
          <div className="job-title-row"><h1>{summary.job_id}</h1><span className={`status-badge status-${summary.progress_status}`}>{titleCase(summary.progress_status)}</span></div>
          <p>{summary.division} · {summary.contract_type} · {summary.project_manager_id} · Started {dateLabel(summary.start_date)}</p>
        </div>
        <div className="job-progress-block"><span>Reported progress</span><strong>{percent(summary.reported_progress_pct)}</strong><div><i style={{ width: `${Math.min((summary.reported_progress_pct ?? 0) * 100, 100)}%` }} /></div></div>
      </header>

      <section className="kpi-grid detail-kpi-grid">
        <DetailKpi tone="dark" label="Projected cost variance" value={currency(summary.projected_cost_variance)} note={`${percent(summary.cost_spent_pct)} of current budget spent`} />
        <DetailKpi label="Current cost budget" value={currency(summary.current_cost_budget)} note={`${currency(summary.adjusted_actual_cost)} adjusted actual`} />
        <DetailKpi label="Projected final cost" value={currency(summary.projected_final_cost)} note={`${currency(summary.forecast_remaining)} forecast remaining`} />
        <DetailKpi tone="lime" label="Correspondence exposure" value={currency(correspondenceTotal)} note={`${currency(summary.confirmed_unbooked_cost)} confirmed`} />
        <DetailKpi label="Potential downside" value={currency(summary.potential_downside_cost)} note={`${currency(summary.reported_budget_variance)} variance reported separately`} />
        <DetailKpi label="Maximum stated delay" value={summary.maximum_reported_delay_days === null ? "—" : `${summary.maximum_reported_delay_days} days`} note={`${summary.schedule_event_count} correspondence schedule events`} />
      </section>

      <aside className="risk-reason-banner"><span>Why this job is flagged</span><p>{summary.risk_reasons}</p></aside>

      <AskJobPanel key={summary.job_id} jobId={summary.job_id} />

      <CostPosition summary={summary} />

      <section className="dashboard-grid scenario-grid detail-top-grid">
        <article className="card"><div className="card-heading"><div><p className="eyebrow">Commercial outlook</p><h2>Job scenario comparison</h2></div><span className="metric-pill">Cost vs proxy</span></div><ScenarioComparison scenarios={detail.scenarios} /></article>
        <article className="card"><div className="card-heading"><div><p className="eyebrow">Outside the ledger</p><h2>Correspondence exposure</h2></div></div><ExposureOverview detail={detail} /></article>
      </section>

      <section className="dashboard-grid detail-chart-grid">
        <article className="card"><div className="card-heading"><div><p className="eyebrow">Cost trajectory</p><h2>Monthly cost trend</h2></div><span className="metric-pill">24 periods</span></div><MonthlyCostChart points={detail.monthly_costs} /></article>
        <article className="card"><div className="card-heading"><div><p className="eyebrow">Cost drivers</p><h2>Budget vs projected by cost code</h2></div><span className="metric-pill">Top 10</span></div><CostCodeChart costCodes={detail.cost_codes} /></article>
      </section>

      <section className="card detail-section"><div className="card-heading"><div><p className="eyebrow">Cost control</p><h2>Cost-code detail</h2></div><span className="metric-pill">{detail.cost_codes.length} codes</span></div><CostCodeTable detail={detail} /></section>

      <section className="card detail-section"><div className="card-heading"><div><p className="eyebrow">Delivery</p><h2>Schedule snapshot</h2></div><span className="metric-pill">Highest attention activities</span></div><SchedulePanel detail={detail} /></section>

      <section className="card detail-section"><div className="card-heading"><div><p className="eyebrow">Vendor exposure</p><h2>Subcontractors</h2></div><span className="metric-pill">Ledger + correspondence</span></div><SubcontractorTable detail={detail} /></section>

      <section className="card detail-section"><div className="card-heading"><div><p className="eyebrow">Audit trail</p><h2>Correspondence events</h2></div><span className="metric-pill">{detail.correspondence_events.length} events</span></div><CorrespondenceTable detail={detail} /></section>
    </div>
  );
}
