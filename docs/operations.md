# Operations

Local stack:

```bash
docker compose up --build
```

Operational checks:

- `/healthz` confirms the API process is alive.
- `/readyz` will evolve into a dependency readiness check.
- `/api/data-sources` lists discoverable source adapters and persisted source metadata.
- `/api/ingestion-runs` exposes source refresh history.
- `/api/ingestion-runs/{run_id}` shows a single run, including counts, status,
  raw snapshot path, and any failure summary.
- Celery queues separate ingestion, analysis, and search indexing work.
- Raw snapshots land in local object-storage paths during development and S3 in AWS.

## Census Ingestion

Trigger Massachusetts TIGER tract geometry ingestion:

```bash
curl -X POST "http://localhost:8000/api/admin/ingest/census_tiger" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

Trigger Massachusetts ACS vulnerability ingestion after TIGER has completed:

```bash
curl -X POST "http://localhost:8000/api/admin/ingest/census_acs" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

Check the returned Celery task id:

```bash
docker compose exec -T worker python -c "from celery.result import AsyncResult; from app.workers.celery_app import celery_app; r=AsyncResult('TASK_ID', app=celery_app); print({'state': r.state, 'ready': r.ready(), 'result': r.result if r.ready() else None})"
```

## Amenity and Provider Ingestion

Trigger Massachusetts OpenStreetMap amenity ingestion:

```bash
curl -X POST "http://localhost:8000/api/admin/ingest/osm_overpass" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

PowerShell:

```powershell
curl.exe -X POST "http://localhost:8000/api/admin/ingest/osm_overpass" `
  -H "X-Admin-Token: your'token.with.dots"
```

Trigger Massachusetts CMS hospital provider ingestion:

```bash
curl -X POST "http://localhost:8000/api/admin/ingest/cms_providers" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

PowerShell:

```powershell
curl.exe -X POST "http://localhost:8000/api/admin/ingest/cms_providers" `
  -H "X-Admin-Token: your'token.with.dots"
```

Inspect data:

```powershell
curl.exe "http://localhost:8000/api/amenities?category=healthcare&city=Boston&limit=25"
curl.exe "http://localhost:8000/api/providers?state=MA&provider_type=Acute&limit=25"
curl.exe "http://localhost:8000/api/ingestion-runs?limit=10"
```

OSM uses the public Overpass API, which can rate limit or temporarily reject large
queries. CMS hospital provider rows are address-only because the official dataset
does not include coordinates; provider geometry is left null.

## Metric Recompute

Trigger tract-level metric recomputation after tracts, ACS fields, and amenities
have been ingested:

```bash
curl -X POST "http://localhost:8000/api/admin/recompute-scores" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

PowerShell:

```powershell
curl.exe -X POST "http://localhost:8000/api/admin/recompute-scores" `
  -H "X-Admin-Token: your'token.with.dots"
```

Check the returned Celery task id:

```powershell
$TASK_ID = "returned-task-id"
docker compose exec -T worker python -c "from celery.result import AsyncResult; from app.workers.celery_app import celery_app; r=AsyncResult('$TASK_ID', app=celery_app); print({'state': r.state, 'ready': r.ready(), 'result': r.result if r.ready() else None})"
```

Inspect computed metrics:

```powershell
curl.exe "http://localhost:8000/api/tracts/25001010100/metrics"
curl.exe "http://localhost:8000/api/scores/top?score_type=vulnerability_poverty_rate&limit=10"
curl.exe "http://localhost:8000/api/scores/distribution?score_type=nearest_food_access_distance_m"
```

Available metric categories:

- Healthcare access proximity from OSM healthcare amenities.
- Pharmacy proximity from OSM pharmacies.
- Food access proximity from OSM supermarkets, grocery stores, convenience stores,
  and food banks.
- ACS vulnerability indicators and percentiles.
- Transit proximity is represented as `not_available` until transit stop data exists.

CMS provider rows with null geometry are excluded from spatial distance and bbox
metrics. OSM healthcare amenities currently drive mapped healthcare-access metrics.

The recompute task also persists the current V1 subscores and composite score in
`access_scores`. Inspect score rollups and explanations:

```powershell
curl.exe "http://localhost:8000/api/scores/top?score_type=civic_access_index&limit=10"
curl.exe "http://localhost:8000/api/scores/distribution?score_type=civic_access_index"
curl.exe "http://localhost:8000/api/tracts/25001010100/explanation"
```

The API and worker need `DATABASE_URL`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND`, `RAW_SNAPSHOT_ROOT`, and `ADMIN_TOKEN`. The local
`.env.example` provides development defaults; do not commit real secrets.
