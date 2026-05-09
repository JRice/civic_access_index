# Scoring Methodology

The first Civic Access Index version uses transparent weighted subscores:

```text
0.35 * healthcare_gap_score
+ 0.25 * food_gap_score
+ 0.20 * transit_gap_score
+ 0.20 * socioeconomic_vulnerability_score
```

Subscores are percentile-normalized at the tract level. The platform should expose the
metric values, percentile ranks, source provenance, and known limitations behind every
score.

## Milestone 4 Metric Ingredients

Milestone 4 does not compute the final Civic Access Index. It writes reusable
tract-level ingredients into `access_metrics`:

- `nearest_healthcare_amenity_distance_m`
- `healthcare_amenities_within_1mi`
- `healthcare_amenities_within_2mi`
- `nearest_pharmacy_distance_m`
- `nearest_food_access_distance_m`
- `food_access_amenities_within_1mi`
- `food_access_amenities_within_2mi`
- `nearest_transit_stop_distance_m`, when mapped transit stops exist
- `transit_stops_within_half_mi`, when mapped transit stops exist
- `vulnerability_poverty_rate`
- `vulnerability_no_vehicle_household_rate`
- `vulnerability_age_65_plus_rate`
- `vulnerability_disability_rate`
- `vulnerability_median_household_income`

Distances use `ST_PointOnSurface` for the tract representative point and PostGIS
geography casts so values are in meters. Higher statewide percentile means more
gap or vulnerability: longer distances rank higher, lower amenity counts rank
higher, and median household income is inverted so lower income ranks as more
vulnerable.

CMS hospital providers are address-only in the current official source and are not
used for spatial distance calculations. OSM healthcare amenities currently drive
mapped healthcare proximity.

## Milestone 5 Subscores and Explanations

The recompute task now rolls available metric percentiles into persisted
`access_scores` rows:

- `healthcare_access_score`: average of healthcare distance/count and pharmacy
  percentiles.
- `food_access_score`: average of food distance/count percentiles.
- `transit_access_score`: average of transit proximity percentiles, when transit
  stop data exists.
- `vulnerability_score`: average of ACS vulnerability percentiles.
- `civic_access_index` / `composite_score`: weighted blend using the V1 weights,
  renormalized across available components when a component is missing.

Explanation payloads are stored on `access_scores.explanation_json`. The main
drivers are the highest-percentile metric ingredients for the tract, and
limitations call out OSM coverage, straight-line distance limitations, CMS null
geometry, and missing transit data when applicable.

This is not a definitive equity model or policy recommendation. It is an inspectable
public-interest data system for surfacing potential service gaps.
