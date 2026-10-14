import type { CSSProperties } from "react";

import { currency, percent, titleCase } from "../format";
import type {
  CostCodeDetail,
  JobSummary,
  MonthlyCostPoint,
  ParetoPoint,
  ScenarioSummary,
  StatusCount,
} from "../types";

const STATUS_COLORS: Record<string, string> = {
  critical: "#e05252",
  high: "#ef8c3d",
  watch: "#e7bd25",
  normal: "#4d9a72",
  missing_budget: "#8090a4",
};

interface ScenarioComparisonProps {
  scenarios: ScenarioSummary[];
}

export function ScenarioComparison({ scenarios }: ScenarioComparisonProps) {
  const maximum = Math.max(
    ...scenarios.flatMap((scenario) => [
      scenario.contract_value_proxy,
      scenario.projected_final_cost,
    ]),
    1,
  );

  return (
    <div className="scenario-list">
      {scenarios.map((scenario, index) => {
        const costWidth = (scenario.projected_final_cost / maximum) * 100;
        const contractPosition = (scenario.contract_value_proxy / maximum) * 100;
        return (
          <div className="scenario-row" key={scenario.scenario}>
            <div className="scenario-heading">
              <div>
                <span className={`scenario-index scenario-index-${index}`}>0{index + 1}</span>
                <strong>{scenario.scenario}</strong>
              </div>
              <div className="scenario-values">
                <strong>{currency(scenario.projected_final_cost)}</strong>
                <span className="negative-value">{currency(scenario.projected_margin)} margin</span>
              </div>
            </div>
            <div className="scenario-track" aria-label={`${scenario.scenario} projected cost`}>
              <div
                className={`scenario-fill scenario-fill-${index}`}
                style={{ width: `${costWidth}%` }}
              />
              <span
                className="contract-marker"
                style={{ left: `${contractPosition}%` }}
                title={`Original budget ${currency(scenario.contract_value_proxy)}`}
              />
            </div>
            <div className="scenario-footnote">
              <span>Original budget {currency(scenario.contract_value_proxy)}</span>
              <span>
                {index === 0
                  ? "Forecast baseline"
                  : `${currency(scenario.change_from_base)} vs base margin`}
              </span>
            </div>
          </div>
        );
      })}
      <div className="scenario-legend">
        <span><i className="legend-cost" /> Projected final cost</span>
        <span><i className="legend-marker" /> Original budget</span>
      </div>
    </div>
  );
}

interface StatusSummaryProps {
  counts: StatusCount[];
}

