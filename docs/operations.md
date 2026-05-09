# Operations

Local stack:

```bash
docker compose up --build
```

Operational checks:

- `/healthz` confirms the API process is alive.
- `/readyz` will evolve into a dependency readiness check.
- `/api/ingestion-runs` will expose source refresh history.
- Celery queues separate ingestion, analysis, and search indexing work.
- Raw snapshots land in local object-storage paths during development and S3 in AWS.

