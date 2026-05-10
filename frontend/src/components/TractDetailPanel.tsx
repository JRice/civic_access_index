import { useQuery } from "@tanstack/react-query";
import { fetchTractExplanation, fetchTractMetrics, type ScoreType, type TractFeature } from "../api";

type Props = {
  feature: TractFeature | null;
  scoreType: ScoreType;
};

export function TractDetailPanel({ feature, scoreType }: Props) {
  const geoid = feature?.properties.geoid;
  const metricsQuery = useQuery({
    queryKey: ["tract-metrics", geoid],
    queryFn: () => fetchTractMetrics(geoid!),
    enabled: Boolean(geoid),
  });
  const explanationQuery = useQuery({
    queryKey: ["tract-explanation", geoid],
    queryFn: () => fetchTractExplanation(geoid!),
    enabled: Boolean(geoid),
  });

  return (
    <aside className="detail-panel">
      <div className="section-heading">
        <h2>Tract Detail</h2>
        {geoid ? <span>{geoid}</span> : <span>Select a tract</span>}
      </div>
      {!feature ? (
        <div className="empty-state">
          Pick a tract on the map to inspect score components, drivers, and caveats.
        </div>
      ) : (
        <>
          <div className="score-hero">
            <span>{layerLabel(scoreType)}</span>
            <strong>{formatScore(feature.properties[scoreType])}</strong>
          </div>
          <div className="score-list">
            <MetricRow label="Civic Access Index" value={feature.properties.civic_access_index} />
            <MetricRow label="Healthcare gap" value={feature.properties.healthcare_access_score} />
            <MetricRow label="Food gap" value={feature.properties.food_access_score} />
            <MetricRow label="Transit gap" value={feature.properties.transit_access_score} />
            <MetricRow label="Vulnerability" value={feature.properties.vulnerability_score} />
          </div>
          <section className="panel-section compact">
            <h3>Top Drivers</h3>
            <div className="driver-list">
              {explanationQuery.data?.main_drivers.slice(0, 4).map((driver) => (
                <div className="driver-row" key={driver.metric}>
                  <strong>{prettyMetric(driver.metric)}</strong>
                  <span>{formatScore(driver.percentile)} pct</span>
                  <small>{driver.interpretation}</small>
                </div>
              ))}
            </div>
          </section>
          <section className="panel-section compact">
            <h3>Metric Snapshot</h3>
            {(metricsQuery.data?.metrics ?? [])
              .filter((metric) => metric.status === "available")
              .slice(0, 6)
              .map((metric) => (
                <div className="metric-row" key={metric.metric_name}>
                  <span>{prettyMetric(metric.metric_name)}</span>
                  <strong>{formatValue(metric.metric_value, metric.metric_unit)}</strong>
                </div>
              ))}
          </section>
          <section className="panel-section compact">
            <h3>Limitations</h3>
            <ul className="limitations">
              {(explanationQuery.data?.limitations ?? []).slice(0, 4).map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </section>
        </>
      )}
    </aside>
  );
}

function MetricRow({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>{formatScore(value)}</strong>
    </div>
  );
}

function formatScore(value: number | null | undefined) {
  return value === null || value === undefined ? "N/A" : value.toFixed(1);
}

function formatValue(value: number | null, unit: string | null) {
  if (value === null) return "N/A";
  if (unit === "meters") return `${Math.round(value).toLocaleString()} m`;
  if (unit === "rate") return `${(value * 100).toFixed(1)}%`;
  if (unit === "dollars") return `$${Math.round(value).toLocaleString()}`;
  return value.toLocaleString();
}

function prettyMetric(metric: string) {
  return metric.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function layerLabel(scoreType: ScoreType) {
  return prettyMetric(scoreType).replace("Score", "");
}