export function StatusSummary({ counts }: StatusSummaryProps) {
  const total = counts.reduce((sum, item) => sum + item.job_count, 0);
  const ordered = ["critical", "high", "watch", "normal", "missing_budget"]
    .map((status) => counts.find((item) => item.status === status))
    .filter((item): item is StatusCount => item !== undefined);
  let cumulative = 0;
  const segments = ordered.map((item) => {
    const start = cumulative;
    cumulative += total ? item.job_count / total * 100 : 0;
    return `${STATUS_COLORS[item.status]} ${start}% ${cumulative}%`;
  });
  const ringStyle = {
    background: segments.length ? `conic-gradient(${segments.join(", ")})` : "#e7ebf0",
  } as CSSProperties;
  return (
    <div className="status-summary">
      <div className="status-ring" style={ringStyle}>
        <div>
          <strong>{total}</strong>
          <span>jobs</span>
        </div>
      </div>
      <div className="status-list">
        {ordered.map((item) => (
          <div className="status-item" key={item.status}>
            <span>
              <i style={{ background: STATUS_COLORS[item.status] }} />
              {titleCase(item.status)}
            </span>
            <strong>{item.job_count}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

interface RiskMatrixProps {
  jobs: JobSummary[];
  selectedJob: string | null;
  onSelect: (jobId: string) => void;
}

export function RiskMatrix({ jobs, selectedJob, onSelect }: RiskMatrixProps) {
  const points = jobs.filter(
    (job) => job.reported_progress_pct !== null && job.cost_spent_pct !== null,
  );
  const width = 720;
  const height = 336;
  const left = 58;
  const right = 24;
  const top = 18;
  const bottom = 48;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const yMaximum = Math.max(
    1,
    Math.ceil(Math.max(...points.map((job) => job.cost_spent_pct ?? 0), 1) * 4) / 4,
  );
  const varianceMaximum = Math.max(...points.map((job) => Math.max(job.projected_cost_variance, 0)), 1);
  const x = (value: number) => left + Math.min(Math.max(value, 0), 1) * plotWidth;
  const y = (value: number) => top + plotHeight - Math.min(Math.max(value, 0), yMaximum) / yMaximum * plotHeight;
  const yTicks = Array.from({ length: 5 }, (_, index) => (index / 4) * yMaximum);
  const xTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="chart-wrap">
      <svg className="matrix-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Cost spent versus job progress">
        <rect x={left} y={top} width={plotWidth} height={plotHeight} rx="12" fill="#f8faf7" />
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line x1={x(tick)} y1={top} x2={x(tick)} y2={top + plotHeight} stroke="#dfe6dc" />
            <text x={x(tick)} y={height - 20} textAnchor="middle" className="axis-label">{percent(tick)}</text>
          </g>
        ))}
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line x1={left} y1={y(tick)} x2={left + plotWidth} y2={y(tick)} stroke="#dfe6dc" />
            <text x={left - 10} y={y(tick) + 4} textAnchor="end" className="axis-label">{percent(tick)}</text>
          </g>
        ))}
        <line
          x1={x(0)}
          y1={y(0)}
          x2={x(Math.min(1, yMaximum))}
          y2={y(Math.min(1, yMaximum))}
          stroke="#66778d"
          strokeDasharray="6 6"
          strokeWidth="1.5"
        />
        <text x={x(0.72)} y={y(0.72) - 8} className="diagonal-label">cost = progress</text>
        {points.map((job) => {
          const radius = 5 + 7 * Math.sqrt(Math.max(job.projected_cost_variance, 0) / varianceMaximum);
          const selected = selectedJob === job.job_id;
          return (
            <circle
              key={job.job_id}
              cx={x(job.reported_progress_pct ?? 0)}
              cy={y(job.cost_spent_pct ?? 0)}
              r={selected ? radius + 3 : radius}
              fill={STATUS_COLORS[job.progress_status]}
              fillOpacity={selected ? 1 : 0.82}
              stroke={selected ? "#0e1b2e" : "#ffffff"}
              strokeWidth={selected ? 3 : 1.5}
              className="matrix-point"
              onClick={() => onSelect(job.job_id)}
            >
              <title>{`${job.job_id}: ${percent(job.reported_progress_pct)} complete, ${percent(job.cost_spent_pct)} cost spent`}</title>
            </circle>
          );
        })}
        <text x={left + plotWidth / 2} y={height - 2} textAnchor="middle" className="axis-title">Reported progress</text>
        <text transform={`translate(14 ${top + plotHeight / 2}) rotate(-90)`} textAnchor="middle" className="axis-title">Cost spent</text>
      </svg>
      <div className="chart-legend">
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <span key={status}><i style={{ background: color }} />{titleCase(status)}</span>
        ))}
      </div>
    </div>
  );
}

interface ParetoChartProps {
  points: ParetoPoint[];
}

