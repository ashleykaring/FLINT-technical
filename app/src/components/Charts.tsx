import type { CSSProperties } from "react";

import { currency, percent, titleCase } from "../format";
import type { JobSummary, ParetoPoint, ScenarioSummary, StatusCount } from "../types";

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
                title={`Contract value proxy ${currency(scenario.contract_value_proxy)}`}
              />
            </div>
            <div className="scenario-footnote">
              <span>Contract proxy {currency(scenario.contract_value_proxy)}</span>
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
        <span><i className="legend-marker" /> Contract value proxy</span>
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
