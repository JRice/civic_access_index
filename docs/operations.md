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

The API and worker need `DATABASE_URL`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND`, `RAW_SNAPSHOT_ROOT`, and `ADMIN_TOKEN`. The local
`.env.example` provides development defaults; do not commit real secrets.
