export function IngestionStatus() {
  return (
    <section>
      <h2>Data Operations</h2>
      <div className="status-list">
        <div className="metric-row">
          <span>Census ACS</span>
          <strong>Queued</strong>
        </div>
        <div className="metric-row">
          <span>OSM amenities</span>
          <strong>Queued</strong>
        </div>
        <div className="metric-row">
          <span>CMS providers</span>
          <strong>Queued</strong>
        </div>
      </div>
    </section>
  );
}

