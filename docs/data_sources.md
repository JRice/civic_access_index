# Data Sources

Initial source adapters:

- Census TIGER tract geometries (`census_tiger`)
- Census ACS demographic and vulnerability fields (`census_acs`)
- USDA Food Access Research Atlas
- CMS provider data (`cms_providers`)
- OpenStreetMap amenities via Overpass (`osm_overpass`)

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

## Massachusetts OSM Amenities

`osm_overpass` queries the public Overpass API for Massachusetts OpenStreetMap
nodes, ways, and relations in these groups:

- Healthcare: `hospital`, `clinic`, `doctors`, `dentist`, `pharmacy`
- Food access: `supermarket`, `grocery`, `convenience`, `food_bank`
- Civic services: `library`, `community_centre`, `social_facility`

Ways and relations use the `center` coordinates returned by Overpass. Records are
upserted by source and stable OSM id (`osm:{type}/{id}`), with tags preserved in
`raw_payload_json`. Overpass is a shared public service, so the adapter uses
timeouts, retries, and modest backoff; avoid aggressive refresh schedules.

## Massachusetts CMS Providers

`cms_providers` reads the official CMS Provider Data API Hospital General
Information dataset (`xubh-q36u`) and filters rows to Massachusetts. It persists
hospital facility id, name, hospital type, address, city, state, ZIP, phone,
county, rating, ownership, emergency-services metadata, and source provenance.

The CMS dataset has address fields but no latitude/longitude. Geocoding is skipped
for now to avoid adding a paid API dependency or inventing coordinates; provider
`location` is intentionally null.

Second-phase adapters:

- GTFS transit feeds
- FCC broadband availability data
- HRSA facility datasets
