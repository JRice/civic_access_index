import { useMemo, useState } from "react";
import type { ScoreType, TractFeatureCollection } from "./api";

export type DashboardFilters = {
  county: string;
  scoreType: ScoreType;
  minScore: number;
};

export function useDashboardState(tracts: TractFeatureCollection | undefined) {
  const [filters, setFilters] = useState<DashboardFilters>({
    county: "",
    scoreType: "civic_access_index",
    minScore: 0,
  });
  const [selectedGeoid, setSelectedGeoid] = useState<string | null>(null);

  const counties = useMemo(() => {
    const countySet = new Set<string>();
    tracts?.features.forEach((feature) => countySet.add(feature.properties.county_fips));
    return [...countySet].sort();
  }, [tracts]);

  const selectedFeature = useMemo(
    () => tracts?.features.find((feature) => feature.properties.geoid === selectedGeoid),
    [selectedGeoid, tracts],
  );

  return {
    counties,
    filters,
    selectedFeature,
    selectedGeoid,
    setFilters,
    setSelectedGeoid,
  };
}
