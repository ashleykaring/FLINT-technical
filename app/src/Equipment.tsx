import { useEffect, useState } from "react";

import { fetchEquipment } from "./api";
import { currency, percent } from "./format";
import type {
  EquipmentActiveFilters,
  EquipmentAssignment,
  EquipmentBreakdown,
  EquipmentDashboard,
} from "./types";

const EMPTY_FILTERS: EquipmentActiveFilters = {
  division: "",
  ownership: "",
  equipmentType: "",
  jobId: "",
};

function EquipmentKpi({
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

function EquipmentFilters({
  dashboard,
  filters,
  onChange,
}: {
  dashboard: EquipmentDashboard;
  filters: EquipmentActiveFilters;
  onChange: (filters: EquipmentActiveFilters) => void;
}) {
  const update = (field: keyof EquipmentActiveFilters, value: string) =>
    onChange({ ...filters, [field]: value });
  return (
    <section
      className="filter-bar equipment-filter-bar"
      aria-label="Equipment filters"
    >
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
        <span>Ownership</span>
        <select
          value={filters.ownership}
          onChange={(event) => update("ownership", event.target.value)}
        >
          <option value="">Owned and rented</option>
          {dashboard.filters.ownership_types.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Equipment type</span>
        <select
          value={filters.equipmentType}
          onChange={(event) => update("equipmentType", event.target.value)}
        >
          <option value="">All equipment types</option>
          {dashboard.filters.equipment_types.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Job</span>
        <select
          value={filters.jobId}
          onChange={(event) => update("jobId", event.target.value)}
        >
          <option value="">All jobs</option>
          {dashboard.filters.jobs.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <button
        className="reset-button"
        type="button"
        disabled={!Object.values(filters).some(Boolean)}
        onClick={() => onChange(EMPTY_FILTERS)}
      >
        Reset
      </button>
    </section>
  );
}

function OwnershipChart({ rows }: { rows: EquipmentBreakdown[] }) {
  const maximum = Math.max(...rows.map((row) => row.cost_per_unit ?? 0), 1);
  return (
    <div className="ownership-chart">
      {rows.map((row) => (
        <div key={`${row.division}-${row.ownership}`}>
          <span>
            <strong>{row.division}</strong>
            <small>{row.ownership}</small>
          </span>
          <div>
            <i
              className={`ownership-fill ownership-${row.ownership.toLowerCase()}`}
              style={{
                width: `${((row.cost_per_unit ?? 0) / maximum) * 100}%`,
              }}
            />
          </div>
          <strong>
            {row.cost_per_unit === null
              ? "—"
              : `${currency(row.cost_per_unit, false)}/unit`}
          </strong>
          <small>{percent(row.average_utilization, 1)} utilized</small>
        </div>
      ))}
      <div className="chart-legend">
        <span>
          <i style={{ background: "#1f4fd8" }} />
          Owned
        </span>
        <span>
          <i style={{ background: "#ef9b49" }} />
          Rented
        </span>
      </div>
    </div>
  );
}

function UtilizationScatter({
  assignments,
}: {
  assignments: EquipmentAssignment[];
}) {
  const points = assignments.filter(
    (item) => item.utilization !== null && item.cost_per_unit !== null,
  );
  const sortedCosts = points
    .map((item) => item.cost_per_unit ?? 0)
    .sort((a, b) => a - b);
  const percentileIndex = Math.min(
    Math.floor(sortedCosts.length * 0.95),
    sortedCosts.length - 1,
  );
  const yMaximum = Math.max(sortedCosts[percentileIndex] ?? 1, 1);
  const width = 680;
  const height = 230;
  const left = 50;
  const right = 20;
  const top = 14;
  const bottom = 38;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const x = (value: number) =>
    left + Math.min(Math.max(value, 0), 1) * plotWidth;
  const y = (value: number) =>
    top +
    plotHeight -
    (Math.min(Math.max(value, 0), yMaximum) / yMaximum) * plotHeight;
  return (
    <div className="chart-wrap equipment-scatter">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Equipment utilization versus cost per production unit"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={`x-${tick}`}>
            <line
              x1={x(tick)}
              y1={top}
              x2={x(tick)}
              y2={top + plotHeight}
              stroke="#dfe6dc"
            />
            <text
              x={x(tick)}
              y={height - 20}
              textAnchor="middle"
              className="axis-label"
            >
              {percent(tick)}
            </text>
          </g>
        ))}
        {[0, 0.5, 1].map((tick) => (
          <g key={`y-${tick}`}>
            <line
              x1={left}
              y1={y(yMaximum * tick)}
              x2={left + plotWidth}
              y2={y(yMaximum * tick)}
              stroke="#dfe6dc"
            />
            <text
              x={left - 8}
              y={y(yMaximum * tick) + 4}
              textAnchor="end"
              className="axis-label"
            >
              {currency(yMaximum * tick, false)}
            </text>
          </g>
        ))}
        {points.map((item) => (
          <circle
            key={item.assignment_key}
            cx={x(item.utilization ?? 0)}
            cy={y(item.cost_per_unit ?? 0)}
            r="5"
            fill={item.ownership === "Owned" ? "#1f4fd8" : "#ef9b49"}
            fillOpacity=".72"
            stroke="white"
          >
            <title>{`${item.job_id} · ${item.equipment_type} · ${item.ownership}: ${percent(item.utilization, 1)} utilization, ${currency(item.cost_per_unit ?? 0, false)}/unit`}</title>
          </circle>
        ))}
        <text
          x={left + plotWidth / 2}
          y={height - 2}
          textAnchor="middle"
          className="axis-title"
        >
          Utilization
        </text>
        <text
          transform={`translate(13 ${top + plotHeight / 2}) rotate(-90)`}
          textAnchor="middle"
          className="axis-title"
        >
          Cost per unit
        </text>
      </svg>
      <div className="chart-legend">
        <span>
          <i style={{ background: "#1f4fd8" }} />
          Owned
        </span>
        <span>
          <i style={{ background: "#ef9b49" }} />
          Rented
        </span>
        <span>Scale capped at 95th percentile</span>
      </div>
    </div>
  );
}

function EquipmentPage({ onOpenJob }: { onOpenJob: (jobId: string) => void }) {
  const [filters, setFilters] = useState<EquipmentActiveFilters>(EMPTY_FILTERS);
  const [dashboard, setDashboard] = useState<EquipmentDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchEquipment(filters)
      .then((result) => {
        if (active) {
          setDashboard(result);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load equipment data",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters]);

  return (
    <div className="equipment-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Operating efficiency</p>
          <h1>Equipment</h1>
        </div>
      </header>
      {dashboard && (
        <EquipmentFilters
          dashboard={dashboard}
          filters={filters}
          onChange={setFilters}
        />
      )}
      {error && (
        <section className="error-panel">
          <strong>Equipment data is unavailable</strong>
          <p>{error}</p>
        </section>
      )}
      {loading && !dashboard && (
        <div className="loading-panel">
          <span>Loading equipment economics…</span>
        </div>
      )}
      {dashboard && (
        <>
          <section className="kpi-grid equipment-kpi-grid">
            <EquipmentKpi
              tone="dark"
              label="Total equipment cost"
              value={currency(dashboard.kpis.total_equipment_cost)}
              note={`${dashboard.kpis.assignment_count} assignments across ${dashboard.kpis.job_count} jobs`}
            />
            <EquipmentKpi
              label="Weighted cost per unit"
              value={
                dashboard.kpis.weighted_cost_per_unit === null
                  ? "—"
                  : currency(dashboard.kpis.weighted_cost_per_unit, false)
              }
              note={`${dashboard.kpis.production_units.toLocaleString()} production units`}
            />
            <EquipmentKpi
              label="Average utilization"
              value={percent(dashboard.kpis.average_utilization, 1)}
              note="Mean assignment utilization"
            />
            <EquipmentKpi
              tone="lime"
              label="Rental premium"
              value={percent(dashboard.kpis.rental_premium_pct, 1)}
              note={`${dashboard.kpis.owned_cost_per_unit === null ? "—" : currency(dashboard.kpis.owned_cost_per_unit, false)} owned vs ${dashboard.kpis.rented_cost_per_unit === null ? "—" : currency(dashboard.kpis.rented_cost_per_unit, false)} rented per unit`}
            />
          </section>

          <section className="dashboard-grid equipment-chart-grid">
            <article className="card">
              <div className="card-heading">
                <div>
                  <p className="eyebrow">Ownership economics</p>
                  <h2>Cost per production unit</h2>
                </div>
                <span className="metric-pill">Weighted by units</span>
              </div>
              <OwnershipChart rows={dashboard.division_comparison} />
            </article>
            <article className="card">
              <div className="card-heading">
                <div>
                  <p className="eyebrow">Assignment pattern</p>
                  <h2>Utilization vs unit cost</h2>
                </div>
                <span className="metric-pill">Each dot = assignment</span>
              </div>
              <UtilizationScatter assignments={dashboard.assignments} />
            </article>
          </section>

          <section className="card equipment-table-card">
            <div className="card-heading">
              <div>
                <p className="eyebrow">Type and source review</p>
                <h2>Economics by equipment type</h2>
              </div>
              <span className="metric-pill">Owned and rented</span>
            </div>
            <div className="table-scroll equipment-type-table">
              <table>
                <thead>
                  <tr>
                    <th>Equipment type</th>
                    <th>Ownership</th>
                    <th>Assignments</th>
                    <th>Jobs</th>
                    <th>Total cost</th>
                    <th>Cost / unit</th>
                    <th>Utilization</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.type_summary.map((item) => (
                    <tr key={`${item.equipment_type}-${item.ownership}`}>
                      <td>
                        <strong>{item.equipment_type}</strong>
                      </td>
                      <td>
                        <span
                          className={`ownership-badge ownership-badge-${item.ownership.toLowerCase()}`}
                        >
                          {item.ownership}
                        </span>
                      </td>
                      <td>{item.assignment_count}</td>
                      <td>{item.job_count}</td>
                      <td>{currency(item.total_equipment_cost)}</td>
                      <td>
                        {item.cost_per_unit === null
                          ? "—"
                          : currency(item.cost_per_unit, false)}
                      </td>
                      <td>{percent(item.average_utilization, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card equipment-table-card">
            <div className="card-heading">
              <div>
                <p className="eyebrow">Investigation queue</p>
                <h2>Equipment assignments</h2>
              </div>
              <span className="metric-pill">
                {dashboard.assignments.length} records
              </span>
            </div>
            <div className="table-scroll equipment-assignment-table">
              <table>
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Division</th>
                    <th>Equipment</th>
                    <th>Ownership</th>
                    <th>Monthly rate</th>
                    <th>Months</th>
                    <th>Total cost</th>
                    <th>Production</th>
                    <th>Cost / unit</th>
                    <th>Utilization</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.assignments.map((item) => (
                    <tr
                      key={item.assignment_key}
                      onClick={() => onOpenJob(item.job_id)}
                    >
                      <td>
                        <strong>{item.job_id}</strong>
                      </td>
                      <td>{item.division}</td>
                      <td>{item.equipment_type}</td>
                      <td>
                        <span
                          className={`ownership-badge ownership-badge-${item.ownership.toLowerCase()}`}
                        >
                          {item.ownership}
                        </span>
                      </td>
                      <td>{currency(item.monthly_rate, false)}</td>
                      <td>{item.months_on_job}</td>
                      <td>{currency(item.total_equipment_cost)}</td>
                      <td>{item.production_units.toLocaleString()}</td>
                      <td>
                        {item.cost_per_unit === null
                          ? "—"
                          : currency(item.cost_per_unit, false)}
                      </td>
                      <td>{percent(item.utilization, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default EquipmentPage;
