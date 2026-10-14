const sources = [
  { extension: "CSV", title: "Job reference", detail: "Job identity and portfolio attributes" },
  { extension: "CSV · JSON", title: "Cost budgets", detail: "Estimate and API snapshot" },
  { extension: "CSV", title: "Cost ledger", detail: "Actual, committed, and forecast cost" },
  { extension: "CSV · XLSX", title: "Delivery logs", detail: "Schedule and equipment activity" },
  { extension: "JSONL", title: "Correspondence", detail: "1,200 unstructured project records" },
];

function FlowArrow({ label }: { label?: string }) {
  return (
    <div className="flow-arrow" aria-hidden="true">
      {label && <span>{label}</span>}
      <i />
      <b>↓</b>
    </div>
  );
}

function DataFlowPage() {
  return (
    <div className="data-flow-page">
      <header className="page-header data-flow-header">
        <div>
          <p className="eyebrow">System architecture</p>
          <h1>Data flow</h1>
          <p>From fragmented project files to governed, decision-ready evidence.</p>
        </div>
      </header>

      <section className="blueprint" aria-label="FLINT analytical data flow">
        <div className="blueprint-title">
          <div>
            <span className="drawing-number">DF–01</span>
            <p>Portfolio intelligence pipeline</p>
          </div>
          <span className="blueprint-status"><i />Reproducible build</span>
        </div>

        <div className="source-grid">
          {sources.map((source, index) => (
            <article className={index === sources.length - 1 ? "source-ai" : ""} key={source.title}>
              <span>{source.extension}</span>
              <strong>{source.title}</strong>
              <small>{source.detail}</small>
            </article>
          ))}
        </div>

        <FlowArrow label="Raw inputs" />

        <div className="foundation-row">
          <article className="flow-stage">
            <span className="stage-number">01</span>
            <div><p>Ingest &amp; validate</p><strong>Parse · type · deduplicate</strong></div>
            <em>Quality exceptions retained</em>
          </article>
          <div className="horizontal-flow"><i /><b>→</b></div>
          <article className="flow-stage">
            <span className="stage-number">02</span>
            <div><p>Standardize &amp; reconcile</p><strong>Canonical jobs · codes · vendors</strong></div>
            <em>Aliases resolved deterministically</em>
          </article>
        </div>

        <FlowArrow label="Two controlled paths" />

        <div className="processing-lanes">
          <article className="processing-lane deterministic-lane">
            <div className="lane-heading">
              <span>Deterministic</span>
              <div><strong>Structured project data</strong><small>Budgets · costs · schedules · equipment</small></div>
            </div>
            <div className="lane-flow">
              <span>Stage</span><b>→</b><span>Conform</span><b>→</b><span>Model</span>
            </div>
            <p>Business rules calculate financial, progress, equipment, and exposure metrics without LLM involvement.</p>
          </article>

          <article className="processing-lane ai-lane">
            <div className="lane-heading">
              <span>AI assisted</span>
              <div><strong>Project correspondence</strong><small>1,200 documents → 1,307 typed events</small></div>
            </div>
            <div className="lane-flow">
              <span>Extract</span><b>→</b><span>Validate</span><b>→</b><span>Resolve IDs</span>
            </div>
            <p>Schema-constrained extraction finds financial and schedule signals; evidence and deterministic normalization remain auditable.</p>
          </article>
        </div>

        <div className="merge-flow" aria-hidden="true">
          <span /><span /><i /><b>↓</b>
        </div>

        <article className="warehouse-stage">
          <div className="warehouse-icon"><span /><span /><span /></div>
          <div>
            <p>Governed analytical model</p>
            <h2>DuckDB dimensions, facts &amp; marts</h2>
            <small>One reconciled source for financial, delivery, equipment, and correspondence analysis</small>
          </div>
          <dl>
            <div><dt>Jobs</dt><dd>42</dd></div>
            <div><dt>Cost codes</dt><dd>21</dd></div>
            <div><dt>Subcontractors</dt><dd>60</dd></div>
            <div><dt>Checks passing</dt><dd>21 / 21</dd></div>
          </dl>
        </article>

        <FlowArrow label="Read-only delivery" />

        <div className="delivery-row">
          <article>
            <span>API</span>
            <strong>FastAPI</strong>
            <small>Typed, read-only endpoints</small>
          </article>
          <div className="horizontal-flow"><i /><b>→</b></div>
          <article className="delivery-destination">
            <span>React</span>
            <strong>Decision workspace</strong>
            <div><em>Portfolio</em><em>Assessment findings</em><em>Job details</em></div>
          </article>
        </div>

        <div className="control-strip">
          <span><i />Source lineage</span>
          <span><i />Schema validation</span>
          <span><i />Canonical identities</span>
          <span><i />Reconciliation checks</span>
          <span><i />Evidence retained</span>
        </div>
      </section>
    </div>
  );
}

export default DataFlowPage;
