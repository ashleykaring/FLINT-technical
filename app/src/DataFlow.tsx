import { useEffect, useState } from "react";

interface FlowDetailItem {
  name: string;
  grain: string;
  purpose: string;
}

interface FlowDetail {
  eyebrow: string;
  title: string;
  summary?: string;
  items: FlowDetailItem[];
}

const sources = [
  {
    extension: "CSV",
    title: "Job reference",
    filename: "jobs_reference.csv",
    system: "Construction ERP",
  },
  {
    extension: "JSON + CSV",
    title: "Estimates & budgets",
    filename: "API export + validation copy",
    system: "SaaS estimating",
  },
  {
    extension: "CSV",
    title: "Job cost ledger",
    filename: "job_cost_ledger.csv",
    system: "Construction ERP",
  },
  {
    extension: "CSV",
    title: "Schedule activities",
    filename: "schedule_activities.csv",
    system: "P6 / MS Project",
  },
  {
    extension: "XLSX",
    title: "Equipment usage",
    filename: "equipment_rental_log.xlsx",
    system: "Operations spreadsheet",
  },
  {
    extension: "JSONL",
    title: "Project correspondence",
    filename: "project_correspondence.jsonl",
    system: "PM document system",
  },
];

const stageDetails: Record<string, FlowDetail> = {
  raw: {
    eyebrow: "Landing layer",
    title: "Raw DuckDB tables",
    items: [
      {
        name: "raw_jobs",
        grain: "One supplied job-reference row",
        purpose: "Preserves ERP job attributes exactly as delivered.",
      },
      {
        name: "raw_estimate_api_line_items",
        grain: "One nested API estimate line",
        purpose: "Flattens the authoritative estimating API payload.",
      },
      {
        name: "raw_estimate_csv",
        grain: "One flattened estimate line",
        purpose: "Retains the supplied CSV used to reconcile the API extract.",
      },
      {
        name: "raw_job_cost_ledger",
        grain: "One supplied ERP posting row",
        purpose:
          "Lands actual, adjustment, committed, and forecast transactions.",
      },
      {
        name: "raw_schedule_activities",
        grain: "One supplied schedule activity",
        purpose: "Preserves baseline, actual, and completion fields.",
      },
      {
        name: "raw_equipment",
        grain: "One supplied equipment assignment",
        purpose:
          "Lands ownership, rate, utilization, and production information.",
      },
      {
        name: "raw_correspondence",
        grain: "One source document",
        purpose: "Retains the original RFI, change-order, or field-log text.",
      },
    ],
  },
  staging: {
    eyebrow: "Standardization layer",
    title: "Cleaned staging tables",
    summary:
      "Types, identifiers, dates, and quality flags are standardized while source exceptions remain visible for reconciliation.",
    items: [
      {
        name: "stg_jobs",
        grain: "One standardized job",
        purpose:
          "Normalizes job attributes, dates, budgets, progress, and manager IDs.",
      },
      {
        name: "stg_estimates",
        grain: "One job and estimating cost-code line",
        purpose: "Types budget amounts and validates the API against the CSV.",
      },
      {
        name: "stg_job_cost_ledger",
        grain: "One typed ledger row",
        purpose: "Flags duplicates, invalid keys, and unmapped ERP cost codes.",
      },
      {
        name: "stg_schedule_activities",
        grain: "One parsed schedule activity",
        purpose: "Derives job references and standardizes dates and progress.",
      },
      {
        name: "stg_equipment",
        grain: "One cleaned equipment assignment",
        purpose:
          "Normalizes job IDs, ownership, cost, utilization, and production.",
      },
      {
        name: "stg_correspondence",
        grain: "One normalized source document",
        purpose:
          "Prepares document IDs, types, and text for controlled extraction.",
      },
    ],
  },
  references: {
    eyebrow: "Governance",
    title: "Reference mappings",
    summary: "Crosswalks resolve incompatible identifiers and taxonomies.",
    items: [
      {
        name: "ref_cost_code_map",
        grain: "One ERP cost code",
        purpose: "Maps ledger codes to the canonical estimating taxonomy.",
      },
      {
        name: "ref_correspondence_job_alias",
        grain: "One normalized job alias",
        purpose: "Resolves project nicknames to canonical job IDs.",
      },
      {
        name: "ref_correspondence_scope_cost_code",
        grain: "One normalized scope and division",
        purpose: "Maps extracted scope to a canonical cost code.",
      },
    ],
  },
  dimensions: {
    eyebrow: "Core entities",
    title: "Dimensions",
    summary:
      "Reusable business entities provide consistent keys and labels across facts and analytical outputs.",
    items: [
      {
        name: "dim_job",
        grain: "One job",
        purpose: "Carries division, contract, manager, budget, and progress.",
      },
      {
        name: "dim_cost_code",
        grain: "One cost code, plus unmapped",
        purpose:
          "Provides a shared taxonomy for budgets, costs, and correspondence.",
      },
      {
        name: "dim_subcontractor",
        grain: "One normalized subcontractor, plus unknown",
        purpose: "Conforms vendor identities across ledger and correspondence.",
      },
    ],
  },
  facts: {
    eyebrow: "Business events",
    title: "Primary facts",
    summary:
      "Five event tables retain the activity used by the analytical marts.",
    items: [
      {
        name: "fact_cost_transaction",
        grain: "One nonduplicate ERP posting",
        purpose: "Stores actual, adjustment, committed, and forecast costs.",
      },
      {
        name: "fact_budget",
        grain: "One job and cost-code budget line",
        purpose: "Stores original and current budget values.",
      },
      {
        name: "fact_schedule_activity",
        grain: "One schedule activity",
        purpose: "Stores baseline, actual, completion, and delay information.",
      },
      {
        name: "fact_equipment_usage",
        grain: "One valid equipment assignment",
        purpose: "Stores cost, utilization, production, and cost per unit.",
      },
      {
        name: "fact_correspondence_event_current",
        grain: "One current cleaned correspondence event",
        purpose: "Stores governed financial and schedule signals from text.",
      },
    ],
  },
  ai: {
    eyebrow: "AI path",
    title: "Correspondence extraction",
    summary:
      "Gemini creates a schema-constrained extraction. Schema validation, alias resolution, and current-version selection happen before analysis.",
    items: [
      {
        name: "ai_correspondence_extractions",
        grain: "One cached response per document fingerprint",
        purpose: "Retains model, prompt, schema, source hash, and response.",
      },
      {
        name: "ai_correspondence_extraction_current",
        grain: "One selected extraction per document",
        purpose: "Prevents prompt iterations from duplicating documents.",
      },
      {
        name: "fact_correspondence_event_current",
        grain: "One governed event in a current document",
        purpose: "Applies cleanup and canonical entity resolution.",
      },
    ],
  },
  marts: {
    eyebrow: "Decision layer",
    title: "Major analytical marts",
    summary:
      "Analysis-ready tables that turn cleaned data into decision-focused metrics.",
    items: [
      {
        name: "mart_job_financial",
        grain: "One job",
        purpose:
          "Combines budget, incurred cost, forecast, projected cost, and variance.",
      },
      {
        name: "mart_cost_vs_progress",
        grain: "One job",
        purpose: "Compares cost consumed with reported physical progress.",
      },
      {
        name: "mart_job_risk_adjusted",
        grain: "One job",
        purpose: "Calculates base, confirmed-adjusted, and downside scenarios.",
      },
      {
        name: "mart_job_dashboard",
        grain: "One job",
        purpose: "Provides the executive summary and explainable risk status.",
      },
      {
        name: "mart_correspondence_exposure",
        grain: "One governed correspondence event",
        purpose: "Classifies commercial and schedule exposure.",
      },
      {
        name: "mart_equipment_economics",
        grain: "One division and ownership type",
        purpose: "Compares utilization and cost per production unit.",
      },
      {
        name: "mart_monthly_cost_trend",
        grain: "One month, job, and cost code",
        purpose: "Supports monthly and cumulative job cost trends.",
      },
      {
        name: "mart_subcontractor_combined_exposure",
        grain: "One normalized subcontractor",
        purpose: "Shows ledger and correspondence concentration separately.",
      },
    ],
  },
  api: {
    eyebrow: "Serving layer",
    title: "FastAPI endpoints",
    items: [
      {
        name: "GET /api/portfolio",
        grain: "One filtered portfolio response",
        purpose:
          "Returns KPIs, scenarios, risk charts, filters, and job queue.",
      },
      {
        name: "GET /api/jobs/{job_id}",
        grain: "One selected job response",
        purpose:
          "Returns financial, schedule, cost-code, and correspondence detail.",
      },
      {
        name: "GET /api/equipment",
        grain: "One filtered equipment response",
        purpose: "Returns economics, utilization comparisons, and assignments.",
      },
      {
        name: "GET /api/insights",
        grain: "One portfolio findings response",
        purpose: "Returns evidence supporting the assessment conclusions.",
      },
    ],
  },
};