export function ParetoChart({ points }: ParetoChartProps) {
  const visible = points.slice(0, 12);
  const width = 640;
  const height = 336;
  const left = 48;
  const right = 34;
  const top = 18;
  const bottom = 54;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maximum = Math.max(...visible.map((point) => point.exposure), 1);
  const slot = plotWidth / Math.max(visible.length, 1);
  const barWidth = Math.max(slot - 10, 10);
  const barX = (index: number) => left + index * slot + (slot - barWidth) / 2;
  const barY = (value: number) => top + plotHeight - value / maximum * plotHeight;
  const lineY = (value: number) => top + plotHeight - value * plotHeight;
  const linePoints = visible
    .map((point, index) => `${barX(index) + barWidth / 2},${lineY(point.cumulative_pct)}`)
    .join(" ");

  return (
    <div className="chart-wrap">
      <svg className="pareto-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Projected cost variance Pareto by job">
        {[0, 0.5, 1].map((tick) => (
          <g key={tick}>
            <line x1={left} y1={barY(maximum * tick)} x2={left + plotWidth} y2={barY(maximum * tick)} stroke="#dfe6dc" />
            <text x={left - 8} y={barY(maximum * tick) + 4} textAnchor="end" className="axis-label">{currency(maximum * tick)}</text>
          </g>
        ))}
        <line x1={left} y1={lineY(0.8)} x2={left + plotWidth} y2={lineY(0.8)} stroke="#e7bd25" strokeDasharray="5 5" />
        <text x={left + plotWidth - 2} y={lineY(0.8) - 6} textAnchor="end" className="pareto-threshold">80%</text>
        {visible.map((point, index) => (
          <g key={point.job_id}>
            <rect
              x={barX(index)}
              y={barY(point.exposure)}
              width={barWidth}
              height={top + plotHeight - barY(point.exposure)}
              rx="5"
              fill={index < 5 ? "#1f4fd8" : "#8aaaf6"}
            >
              <title>{`${point.job_id}: ${currency(point.exposure)} variance`}</title>
            </rect>
            <text x={barX(index) + barWidth / 2} y={height - 28} textAnchor="middle" className="job-axis-label">{point.job_id}</text>
          </g>
        ))}
        <polyline points={linePoints} fill="none" stroke="#0e1b2e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {visible.map((point, index) => (
          <circle key={`line-${point.job_id}`} cx={barX(index) + barWidth / 2} cy={lineY(point.cumulative_pct)} r="3.5" fill="#c6f135" stroke="#0e1b2e" strokeWidth="1.5" />
        ))}
      </svg>
      <div className="chart-legend">
        <span><i style={{ background: "#1f4fd8" }} />Projected cost variance</span>
        <span><i className="line-legend" />Cumulative share</span>
      </div>
    </div>
  );
}

