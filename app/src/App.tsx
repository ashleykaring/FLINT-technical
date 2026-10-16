import { useEffect, useState } from "react";

import { fetchPortfolio } from "./api";
import {
  ParetoChart,
  RiskMatrix,
  ScenarioComparison,
  ScenarioLegend,
  StatusSummary,
} from "./components/Charts";
import { currency, percent, titleCase } from "./format";
import DataFlowPage from "./DataFlow";
import EquipmentPage from "./Equipment";
import InsightsPage from "./Insights";
import JobDetailPage from "./JobDetail";
import type {
  ActiveFilters,
  BudgetOutlookSummary,
  JobSummary,
  PortfolioDashboard,
  ScenarioSummary,
} from "./types";

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

function Navigation({
  jobId,
  equipment,
  insights,
  dataFlow,
}: {
  jobId: string | null;
  equipment: boolean;
  insights: boolean;
  dataFlow: boolean;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark />
        <span>BOS</span>
      </div>
      <nav aria-label="Main navigation">
        <a
          className={`nav-link ${!jobId && !equipment && !insights && !dataFlow ? "active" : ""}`}
          href="#/"
        >
          <span>01</span>Portfolio
        </a>
        <a
          className={`nav-link ${jobId ? "active" : ""}`}
          href={jobId ? `#/jobs/${jobId}` : "#jobs"}
        >
          <span>02</span>Job details
        </a>
        <a
          className={`nav-link ${equipment ? "active" : ""}`}
          href="#/equipment"
        >
          <span>03</span>Equipment
        </a>
        <a className={`nav-link ${insights ? "active" : ""}`} href="#/insights">
          <span>04</span>Assessment findings
        </a>
        <a
          className={`nav-link ${dataFlow ? "active" : ""}`}
          href="#/data-flow"
        >
          <span>05</span>Data flow
        </a>
      </nav>
      <div className="sidebar-note">
        <span className="live-dot" />
        <div>
          <strong>42 active jobs</strong>
          <small>Analysis current</small>
        </div>
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
  const update = (field: keyof ActiveFilters, value: string) =>
    onChange({ ...filters, [field]: value });
  return (
    <section className="filter-bar" aria-label="Portfolio filters">
      <label>
        <span>Division</span>
        <select
          value={filters.division}
          onChange={(event) => update("division", event.target.value)}
        >
          <option value="">All divisions</option>
          {dashboard.filters.divisions.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Contract type</span>
        <select
          value={filters.contractType}
          onChange={(event) => update("contractType", event.target.value)}
        >
          <option value="">All contracts</option>
          {dashboard.filters.contract_types.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Project manager</span>
        <select
          value={filters.projectManager}
          onChange={(event) => update("projectManager", event.target.value)}
        >
          <option value="">All managers</option>
          {dashboard.filters.project_managers.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Cost / progress</span>
        <select
          value={filters.progressStatus}
          onChange={(event) => update("progressStatus", event.target.value)}
        >
          <option value="">All statuses</option>
          {dashboard.filters.progress_statuses.map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </select>
      </label>
      <button
        className="reset-button"
        type="button"
        onClick={() => onChange(EMPTY_FILTERS)}
        disabled={!Object.values(filters).some(Boolean)}
      >
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
  onClick?: () => void;
}

function KpiCard({
  label,
  value,
  note,
  tone = "default",
  onClick,
}: KpiCardProps) {
  const content = (
    <>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </>
  );
  return onClick ? (
    <button
      className={`kpi-card kpi-${tone} kpi-clickable`}
      type="button"
      onClick={onClick}
      aria-label={`${label}: ${value}. View cost scenarios.`}
    >
      {content}
    </button>
  ) : (
    <article className={`kpi-card kpi-${tone}`}>{content}</article>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`status-badge status-${status}`}>{titleCase(status)}</span>
  );
}

function BudgetOutlookCard({ outlook }: { outlook: BudgetOutlookSummary }) {
  const width = (count: number) =>
    `${outlook.total_jobs ? (count / outlook.total_jobs) * 100 : 0}%`;
  const categories = [
    {
      key: "already",
      label: "Already over",
      count: outlook.currently_over_count,
    },
    {
      key: "forecast",
      label: "Forecast to cross",
      count: outlook.forecast_only_count,
    },
    {
      key: "within",
      label: "Within forecast",
      count: outlook.within_forecast_count,
    },
    { key: "missing", label: "No budget", count: outlook.missing_budget_count },
  ];
  return (
    <article className="kpi-card budget-outlook-card">
      <p className="eyebrow">Budget outlook</p>
      <strong>
        {outlook.currently_over_count} now ·{" "}
        {outlook.currently_over_count + outlook.forecast_only_count} projected
      </strong>
      <div
        className="budget-segments"
        aria-label="Jobs by current and projected budget position"
      >
        {categories.map((category) => (
          <i
            className={`budget-segment budget-segment-${category.key}`}
            key={category.key}
            style={{ width: width(category.count) }}
            title={`${category.label}: ${category.count}`}
          />
        ))}
      </div>
      <div className="budget-segment-legend">
        {categories.map((category) => (
          <span key={category.key}>
            <i className={`budget-dot-${category.key}`} />
            {category.count} {category.label.toLowerCase()}
          </span>
        ))}
      </div>
      <small>
        {currency(outlook.current_gross_overrun)} current ·{" "}
        {currency(outlook.projected_gross_overrun)} projected gross overrun
      </small>
    </article>
  );
}

function BudgetBadge({ outlook }: { outlook: JobSummary["budget_outlook"] }) {
  const labels = {
    already_over: "Already over",
    forecast_over: "Forecast to go over",
    within_forecast: "Within forecast",
    missing_budget: "Budget unavailable",
  };
  return (
    <span className={`budget-badge budget-${outlook}`}>{labels[outlook]}</span>
  );
}

function CostScenarioModal({
  actualCostToDate,
  scenarios,
  onClose,
}: {
  actualCostToDate: number;
  scenarios: ScenarioSummary[];
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);
  const baseCost = scenarios[0]?.projected_final_cost ?? 0;
  const descriptions = [
    "Adjusted actual cost plus forecast remaining",
    "Base forecast plus approved costs not yet booked",
    "Confirmed scenario plus pending and potential costs",
  ];
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="cost-scenario-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cost-scenario-title"
      >
        <button
          className="modal-close"
          type="button"
          onClick={onClose}
          aria-label="Close cost scenarios"
        >
          ×
        </button>
        <p className="eyebrow">Portfolio cost outlook</p>
        <h2 id="cost-scenario-title">What the projected final cost includes</h2>
        <div className="modal-current-cost">
          <span>Recorded cost to date</span>
          <strong>{currency(actualCostToDate)}</strong>
        </div>
        <div className="modal-scenario-list">
          {scenarios.map((scenario, index) => (
            <article key={scenario.scenario}>
              <span>0{index + 1}</span>
              <div>
                <strong>
                  {index === 0
                    ? "Base projected cost"
                    : index === 1
                      ? "Approved-cost scenario"
                      : "Downside scenario"}
                </strong>
                <small>{descriptions[index]}</small>
              </div>
              <div>
                <strong>{currency(scenario.projected_final_cost)}</strong>
                <small>
                  {index === 0
                    ? "Headline forecast"
                    : `+${currency(scenario.projected_final_cost - baseCost)} from base`}
                </small>
              </div>
            </article>
          ))}
        </div>
        <aside>
          <strong>Not included in the base:</strong> approved unbooked
          correspondence costs, pending changes, and RFI potential costs.
        </aside>
      </section>
    </div>
  );
}

interface JobTableProps {
  jobs: JobSummary[];
  onSelect: (jobId: string) => void;
}

function JobTable({ jobs, onSelect }: JobTableProps) {
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
            <th>Budget outlook</th>
            <th>Correspondence exposure</th>
            <th>Delay</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.job_id} onClick={() => onSelect(job.job_id)}>
              <td>
                <strong>{job.job_id}</strong>
                <small>{job.project_manager_id}</small>
              </td>
              <td>
                {job.division}
                <small>{job.contract_type}</small>
              </td>
              <td>{percent(job.reported_progress_pct)}</td>
              <td>{percent(job.cost_spent_pct)}</td>
              <td
                className={
                  job.projected_cost_variance > 0
                    ? "negative-value"
                    : "positive-value"
                }
              >
                {currency(job.projected_cost_variance)}
              </td>
              <td>
                <BudgetBadge outlook={job.budget_outlook} />
              </td>
              <td>
                {currency(
                  job.confirmed_unbooked_cost + job.potential_downside_cost,
                )}
                <small>{currency(job.confirmed_unbooked_cost)} confirmed</small>
              </td>
              <td>
                {job.maximum_reported_delay_days === null
                  ? "—"
                  : `${job.maximum_reported_delay_days}d`}
              </td>
              <td>
                <StatusBadge status={job.progress_status} />
              </td>
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
  const [jobId, setJobId] = useState<string | null>(() => {
    const match = window.location.hash.match(/^#\/jobs\/([^/?]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  });
  const [showInsights, setShowInsights] = useState(() =>
    window.location.hash.startsWith("#/insights"),
  );
  const [showEquipment, setShowEquipment] = useState(() =>
    window.location.hash.startsWith("#/equipment"),
  );
  const [showDataFlow, setShowDataFlow] = useState(() =>
    window.location.hash.startsWith("#/data-flow"),
  );
  const [showCostScenarios, setShowCostScenarios] = useState(false);

  useEffect(() => {
    const updateRoute = () => {
      const hash = window.location.hash;
      const match = hash.match(/^#\/jobs\/([^/?]+)/);
      setJobId(match ? decodeURIComponent(match[1]) : null);
      setShowEquipment(hash.startsWith("#/equipment"));
      setShowInsights(hash.startsWith("#/insights"));
      setShowDataFlow(hash.startsWith("#/data-flow"));
      setShowCostScenarios(false);
      if (match || hash.startsWith("#/")) {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    };
    window.addEventListener("hashchange", updateRoute);
    return () => window.removeEventListener("hashchange", updateRoute);
  }, []);

  useEffect(() => {
    if (jobId || showEquipment || showInsights || showDataFlow) return;
    let active = true;
    setLoading(true);
    fetchPortfolio(filters)
      .then((result) => {
        if (!active) return;
        setDashboard(result);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load dashboard data",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters, jobId, showEquipment, showInsights, showDataFlow]);

  const openJob = (selectedJobId: string) => {
    window.location.hash = `/jobs/${encodeURIComponent(selectedJobId)}`;
  };

  const openPortfolio = () => {
    window.location.hash = "/";
  };

  return (
    <div className="app-shell">
      <Navigation
        jobId={jobId}
        equipment={showEquipment}
        insights={showInsights}
        dataFlow={showDataFlow}
      />
      {jobId ? (
        <main className="main-content">
          <JobDetailPage jobId={jobId} onBack={openPortfolio} />
        </main>
      ) : showEquipment ? (
        <main className="main-content">
          <EquipmentPage onOpenJob={openJob} />
        </main>
      ) : showInsights ? (
        <main className="main-content">
          <InsightsPage onOpenJob={openJob} />
        </main>
      ) : showDataFlow ? (
        <main className="main-content">
          <DataFlowPage />
        </main>
      ) : (
        <main className="main-content" id="overview">
          <header className="page-header">
            <div>
              <p className="eyebrow">Executive portfolio control</p>
              <h1>Cost &amp; risk overview</h1>
            </div>
          </header>

          {dashboard && (
            <FilterBar
              dashboard={dashboard}
              filters={filters}
              onChange={setFilters}
            />
          )}

          {error && (
            <section className="error-panel">
              <strong>Dashboard data is unavailable</strong>
              <p>{error}</p>
              <code>uv run flint refresh</code> (Gemini API key needed on the first run), then{" "}
              <code>uv run flint serve-api</code>
            </section>
          )}

          {loading && !dashboard && (
            <div className="loading-panel">
              <Mark />
              <span>Loading governed portfolio data…</span>
            </div>
          )}

          {dashboard && (
            <>
              <section
                className="kpi-grid portfolio-kpi-grid"
                aria-label="Portfolio key performance indicators"
              >
                <KpiCard
                  tone="dark"
                  label="Projected cost variance"
                  value={currency(dashboard.kpis.projected_cost_variance)}
                  note="Net variance on jobs with budget"
                />
                <KpiCard
                  label="Current cost budget"
                  value={currency(dashboard.kpis.current_cost_budget)}
                  note={`${dashboard.kpis.jobs_in_view} jobs in current view`}
                />
                <KpiCard
                  label="Projected final cost"
                  value={currency(dashboard.kpis.projected_final_cost)}
                  note="Final-cost forecast"
                  onClick={() => setShowCostScenarios(true)}
                />
                <KpiCard
                  tone="lime"
                  label="Confirmed unbooked cost"
                  value={currency(dashboard.kpis.confirmed_unbooked_cost)}
                  note="Authorized, not yet in cost system"
                />
                <KpiCard
                  label="Potential downside"
                  value={currency(dashboard.kpis.potential_downside_cost)}
                  note="Pending changes + RFI potential"
                />
                <BudgetOutlookCard outlook={dashboard.budget_outlook} />
              </section>

              <aside className="assumption-banner">
                <div className="assumption-icon">!</div>
                <div>
                  <strong>Margin is provisional.</strong>
                  <span>
                    The original budget is shown for comparison because
                    authoritative contract revenue is unavailable.
                  </span>
                </div>
              </aside>

              <section className="dashboard-grid scenario-grid">
                <article className="card scenario-card">
                  <div className="card-heading">
                    <div>
                      <p className="eyebrow">Commercial outlook</p>
                      <h2>Scenario comparison</h2>
                    </div>
                    <ScenarioLegend />
                  </div>
                  <ScenarioComparison scenarios={dashboard.scenarios} />
                </article>
                <article className="card status-card">
                  <div className="card-heading">
                    <div>
                      <p className="eyebrow">Operating signal</p>
                      <h2>Cost / progress status</h2>
                    </div>
                  </div>
                  <StatusSummary counts={dashboard.status_counts} />
                </article>
              </section>

              <section className="dashboard-grid charts-grid">
                <article className="card">
                  <div className="card-heading">
                    <div>
                      <p className="eyebrow">Delivery efficiency</p>
                      <h2>Cost burn vs reported progress</h2>
                    </div>
                    <span className="metric-pill">
                      Dot = job · Size = projected variance
                    </span>
                  </div>
                  <RiskMatrix
                    jobs={dashboard.jobs}
                    selectedJob={null}
                    onSelect={openJob}
                  />
                </article>
                <article className="card">
                  <div className="card-heading">
                    <div>
                      <p className="eyebrow">Concentration</p>
                      <h2>Cost-risk Pareto</h2>
                    </div>
                    <span className="metric-pill">Top 12 jobs</span>
                  </div>
                  <ParetoChart points={dashboard.pareto} />
                </article>
              </section>

              <section className="card jobs-card" id="jobs">
                <div className="card-heading jobs-heading">
                  <div>
                    <p className="eyebrow">Action queue</p>
                    <h2>Ranked job risk</h2>
                  </div>
                  <p>Ordered by projected variance plus potential downside. </p>
                </div>
                <JobTable jobs={dashboard.jobs} onSelect={openJob} />
              </section>
            </>
          )}
          {showCostScenarios && dashboard && (
            <CostScenarioModal
              actualCostToDate={dashboard.kpis.actual_cost_to_date}
              scenarios={dashboard.scenarios}
              onClose={() => setShowCostScenarios(false)}
            />
          )}
        </main>
      )}
    </div>
  );
}

export default App;
