# Civic Access Index

Civic Access Index is a Python-based geospatial data platform for identifying census
tracts with overlapping access gaps in healthcare, food, transportation, and
socioeconomic vulnerability.

The project is designed as an operational data system rather than a consumer-facing
app: it includes asynchronous ingestion workers, source-level provenance,
data-quality tracking, PostGIS analysis, cached APIs, searchable entities,
infrastructure-as-code deployment, and a lightweight internal dashboard.

## System Shape

```mermaid
flowchart TD
    sources["Public APIs and datasets<br/>Census, USDA, CMS, OSM, GTFS"] --> workers["Celery ingestion workers"]
    workers --> snapshots["Raw data snapshots<br/>S3 or local object storage"]
    workers --> postgis["PostgreSQL + PostGIS<br/>normalized civic entities"]
    postgis --> analysis["Analysis and scoring engine"]
    analysis --> api["FastAPI REST API"]
    api --> redis["Redis cache"]
    api --> search["OpenSearch"]
    api --> dashboard["Internal dashboard<br/>map, filters, data operations"]
```

## Subsystems

1. **Ingestion**: source adapters fetch public datasets, persist raw snapshots, create
   auditable ingestion runs, and record rejected rows as data-quality issues.
2. **Normalization**: canonicalizes categories, addresses, providers, tract geography,
   and public-source payloads into stable models.
3. **Geospatial analysis**: computes tract-level metrics, percentiles, and transparent
   service-gap scores.
4. **API/search/cache layer**: exposes FastAPI endpoints, cached hot queries, and
   optional OpenSearch-backed faceted search.
5. **Dashboard + observability**: provides a map-oriented analyst UI, health endpoints,
   structured logs, and ingestion-run visibility.

## Local Development

Copy environment defaults before starting the stack. The local `.env` file is
ignored by git and holds development secrets such as the OpenSearch bootstrap
password.

```powershell
Copy-Item .env.example .env
```

Start the full local stack:

```powershell
docker compose up --build
```

Admin endpoints require the `ADMIN_TOKEN` from `.env` in an `X-Admin-Token`
header. In PowerShell, use `curl.exe` and double-quote the header; this works
for tokens containing an apostrophe or dots:

```powershell
curl.exe -X POST "http://localhost:8000/api/admin/ingest/census_acs" `
  -H "X-Admin-Token: your'token.with.dots"
```

If you edit `.env` after the stack is already running, recreate the API
container before retrying:

```powershell
docker compose up -d --force-recreate api
```

You can then check the status of the job by taking the task_id you were handed
and passing that to, e.g.:

```powershell
$TASK_ID = "3b68d46f-a5ce-4c5e-84af-5a6461042ed8"
docker compose exec -T worker python -c "from celery.result import AsyncResult; from app.workers.celery_app import celery_app; r=AsyncResult('$TASK_ID', app=celery_app); print({'state': r.state, 'ready': r.ready(), 'result': r.result if r.ready() else None})"
```

Useful URLs:

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Health: http://localhost:8000/healthz
- Dashboard: http://localhost:5173
- OpenSearch: http://localhost:9200

## First Milestones

- **Milestone 1**: FastAPI app, PostGIS database, Alembic migrations, Celery worker,
  Redis, structured logs, health endpoints, and ingestion-run tables.
- **Milestone 2**: Massachusetts census tract geometries and ACS vulnerability fields.
- **Milestone 3**: OSM amenities and CMS provider ingestion.
- **Milestone 4**: tract-level metrics, distance calculations, and vulnerability
  percentiles.
- **Milestone 5**: Civic Access Index scoring with explanation objects and limitations.
- **Milestone 6**: map dashboard, tract side panel, and data operations page.
- **Milestone 7**: OpenSearch indexing, Terraform-managed AWS deployment, and CI/CD.

## Scoring V1

The first transparent scoring formula is intentionally plain:

```text
Civic Access Index =
  0.35 * healthcare_gap_score
+ 0.25 * food_gap_score
+ 0.20 * transit_gap_score
+ 0.20 * socioeconomic_vulnerability_score
```

Each subscore is percentile-normalized from tract-level metrics. Score explanations
include the main drivers and limitations so the platform remains inspectable rather
than pretending to be definitive policy advice.

## API Surface

Initial endpoint groups:

- `/healthz`, `/readyz`, `/version`
- `/api/tracts`, `/api/tracts/{geoid}`, `/api/tracts/{geoid}/metrics`,
  `/api/tracts/{geoid}/explanation`, `/api/tracts/{geoid}/nearby-amenities`
- `/api/amenities`, `/api/providers`, `/api/search`
- `/api/scores/top`, `/api/scores/distribution`
- `/api/ingestion-runs`, `/api/data-sources`
- `/api/admin/ingest/{source_name}`, `/api/admin/recompute-scores`,
  `/api/admin/reindex-search`

## Public-Interest Caveat

Civic Access Index is not policy advice and is not a definitive equity model. It is a
data-integration and analysis platform that demonstrates how heterogeneous civic
datasets can be operationalized into inspectable geospatial metrics.
