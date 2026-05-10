const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type ScoreType =
  | "civic_access_index"
  | "healthcare_access_score"
  | "food_access_score"
  | "transit_access_score"
  | "vulnerability_score";

export type TractFeatureProperties = {
  geoid: string;
  name: string | null;
  state_fips: string;
  county_fips: string;
  population: number | null;
  civic_access_index: number | null;
  healthcare_access_score: number | null;
  food_access_score: number | null;
  transit_access_score: number | null;
  vulnerability_score: number | null;
};

export type TractFeature = GeoJSON.Feature<GeoJSON.Geometry, TractFeatureProperties>;

export type TractFeatureCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  TractFeatureProperties
>;

export type IngestionRun = {
  id: string;
  data_source_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  records_seen: number;
  records_created: number;
  records_updated: number;
  records_rejected: number;
  raw_snapshot_uri: string | null;
  error_summary: string | null;
};

export type DataSource = {
  id: string;
  name: string;
  source_type: string;
  enabled: boolean;
  last_success_at: string | null;
  last_failure_at: string | null;
};

export type TractMetric = {
  metric_name: string;
  metric_value: number | null;
  metric_unit: string | null;
  percentile_statewide: number | null;
  status: string;
  caveat: string | null;
};

export type ScoreComponent = {
  score: number | null;
  weight: number;
  status: string;
  metric_count: number;
};

export type ScoreExplanation = {
  tract_geoid: string;
  composite_score: number;
  score_version: string;
  methodology: string | null;
  component_scores: Record<string, ScoreComponent>;
  missing_components: string[];
  main_drivers: Array<{
    metric: string;
    value: number | string | null;
    percentile: number | null;
    interpretation: string;
  }>;
  limitations: string[];
};

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function fetchTractsGeoJson(params: {
  county?: string;
  minScore?: number;
}): Promise<TractFeatureCollection> {
  const search = new URLSearchParams({ state: "25", limit: "5000" });
  if (params.county) search.set("county", params.county);
  if (params.minScore !== undefined) search.set("min_score", String(params.minScore));
  return fetchJson(`/api/tracts.geojson?${search.toString()}`);
}

export function fetchIngestionRuns(): Promise<{ results: IngestionRun[] }> {
  return fetchJson("/api/ingestion-runs?limit=8");
}

export function fetchDataSources(): Promise<{ results: DataSource[] }> {
  return fetchJson("/api/data-sources");
}

export function fetchTractMetrics(geoid: string): Promise<{
  tract_geoid: string;
  tract_name: string | null;
  metrics: TractMetric[];
  caveats: string[];
}> {
  return fetchJson(`/api/tracts/${geoid}/metrics`);
}

export function fetchTractExplanation(geoid: string): Promise<ScoreExplanation> {
  return fetchJson(`/api/tracts/${geoid}/explanation`);
}
