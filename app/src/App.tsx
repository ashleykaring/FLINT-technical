import { useEffect, useMemo, useState } from "react";

import { fetchPortfolio } from "./api";
import { ParetoChart, RiskMatrix, ScenarioComparison, StatusSummary } from "./components/Charts";
import { currency, percent, titleCase } from "./format";
import type { ActiveFilters, JobSummary, PortfolioDashboard } from "./types";

const EMPTY_FILTERS: ActiveFilters = {
  division: "",
  contractType: "",
  projectManager: "",
  progressStatus: "",
};

function Mark() {
  return (
    <div className="brand-mark" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}

function Navigation() {
  return (
    <aside className="sidebar">
      <div className="brand"><Mark /><span>FLINT</span></div>
      <nav aria-label="Main navigation">
        <a className="nav-link active" href="#overview"><span>01</span>Portfolio overview</a>
        <a className="nav-link" href="#jobs"><span>02</span>Job risk</a>
        <span className="nav-link disabled"><span>03</span>Equipment</span>
        <span className="nav-link disabled"><span>04</span>Cross-division</span>
      </nav>
      <div className="sidebar-note">
        <span className="live-dot" />
        <div><strong>Warehouse connected</strong><small>DuckDB analytical marts</small></div>
      </div>
    </aside>
  );
}

interface FilterBarProps {
  dashboard: PortfolioDashboard;
  filters: ActiveFilters;
  onChange: (filters: ActiveFilters) => void;
}

function FilterBar({ dashboard, filters, onChange }: FilterBarProps) {
  const update = (field: keyof ActiveFilters, value: string) => onChange({ ...filters, [field]: value });
  return (
    <section className="filter-bar" aria-label="Portfolio filters">
      <label>
        <span>Division</span>
        <select value={filters.division} onChange={(event) => update("division", event.target.value)}>
          <option value="">All divisions</option>
          {dashboard.filters.divisions.map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label>
        <span>Contract type</span>
        <select value={filters.contractType} onChange={(event) => update("contractType", event.target.value)}>
          <option value="">All contracts</option>
          {dashboard.filters.contract_types.map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label>
        <span>Project manager</span>
        <select value={filters.projectManager} onChange={(event) => update("projectManager", event.target.value)}>
          <option value="">All managers</option>
          {dashboard.filters.project_managers.map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label>
        <span>Cost / progress</span>
        <select value={filters.progressStatus} onChange={(event) => update("progressStatus", event.target.value)}>
          <option value="">All statuses</option>
          {dashboard.filters.progress_statuses.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
        </select>
      </label>
      <button className="reset-button" type="button" onClick={() => onChange(EMPTY_FILTERS)} disabled={!Object.values(filters).some(Boolean)}>
        Reset
      </button>
    </section>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  note: string;
  tone?: "dark" | "default" | "lime";
}

function KpiCard({ label, value, note, tone = "default" }: KpiCardProps) {
  return (
    <article className={`kpi-card kpi-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </article>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-${status}`}>{titleCase(status)}</span>;
}

interface JobTableProps {
  jobs: JobSummary[];
  selectedJob: string | null;
  onSelect: (jobId: string) => void;
}

function JobTable({ jobs, selectedJob, onSelect }: JobTableProps) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Job</th>
            <th>Division / contract</th>
            <th>Progress</th>
            <th>Cost spent</th>
            <th>Projected variance</th>
            <th>Correspondence exposure</th>
            <th>Delay</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.job_id}
              className={selectedJob === job.job_id ? "selected-row" : ""}
              onClick={() => onSelect(job.job_id)}
            >
              <td><strong>{job.job_id}</strong><small>{job.project_manager_id}</small></td>
              <td>{job.division}<small>{job.contract_type}</small></td>
              <td>{percent(job.reported_progress_pct)}</td>
              <td>{percent(job.cost_spent_pct)}</td>
              <td className={job.projected_cost_variance > 0 ? "negative-value" : "positive-value"}>{currency(job.projected_cost_variance)}</td>
              <td>{currency(job.confirmed_unbooked_cost + job.potential_downside_cost)}<small>{currency(job.confirmed_unbooked_cost)} confirmed</small></td>
              <td>{job.maximum_reported_delay_days === null ? "—" : `${job.maximum_reported_delay_days}d`}</td>
              <td><StatusBadge status={job.progress_status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [filters, setFilters] = useState<ActiveFilters>(EMPTY_FILTERS);
  const [dashboard, setDashboard] = useState<PortfolioDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchPortfolio(filters)
      .then((result) => {
        if (!active) return;
        setDashboard(result);
        setError(null);
        setSelectedJob((current) =>
          current && !result.jobs.some((job) => job.job_id === current) ? null : current,
        );
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Could not load dashboard data");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters]);

  const selected = useMemo(
    () => dashboard?.jobs.find((job) => job.job_id === selectedJob) ?? null,
    [dashboard, selectedJob],
  );

  return (
    <div className="app-shell">
      <Navigation />
      <main className="main-content" id="overview">
        <header className="page-header">
          <div>
            <p className="eyebrow">Executive portfolio control</p>
            <h1>Cost &amp; risk overview</h1>
            <p>Baseline financials, correspondence exposure, and delivery signals in one view.</p>
          </div>
          <div className="header-meta">
            <span><i className="live-dot" />Analysis current</span>
            <strong>42 active jobs</strong>
          </div>
        </header>

        {dashboard && <FilterBar dashboard={dashboard} filters={filters} onChange={setFilters} />}

        {error && (
          <section className="error-panel">
            <strong>Dashboard data is unavailable</strong>
            <p>{error}</p>
            <code>uv run flint analyze</code> then <code>uv run flint serve-api</code>
          </section>
        )}

        {loading && !dashboard && <div className="loading-panel"><Mark /><span>Loading governed portfolio data…</span></div>}

        {dashboard && (
          <>
            <section className="kpi-grid" aria-label="Portfolio key performance indicators">
              <KpiCard tone="dark" label="Projected cost variance" value={currency(dashboard.kpis.projected_cost_variance)} note="Net variance on jobs with budget" />
              <KpiCard label="Current cost budget" value={currency(dashboard.kpis.current_cost_budget)} note={`${dashboard.kpis.jobs_in_view} jobs in current view`} />
              <KpiCard label="Projected final cost" value={currency(dashboard.kpis.projected_final_cost)} note="Actual + adjustments + forecast" />
              <KpiCard tone="lime" label="Confirmed unbooked cost" value={currency(dashboard.kpis.confirmed_unbooked_cost)} note="Authorized, not yet in cost system" />
              <KpiCard label="Potential downside" value={currency(dashboard.kpis.potential_downside_cost)} note="Pending changes + RFI potential" />
              <KpiCard label="Jobs requiring attention" value={`${dashboard.kpis.jobs_requiring_attention} / ${dashboard.kpis.jobs_in_view}`} note="Watch, high, or critical cost burn" />
            </section>

            <aside className="assumption-banner">
              <div className="assumption-icon">!</div>
              <div><strong>Margin is provisional.</strong><span>The source field <code>original_budget</code> is used as a contract-value proxy until authoritative contract revenue is available.</span></div>
            </aside>

            <section className="dashboard-grid scenario-grid">
              <article className="card scenario-card">
                <div className="card-heading"><div><p className="eyebrow">Commercial outlook</p><h2>Scenario comparison</h2></div><span className="metric-pill">Cost vs proxy</span></div>
                <ScenarioComparison scenarios={dashboard.scenarios} />
              </article>
              <article className="card status-card">
                <div className="card-heading"><div><p className="eyebrow">Operating signal</p><h2>Cost / progress status</h2></div></div>
                <StatusSummary counts={dashboard.status_counts} />
              </article>
            </section>

            <section className="dashboard-grid charts-grid">
              <article className="card">
                <div className="card-heading"><div><p className="eyebrow">Delivery efficiency</p><h2>Cost burn vs reported progress</h2></div><span className="metric-pill">Bubble = variance</span></div>
                <RiskMatrix jobs={dashboard.jobs} selectedJob={selectedJob} onSelect={setSelectedJob} />
              </article>
              <article className="card">
                <div className="card-heading"><div><p className="eyebrow">Concentration</p><h2>Cost-risk Pareto</h2></div><span className="metric-pill">Top 12 jobs</span></div>
                <ParetoChart points={dashboard.pareto} />
              </article>
            </section>

            {selected && (
              <aside className="selection-strip">
                <div><span>Selected job</span><strong>{selected.job_id}</strong></div>
                <p>{selected.risk_reasons}</p>
                <button type="button" onClick={() => setSelectedJob(null)} aria-label="Clear selected job">×</button>
              </aside>
            )}

            <section className="card jobs-card" id="jobs">
              <div className="card-heading jobs-heading">
                <div><p className="eyebrow">Action queue</p><h2>Ranked job risk</h2></div>
                <p>Ordered by projected variance plus potential downside. Select a row to connect it to the risk matrix.</p>
              </div>
              <JobTable jobs={dashboard.jobs} selectedJob={selectedJob} onSelect={setSelectedJob} />
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
