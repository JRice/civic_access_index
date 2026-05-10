import type { DataSource, IngestionRun } from "../api";

type Props = {
  runs: IngestionRun[];
  sources: DataSource[];
};

export function IngestionStatus({ runs, sources }: Props) {
  return (
    <section className="panel-section">
      <div className="section-heading">
        <h2>Data Operations</h2>
        <span>{runs.length} recent</span>
      </div>
      <div className="status-list">
        {sources.slice(0, 5).map((source) => (
          <div className="status-row" key={source.id}>
            <div>
              <strong>{source.name}</strong>
              <span>{source.source_type}</span>
            </div>
            <span className={source.last_success_at ? "pill success" : "pill muted"}>
              {source.last_success_at ? "ready" : "pending"}
            </span>
          </div>
        ))}
      </div>
      <div className="run-list">
        {runs.slice(0, 4).map((run) => (
          <div className="run-row" key={run.id}>
            <span className={`status-dot ${run.status}`} />
            <span>{run.status}</span>
            <strong>{run.records_seen.toLocaleString()} rows</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
