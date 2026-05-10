import React from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
import {
  fetchDataSources,
  fetchIngestionRuns,
  fetchTractsGeoJson,
  type TractFeature,
} from "./api";
import { FilterPanel } from "./components/FilterPanel";
import { IngestionStatus } from "./components/IngestionStatus";
import { MapView } from "./components/MapView";
import { TractDetailPanel } from "./components/TractDetailPanel";
import { useDashboardState } from "./useDashboardState";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

function Dashboard() {
  const initialTractsQuery = useQuery({
    queryKey: ["tracts-geojson", "counties"],
    queryFn: () => fetchTractsGeoJson({}),
  });
  const { counties, filters, selectedFeature, selectedGeoid, setFilters, setSelectedGeoid } =
    useDashboardState(initialTractsQuery.data);
  const tractsQuery = useQuery({
    queryKey: ["tracts-geojson", filters.county, filters.minScore],
    queryFn: () => fetchTractsGeoJson({ county: filters.county, minScore: filters.minScore }),
  });
  const runsQuery = useQuery({ queryKey: ["ingestion-runs"], queryFn: fetchIngestionRuns });
  const sourcesQuery = useQuery({ queryKey: ["data-sources"], queryFn: fetchDataSources });

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="eyebrow">Massachusetts</span>
          <h1>Civic Access Index</h1>
          <p>
            Operational dashboard for tract-level service gaps, source freshness, and
            explainable score drivers.
          </p>
        </div>
        <FilterPanel
          counties={counties}
          filters={filters}
          onChange={(nextFilters) => {
            setFilters(nextFilters);
            setSelectedGeoid(null);
          }}
        />
        <IngestionStatus runs={runsQuery.data?.results ?? []} sources={sourcesQuery.data?.results ?? []} />
      </aside>
      <section className="map-stage">
        <MapView
          data={tractsQuery.data}
          isLoading={tractsQuery.isLoading}
          error={tractsQuery.error}
          scoreType={filters.scoreType}
          selectedGeoid={selectedGeoid}
          onSelect={(feature: TractFeature) => setSelectedGeoid(feature.properties.geoid)}
        />
      </section>
      <TractDetailPanel feature={selectedFeature ?? null} scoreType={filters.scoreType} />
    </main>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
