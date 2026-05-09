# API Examples

```bash
curl http://localhost:8000/healthz
curl "http://localhost:8000/api/tracts?state=25&limit=10"
curl http://localhost:8000/api/tracts/25017383100/explanation
curl "http://localhost:8000/api/search?q=pharmacy&type=amenity"
```

Admin ingestion triggers require `X-Admin-Token`.

```bash
curl -X POST http://localhost:8000/api/admin/ingest/census_acs \
  -H "X-Admin-Token: change-me"
```