function FlowArrow({ label }: { label?: string }) {
  return (
    <div className="flow-arrow" aria-hidden="true">
      {label && <span>{label}</span>}
      <i />
      <b>↓</b>
    </div>
  );
}

function StageButton({
  detailKey,
  eyebrow,
  title,
  description,
  count,
  tone = "blue",
  onOpen,
}: {
  detailKey: string;
  eyebrow: string;
  title: string;
  description: string;
  count: string;
  tone?: "blue" | "lime";
  onOpen: (detailKey: string) => void;
}) {
  return (
    <button
      className={`architecture-stage architecture-${tone}`}
      type="button"
      onClick={() => onOpen(detailKey)}
    >
      <span>{eyebrow}</span>
      <strong>{title}</strong>
      <small>{description}</small>
      <em>{count} · View details →</em>
    </button>
  );
}

function FlowDetailModal({
  detail,
  onClose,
}: {
  detail: FlowDetail;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="flow-detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="flow-detail-title"
      >
        <button
          className="modal-close"
          type="button"
          onClick={onClose}
          aria-label="Close data-flow details"
        >
          ×
        </button>
        <p className="eyebrow">{detail.eyebrow}</p>
        <h2 id="flow-detail-title">{detail.title}</h2>
        {detail.summary && (
          <p className="flow-detail-summary">{detail.summary}</p>
        )}
        <div className="flow-detail-head" aria-hidden="true">
          <span>Table or endpoint</span>
          <span>Grain or contract</span>
          <span>Role</span>
        </div>
        <div className="flow-detail-list">
          {detail.items.map((item) => (
            <article key={item.name}>
              <code>{item.name}</code>
              <strong>{item.grain}</strong>
              <p>{item.purpose}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function DataFlowPage() {
  const [activeDetail, setActiveDetail] = useState<string | null>(null);
  const detail = activeDetail ? stageDetails[activeDetail] : null;

  return (
    <div className="data-flow-page">
      <header className="page-header data-flow-header">
        <div>
          <p className="eyebrow">System architecture</p>
          <h1>Data flow</h1>
        </div>
      </header>

      <section className="blueprint" aria-label="FLINT analytical data flow">
        <div className="source-grid">
          {sources.map((source, index) => (
            <article
              className={index === sources.length - 1 ? "source-ai" : ""}
              key={source.title}
            >
              <span>{source.extension}</span>
              <strong>{source.title}</strong>
              <small>{source.filename}</small>
              <em>{source.system}</em>
            </article>
          ))}
        </div>

        <FlowArrow label="Land supplied files" />

        <div className="landing-layers">
          <StageButton
            detailKey="raw"
            eyebrow="01 · Raw landing"
            title="Source-aligned DuckDB tables"
            description="Original values retained before business transformations"
            count="7 physical tables"
            onOpen={setActiveDetail}
          />
          <div className="horizontal-flow" aria-hidden="true">
            <b>→</b>
          </div>
          <StageButton
            detailKey="staging"
            eyebrow="02 · Standardize"
            title="Cleaned staging tables"
            description="Typed fields, normalized identifiers, and visible quality flags"
            count="6 primary tables"
            onOpen={setActiveDetail}
          />
        </div>

        <FlowArrow label="Conform business entities" />

        <section className="model-layer" aria-label="Governed DuckDB model">
          <div className="model-layer-heading">
            <span>03 · Governed model</span>
            <strong>DuckDB dimensional layer</strong>
            <small>
              Reviewed mappings connect reusable entities to measurable business
              events.
            </small>
          </div>

          <div className="model-stage-row">
            <StageButton
              detailKey="references"
              eyebrow="Crosswalks"
              title="Reference mappings"
              description="Codes, aliases, and scope resolution"
              count="3 tables"
              onOpen={setActiveDetail}
            />
            <div className="model-link" aria-hidden="true">
              →
            </div>
            <StageButton
              detailKey="dimensions"
              eyebrow="Shared entities"
              title="Dimensions"
              description="Canonical jobs, cost codes, and subcontractors"
              count="3 tables"
              onOpen={setActiveDetail}
            />
            <div className="model-link" aria-hidden="true">
              →
            </div>
            <StageButton
              detailKey="facts"
              eyebrow="Measurable activity"
              title="Primary facts"
              description="Financial, schedule, equipment, and correspondence events"
              count="5 tables"
              onOpen={setActiveDetail}
            />
          </div>

          <button
            className="ai-extraction-path"
            type="button"
            onClick={() => setActiveDetail("ai")}
          >
            <div>
              <span>AI-assisted correspondence path</span>
              <strong>Staged documents</strong>
            </div>
            <b>→</b>
            <em>Gemini extraction</em>
            <b>→</b>
            <em>Schema validation</em>
            <b>→</b>
            <em>Resolve identities</em>
            <b>→</b>
            <div>
              <span>Governed output</span>
              <strong>Correspondence fact</strong>
            </div>
            <small>View controls and tables →</small>
          </button>
        </section>

        <FlowArrow label="Aggregate" />

        <StageButton
          detailKey="marts"
          eyebrow="04 · Analytical layer"
          title="DuckDB marts"
          description="Question-ready financial, delivery, equipment, and exposure models"
          count="8 major marts"
          tone="lime"
          onOpen={setActiveDetail}
        />

        <FlowArrow />

        <div className="delivery-row">
          <button
            className="delivery-api"
            type="button"
            onClick={() => setActiveDetail("api")}
          >
            <span>05 · API</span>
            <strong>FastAPI</strong>
            <em>View endpoints →</em>
          </button>
          <div className="horizontal-flow" aria-hidden="true">
            <b>→</b>
          </div>
          <article className="delivery-destination">
            <span>06 · Consumer</span>
            <strong>Portfolio dashboard</strong>
            <small>Decision-ready operating views</small>
          </article>
        </div>
      </section>

      {detail && (
        <FlowDetailModal
          detail={detail}
          onClose={() => setActiveDetail(null)}
        />
      )}
    </div>
  );
}

export default DataFlowPage;
