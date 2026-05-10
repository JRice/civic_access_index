import { useEffect, useMemo, useRef } from "react";
import maplibregl, {
  type ExpressionSpecification,
  type MapLayerMouseEvent,
  type MapGeoJSONFeature,
} from "maplibre-gl";
import type { ScoreType, TractFeature, TractFeatureCollection } from "../api";

type Props = {
  data: TractFeatureCollection | undefined;
  isLoading: boolean;
  error: Error | null;
  scoreType: ScoreType;
  selectedGeoid: string | null;
  onSelect: (feature: TractFeature) => void;
};

const SOURCE_ID = "tracts";
const FILL_LAYER_ID = "tract-fill";
const LINE_LAYER_ID = "tract-line";
const SELECTED_LAYER_ID = "tract-selected";

export function MapView({ data, isLoading, error, scoreType, selectedGeoid, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const colorExpression = useMemo<ExpressionSpecification>(
    () => [
      "case",
      ["==", ["get", scoreType], null],
      "#d7dbd4",
      ["interpolate", ["linear"], ["get", scoreType], 0, "#f3efe3", 35, "#b7d4c2", 65, "#4b9b86", 100, "#1c4d59"],
    ],
    [scoreType],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          basemap: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "OpenStreetMap contributors",
          },
        },
        layers: [{ id: "basemap", type: "raster", source: "basemap", paint: { "raster-opacity": 0.42 } }],
      },
      center: [-71.75, 42.18],
      zoom: 7,
      maxBounds: [
        [-74.5, 40.6],
        [-68.0, 43.4],
      ],
    });
    mapRef.current.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    const applyData = () => {
      const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(data);
        return;
      }
      map.addSource(SOURCE_ID, { type: "geojson", data, promoteId: "geoid" });
      map.addLayer({
        id: FILL_LAYER_ID,
        type: "fill",
        source: SOURCE_ID,
        paint: {
          "fill-color": colorExpression,
          "fill-opacity": 0.76,
        },
      });
      map.addLayer({
        id: LINE_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#41504a", "line-opacity": 0.34, "line-width": 0.7 },
      });
      map.addLayer({
        id: SELECTED_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#101820", "line-width": 3 },
        filter: ["==", ["get", "geoid"], ""],
      });
      map.on("click", FILL_LAYER_ID, (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as MapGeoJSONFeature | undefined;
        if (feature) onSelect(feature as unknown as TractFeature);
      });
      map.on("mouseenter", FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = "";
      });
    };
    if (map.loaded()) applyData();
    else map.once("load", applyData);
  }, [colorExpression, data, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer(FILL_LAYER_ID)) return;
    map.setPaintProperty(FILL_LAYER_ID, "fill-color", colorExpression);
  }, [colorExpression]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer(SELECTED_LAYER_ID)) return;
    map.setFilter(SELECTED_LAYER_ID, ["==", ["get", "geoid"], selectedGeoid ?? ""]);
  }, [selectedGeoid]);

  return (
    <div className="map-wrap">
      <div className="map-canvas" ref={containerRef} />
      <div className="map-overlay">
        <strong>{layerLabel(scoreType)}</strong>
        <span>{data?.features.length.toLocaleString() ?? 0} tracts</span>
      </div>
      {isLoading ? <div className="map-state">Loading tract geometry...</div> : null}
      {error ? <div className="map-state error">Map data failed: {error.message}</div> : null}
    </div>
  );
}

function layerLabel(scoreType: ScoreType) {
  return scoreType
    .replaceAll("_", " ")
    .replace("score", "")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