export function MonthlyCostChart({ points }: { points: MonthlyCostPoint[] }) {
  const width = 820;
  const height = 320;
  const left = 52;
  const right = 36;
  const top = 18;
  const bottom = 48;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maximumMonthly = Math.max(
    ...points.flatMap((point) => [point.adjusted_actual_cost, point.forecast_remaining]),
    1,
  );
  const maximumCumulative = Math.max(
    ...points.map((point) => point.cumulative_adjusted_actual_cost),
    1,
  );
  const slot = plotWidth / Math.max(points.length, 1);
  const barWidth = Math.max(slot * 0.52, 4);
  const x = (index: number) => left + slot * index + slot / 2;
  const monthlyY = (value: number) => top + plotHeight - Math.max(value, 0) / maximumMonthly * plotHeight;
  const cumulativeY = (value: number) => top + plotHeight - value / maximumCumulative * plotHeight;
  const linePoints = points
    .map((point, index) => `${x(index)},${cumulativeY(point.cumulative_adjusted_actual_cost)}`)
    .join(" ");

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Monthly actual, forecast, and cumulative cost">
        {[0, 0.5, 1].map((tick) => (
          <g key={tick}>
            <line x1={left} y1={monthlyY(maximumMonthly * tick)} x2={left + plotWidth} y2={monthlyY(maximumMonthly * tick)} stroke="#dfe6dc" />
            <text x={left - 8} y={monthlyY(maximumMonthly * tick) + 4} textAnchor="end" className="axis-label">{currency(maximumMonthly * tick)}</text>
          </g>
        ))}
        {points.map((point, index) => {
          const actualHeight = top + plotHeight - monthlyY(point.adjusted_actual_cost);
          const forecastHeight = top + plotHeight - monthlyY(point.forecast_remaining);
          return (
            <g key={point.period}>
              <rect x={x(index) - barWidth / 2} y={monthlyY(point.adjusted_actual_cost)} width={barWidth} height={Math.max(actualHeight, 0)} rx="3" fill="#1f4fd8">
                <title>{`${point.period}: ${currency(point.adjusted_actual_cost)} adjusted actual`}</title>
              </rect>
              <rect x={x(index) - barWidth / 2} y={monthlyY(point.forecast_remaining)} width={barWidth} height={Math.max(forecastHeight, 0)} rx="3" fill="#b9c9f4" fillOpacity=".7">
                <title>{`${point.period}: ${currency(point.forecast_remaining)} forecast`}</title>
              </rect>
              {(index % 3 === 0 || index === points.length - 1) && (
                <text x={x(index)} y={height - 25} textAnchor="middle" className="job-axis-label">
                  {new Date(`${point.period}T00:00:00`).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
                </text>
              )}
            </g>
          );
        })}
        <polyline points={linePoints} fill="none" stroke="#0e1b2e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((point, index) => (
          <circle key={`cumulative-${point.period}`} cx={x(index)} cy={cumulativeY(point.cumulative_adjusted_actual_cost)} r="2.7" fill="#c6f135" stroke="#0e1b2e" strokeWidth="1" />
        ))}
      </svg>
      <div className="chart-legend">
        <span><i style={{ background: "#1f4fd8" }} />Adjusted actual</span>
        <span><i style={{ background: "#b9c9f4" }} />Forecast</span>
        <span><i className="line-legend" />Cumulative actual</span>
      </div>
    </div>
  );
}

export function CostCodeChart({ costCodes }: { costCodes: CostCodeDetail[] }) {
  const visible = costCodes.slice(0, 10);
  const width = 760;
  const rowHeight = 48;
  const top = 14;
  const bottom = 18;
  const labelWidth = 190;
  const valueWidth = 76;
  const plotWidth = width - labelWidth - valueWidth;
  const height = top + bottom + visible.length * rowHeight;
  const maximum = Math.max(
    ...visible.flatMap((item) => [item.current_budget, item.projected_cost]),
    1,
  );

  return (
    <div className="chart-wrap cost-code-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Budget and projected cost by cost code">
        {visible.map((item, index) => {
          const y = top + index * rowHeight;
          const budgetWidth = item.current_budget / maximum * plotWidth;
          const projectedWidth = item.projected_cost / maximum * plotWidth;
          return (
            <g key={item.cost_code}>
              <text x="0" y={y + 13} className="cost-code-name">{item.cost_code} · {item.description}</text>
              <rect x={labelWidth} y={y + 3} width={plotWidth} height="16" rx="5" fill="#edf1eb" />
              <rect x={labelWidth} y={y + 3} width={budgetWidth} height="16" rx="5" fill="#b8c2cf">
                <title>{`Budget ${currency(item.current_budget)}`}</title>
              </rect>
              <rect x={labelWidth} y={y + 23} width={projectedWidth} height="16" rx="5" fill={item.projected_variance > 0 ? "#e2756d" : "#4d9a72"}>
                <title>{`Projected ${currency(item.projected_cost)}`}</title>
              </rect>
              <text x={width - 2} y={y + 34} textAnchor="end" className={item.projected_variance > 0 ? "variance-label adverse" : "variance-label favorable"}>
                {currency(item.projected_variance)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="chart-legend">
        <span><i style={{ background: "#b8c2cf" }} />Current budget</span>
        <span><i style={{ background: "#e2756d" }} />Projected cost</span>
      </div>
    </div>
  );
}
