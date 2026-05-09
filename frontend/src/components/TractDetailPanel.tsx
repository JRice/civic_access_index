export function TractDetailPanel() {
  return (
    <aside className="detail-panel">
      <h2>Tract Detail</h2>
      <div className="score-list">
        <div className="metric-row">
          <span>Civic Access Index</span>
          <strong>Pending</strong>
        </div>
        <div className="metric-row">
          <span>Healthcare gap</span>
          <strong>Pending</strong>
        </div>
        <div className="metric-row">
          <span>Food gap</span>
          <strong>Pending</strong>
        </div>
      </div>
      <p>Clicking a tract will show drivers, nearby amenities, provenance, and caveats.</p>
    </aside>
  );
}

