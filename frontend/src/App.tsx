import React from "react";
import { createRoot } from "react-dom/client";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
import { FilterPanel } from "./components/FilterPanel";
import { IngestionStatus } from "./components/IngestionStatus";
import { MapView } from "./components/MapView";
import { TractDetailPanel } from "./components/TractDetailPanel";

function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <h1>Civic Access Index</h1>
        <FilterPanel />
        <IngestionStatus />
      </aside>
      <section className="map-stage">
        <MapView />
      </section>
      <TractDetailPanel />
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

