# Data Sources

Initial source adapters:

- Census TIGER tract geometries (`census_tiger`)
- USDA Food Access Research Atlas
- CMS provider data
- OpenStreetMap amenities via Overpass

## Massachusetts Census Sources

`census_tiger` downloads the official Census TIGER/Line 2024 Massachusetts tract
shapefile from `www2.census.gov`, normalizes tract identifiers and
PostGIS-compatible multipolygon geometries, and upserts rows into
`census_tracts` by GEOID.

`census_acs` downloads official Census ACS 2024 5-year Data Profile tract rows
for Massachusetts from the Census API. It updates tract-level population and
vulnerability fields and writes idempotent `access_metrics` rows for:

- `poverty_count` / `poverty_rate`: `DP03_0128E` / `DP03_0128PE`
- `median_household_income`: `DP03_0062E`
- `no_vehicle_access_count` / `no_vehicle_access_rate`: `DP04_0058E` / `DP04_0058PE`
- `disability_count` / `disability_rate`: `DP02_0072E` / `DP02_0072PE`
- `age_65_plus_count` / `age_65_plus_rate`: `DP05_0024E` / `DP05_0024PE`
- `total_population`: `DP05_0001E`, persisted on `census_tracts.population`

Rates are stored as unit rates from 0 to 1. No Census API key is required for the
current Massachusetts-only implementation, but upstream API availability and rate
limits still apply.

Second-phase adapters:

- GTFS transit feeds
- FCC broadband availability data
- HRSA facility datasets
